import hmac
import json

import frappe
from frappe_mamopay.mamopay_client import MamoPayClient


@frappe.whitelist()
def create_payment_link(
	title,
	amount,
	amount_currency=None,
	description=None,
	reference_doctype=None,
	reference_name=None,
	customer_email=None,
	customer_name=None,
	return_url=None,
	failure_return_url=None,
	custom_data=None,
):
	"""Create a Mamo Pay payment link and log it as a Mamo Pay Payment record."""
	settings = frappe.get_single("Mamo Pay Settings")
	if not settings.enabled:
		frappe.throw("Mamo Pay is not enabled.")

	amount = float(amount)

	# Build params for Mamo Pay API
	params = {
		"title": title,
		"amount": amount,
		"amount_currency": amount_currency or settings.default_currency,
		"return_url": return_url or settings.return_url,
		"failure_return_url": failure_return_url or settings.failure_return_url,
		"enable_customer_details": True,
	}

	if description:
		params["description"] = description

	if customer_email:
		params["email"] = customer_email

	if customer_name:
		# Split name into first/last for Mamo Pay
		name_parts = customer_name.strip().split(" ", 1)
		params["first_name"] = name_parts[0]
		if len(name_parts) > 1:
			params["last_name"] = name_parts[1]

	if custom_data:
		if isinstance(custom_data, str):
			custom_data = json.loads(custom_data)
		params["custom_data"] = custom_data

	# Call Mamo Pay API
	client = MamoPayClient()
	response = client.create_payment_link(**params)

	# Create Mamo Pay Payment record
	payment = frappe.get_doc({
		"doctype": "Mamo Pay Payment",
		"title": title,
		"amount": amount,
		"amount_currency": params["amount_currency"],
		"description": description,
		"payment_link_id": response.get("id"),
		"payment_url": response.get("payment_url"),
		"status": "Created",
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"customer_email": customer_email,
		"customer_name": customer_name,
		"external_id": response.get("external_id"),
		"mamo_response": json.dumps(response, indent=2),
	})
	payment.insert(ignore_permissions=True)

	return {
		"name": payment.name,
		"payment_url": response.get("payment_url"),
		"payment_link_id": response.get("id"),
	}


@frappe.whitelist()
def verify_payment(payment_link_id, transaction_id=None):
	"""Verify payment status with Mamo Pay API. Called by frontend after redirect."""
	payment = frappe.get_doc("Mamo Pay Payment", {"payment_link_id": payment_link_id})

	# Always verify server-side — never trust redirect params
	client = MamoPayClient()
	link_data = client.get_payment_link(payment_link_id)

	# If transaction_id provided, also fetch charge details
	charge_data = None
	if transaction_id:
		try:
			charge_data = client.get_charge(transaction_id)
		except Exception:
			pass

	# Determine status from charge data or link data
	if charge_data:
		charge_status = charge_data.get("status", "").lower()
		if charge_status == "captured":
			new_status = "Captured"
		elif charge_status == "failed":
			new_status = "Failed"
		elif charge_status == "authorized":
			new_status = "Authorized"
		else:
			new_status = payment.status

		payment.transaction_id = transaction_id
		payment.mamo_response = json.dumps(charge_data, indent=2)
	else:
		new_status = payment.status

	if new_status != payment.status:
		payment.status = new_status
		payment.save(ignore_permissions=True)

		# Call hook on reference document
		payment._call_payment_hook()

	return {
		"name": payment.name,
		"status": payment.status,
		"amount": payment.amount,
		"amount_currency": payment.amount_currency,
		"transaction_id": payment.transaction_id,
	}


@frappe.whitelist(allow_guest=True, xss_safe=True, methods=["POST"])
def webhook():
	"""Receive webhook notifications from Mamo Pay."""
	# Validate webhook secret
	settings = frappe.get_single("Mamo Pay Settings")
	webhook_secret = settings.get_webhook_secret()

	if webhook_secret:
		auth_header = frappe.request.headers.get("Authorization", "")
		if not hmac.compare_digest(auth_header, webhook_secret):
			frappe.throw("Unauthorized", frappe.AuthenticationError)

	# Parse payload
	try:
		payload = json.loads(frappe.request.data)
	except (json.JSONDecodeError, TypeError):
		frappe.throw("Invalid JSON payload")

	event_type = payload.get("event_type") or payload.get("type", "")
	charge_data = payload.get("data", payload)

	# Find the corresponding Mamo Pay Payment
	payment_link_id = charge_data.get("payment_link_id") or charge_data.get("paymentLinkId")
	external_id = charge_data.get("external_id")

	payment = None
	if payment_link_id:
		payment = frappe.db.exists("Mamo Pay Payment", {"payment_link_id": payment_link_id})
	if not payment and external_id:
		payment = frappe.db.exists("Mamo Pay Payment", {"external_id": external_id})

	if payment:
		payment_doc = frappe.get_doc("Mamo Pay Payment", payment)
		payment_doc.update_from_webhook(event_type, charge_data)
	else:
		# Log unmatched webhook for manual review
		frappe.log_error(
			title="Mamo Pay: Unmatched webhook",
			message=json.dumps(payload, indent=2),
		)

	# Always return 200 to acknowledge receipt
	return {"status": "ok"}


def _parse_events(enabled_events):
	"""Parse enabled_events from various input formats into a list."""
	if isinstance(enabled_events, list):
		return enabled_events
	if isinstance(enabled_events, str):
		# Try JSON array first, then comma-separated
		try:
			parsed = json.loads(enabled_events)
			if isinstance(parsed, list):
				return parsed
		except (json.JSONDecodeError, TypeError):
			pass
		return [e.strip() for e in enabled_events.split(",") if e.strip()]
	return []


@frappe.whitelist()
def register_webhook(url, enabled_events, auth_header=None):
	"""Register a webhook with Mamo Pay."""
	enabled_events = _parse_events(enabled_events)

	client = MamoPayClient()
	return client.create_webhook(url, enabled_events, auth_header=auth_header)


@frappe.whitelist()
def list_webhooks():
	"""List all registered webhooks from Mamo Pay."""
	client = MamoPayClient()
	return client.list_webhooks()


@frappe.whitelist()
def update_webhook(webhook_id, url, enabled_events, auth_header=None):
	"""Update an existing webhook in Mamo Pay."""
	enabled_events = _parse_events(enabled_events)

	client = MamoPayClient()
	return client.update_webhook(webhook_id, url, enabled_events, auth_header=auth_header)


@frappe.whitelist()
def delete_webhook(webhook_id):
	"""Delete a webhook from Mamo Pay."""
	client = MamoPayClient()
	return client.delete_webhook(webhook_id)


@frappe.whitelist()
def refund_payment(payment_name):
	"""Initiate a refund for a captured payment."""
	payment = frappe.get_doc("Mamo Pay Payment", payment_name)

	if payment.status != "Captured":
		frappe.throw(f"Cannot refund payment with status '{payment.status}'. Only captured payments can be refunded.")

	if not payment.transaction_id:
		frappe.throw("Transaction ID not found. Cannot process refund.")

	client = MamoPayClient()
	response = client.create_refund(payment.transaction_id, payment.amount)

	payment.status = "Refund Initiated"
	payment.mamo_response = json.dumps(response, indent=2)
	payment.save(ignore_permissions=True)

	return {
		"name": payment.name,
		"status": payment.status,
	}
