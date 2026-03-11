import frappe
from frappe.model.document import Document

SANDBOX_URL = "https://sandbox.dev.business.mamopay.com/manage_api/v1/"
PRODUCTION_URL = "https://business.mamopay.com/manage_api/v1/"


class MamoPaySettings(Document):
	def validate(self):
		self.base_url = SANDBOX_URL if self.is_sandbox else PRODUCTION_URL

	def get_api_key(self):
		return self.get_password("api_key")

	def get_webhook_secret(self):
		return self.get_password("webhook_secret")

	@staticmethod
	def get_instance():
		settings = frappe.get_single("Mamo Pay Settings")
		if not settings.enabled:
			frappe.throw("Mamo Pay is not enabled. Please enable it in Mamo Pay Settings.")
		return settings
