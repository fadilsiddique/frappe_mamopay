frappe.ui.form.on("Mamo Pay Settings", {
	refresh(frm) {
		// Disable password strength checks on API key and webhook secret
		// These are API tokens, not user passwords — the zxcvbn check
		// causes an orjson serialization error on large entropy values
		["api_key", "webhook_secret"].forEach((field) => {
			let control = frm.fields_dict[field];
			if (control && control.disable_password_checks) {
				control.disable_password_checks();
			}
		});
	},
});
