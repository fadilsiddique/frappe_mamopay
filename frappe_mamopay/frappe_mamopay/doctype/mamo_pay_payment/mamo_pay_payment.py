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
		"""Call payment hook on the reference document if it exists."""
		if not self.reference_doctype or not self.reference_name:
			return

		try:
			if self.reference_doctype == "Sales Order":
				self._handle_sales_order_payment()
			else:
				ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
				if hasattr(ref_doc, "on_payment_authorized"):
					ref_doc.on_payment_authorized(self.status)
		except Exception:
			frappe.log_error(
				title=f"Mamo Pay: Error in payment hook for {self.reference_doctype} {self.reference_name}",
			)

	def _handle_sales_order_payment(self):
		"""Handle Sales Order submission and Payment Entry creation."""
		so = frappe.get_doc("Sales Order", self.reference_name)

		# Update custom fields (works for both Draft and Submitted)
		so.db_set("custom_mamo_pay_payment", self.name, update_modified=False)
		so.db_set("custom_mamo_pay_status", self.status, update_modified=False)

		# Auto-submit Sales Order if still in Draft
		if so.docstatus == 0:
			so.reload()
			so.flags.ignore_permissions = True
			so.submit()

		# Create Payment Entry only when payment is captured
		if self.status == "Captured":
			self._create_payment_entry_for_sales_order(so)

	def _create_payment_entry_for_sales_order(self, so):
		"""Create a Payment Entry against the Sales Order with Mamo Pay deductions."""
		# Prevent duplicate Payment Entries
		existing_pe = frappe.db.exists("Payment Entry", {
			"reference_no": self.name,
			"docstatus": ["!=", 2],
		})
		if existing_pe:
			return

		settings = frappe.get_single("Mamo Pay Settings")
		if not settings.default_payment_account:
			frappe.log_error(
				title="Mamo Pay: Missing payment account",
				message="Default Payment Account not set in Mamo Pay Settings. Cannot create Payment Entry.",
			)
			return

		# Ensure SO is submitted before creating PE
		if so.docstatus != 1:
			so.reload()

		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		pe = get_payment_entry("Sales Order", so.name)

		# Override with Mamo Pay configured account
		pe.paid_to = settings.default_payment_account
		pe.paid_to_account_currency = frappe.db.get_value(
			"Account", settings.default_payment_account, "account_currency"
		)

		# Set reference for traceability and duplicate detection
		pe.reference_no = self.name
		pe.reference_date = frappe.utils.nowdate()

		# Add Mamo Pay processing fee deduction
		deduction_amount = (
			(so.grand_total * (settings.mamo_charge_percent or 0) / 100)
			+ (settings.mamo_charge_amount or 0)
		)
		if deduction_amount > 0 and settings.default_deduction_account:
			pe.append("deductions", {
				"account": settings.default_deduction_account,
				"cost_center": so.get("cost_center") or frappe.get_cached_value(
					"Company", so.company, "cost_center"
				),
				"amount": deduction_amount,
				"description": "Mamo Pay processing fee",
			})

		pe.flags.ignore_permissions = True
		pe.insert()
		pe.submit()
