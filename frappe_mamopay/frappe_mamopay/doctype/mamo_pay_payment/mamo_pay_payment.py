import json

import frappe
from frappe.model.document import Document

EVENT_STATUS_MAP = {
	"charge.succeeded": "Captured",
	"charge.failed": "Failed",
	"charge.refunded": "Refunded",
	"charge.refund_initiated": "Refund Initiated",
	"charge.refund_failed": "Captured",
	"charge.authorized": "Authorized",
}


class MamoPayPayment(Document):
	def before_insert(self):
		if not self.external_id:
			self.external_id = self.name

	def update_from_webhook(self, event_type, payload):
		"""Update payment status from a webhook event."""
		new_status = EVENT_STATUS_MAP.get(event_type)
		if not new_status:
			return

		# Don't downgrade status
		if self.status == "Captured" and new_status == "Authorized":
			return

		self.status = new_status
		self.mamo_response = json.dumps(payload, indent=2)

		# Extract transaction ID from payload if available
		charge_id = payload.get("id") or payload.get("charge_id")
		if charge_id:
			self.transaction_id = charge_id

		self.save(ignore_permissions=True)

		# Call hook on reference document
		self._call_payment_hook()

	def _call_payment_hook(self):
		"""Call on_payment_authorized on the reference document if it exists."""
		if not self.reference_doctype or not self.reference_name:
			return

		try:
			ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
			if hasattr(ref_doc, "on_payment_authorized"):
				ref_doc.on_payment_authorized(self.status)
		except Exception:
			frappe.log_error(
				title=f"Mamo Pay: Error calling on_payment_authorized for {self.reference_doctype} {self.reference_name}",
			)
