import json

import frappe
import requests
from frappe.integrations.utils import create_request_log


class MamoPayClient:
	def __init__(self):
		from frappe_mamopay.frappe_mamopay.doctype.mamo_pay_settings.mamo_pay_settings import (
			MamoPaySettings,
		)

		settings = MamoPaySettings.get_instance()
		self.base_url = settings.base_url
		self.headers = {
			"Authorization": f"Bearer {settings.get_api_key()}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		}

	def _request(self, method, endpoint, data=None, log=True):
		url = f"{self.base_url}{endpoint}"
		integration_request = None

		if log:
			integration_request = create_request_log(
				data=data or {},
				service_name="Mamo Pay",
				url=url,
			)

		try:
			response = requests.request(
				method=method,
				url=url,
				headers=self.headers,
				json=data if method in ("POST", "PATCH") else None,
				timeout=30,
			)
			response_data = response.json()

			if integration_request:
				if response.ok:
					integration_request.update_status(response_data, "Completed")
				else:
					integration_request.update_status(response_data, "Failed")

			if not response.ok:
				error_msg = response_data.get("message") or response_data.get("messages") or response.text
				frappe.throw(f"Mamo Pay API error ({response.status_code}): {error_msg}")

			return response_data

		except requests.exceptions.RequestException as e:
			if integration_request:
				integration_request.update_status({"error": str(e)}, "Failed")
			frappe.throw(f"Mamo Pay API request failed: {e}")

	def create_payment_link(self, **params):
		"""Create a payment link. POST /links"""
		return self._request("POST", "links", data=params)

	def get_payment_link(self, link_id):
		"""Get payment link details. GET /links/{linkId}"""
		return self._request("GET", f"links/{link_id}")

	def get_charge(self, charge_id):
		"""Get charge details. GET /charges/{chargeId}"""
		return self._request("GET", f"charges/{charge_id}")

	def create_refund(self, charge_id):
		"""Initiate a refund. POST /charges/{chargeId}/refunds"""
		return self._request("POST", f"charges/{charge_id}/refunds")

	def create_webhook(self, url, enabled_events, auth_header=None):
		"""Register a webhook. POST /webhooks"""
		data = {
			"url": url,
			"enabled_events": enabled_events,
		}
		if auth_header:
			data["auth_header"] = auth_header
		return self._request("POST", "webhooks", data=data)

	def list_webhooks(self):
		"""List all webhooks. GET /webhooks"""
		return self._request("GET", "webhooks")
