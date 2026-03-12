const AVAILABLE_EVENTS = [
	"charge.succeeded",
	"charge.failed",
	"charge.refund_initiated",
	"charge.refunded",
	"charge.refund_failed",
	"charge.card_verified",
	"charge.authorized",
	"subscription.succeeded",
	"subscription.failed",
	"payment_link.create",
	"payout.processed",
	"payout.failed",
	"expense.create",
	"expense.update",
	"card_transaction.create",
	"card_transaction.update",
];

frappe.ui.form.on("Mamo Pay Settings", {
	refresh(frm) {
		// Disable password strength checks on API key and webhook secret
		["api_key", "webhook_secret"].forEach((field) => {
			let control = frm.fields_dict[field];
			if (control && control.disable_password_checks) {
				control.disable_password_checks();
			}
		});

		if (frm.doc.enabled) {
			frm.add_custom_button(__("List Webhooks"), () => load_webhooks(frm), __("Webhooks"));
			frm.add_custom_button(__("Register Webhook"), () => register_webhook_dialog(frm), __("Webhooks"));
		}
	},
});

function load_webhooks(frm) {
	frappe.call({
		method: "frappe_mamopay.api.list_webhooks",
		freeze: true,
		freeze_message: __("Fetching webhooks..."),
		callback(r) {
			const webhooks = r.message || [];
			if (!webhooks.length) {
				frappe.msgprint(__("No webhooks registered."));
				return;
			}
			show_webhooks_dialog(frm, webhooks);
		},
	});
}

function show_webhooks_dialog(frm, webhooks) {
	let rows = webhooks
		.map(
			(wh, idx) => `
		<tr>
			<td><code style="font-size: 11px;">${frappe.utils.escape_html(wh.id)}</code></td>
			<td style="max-width: 250px; word-break: break-all;">${frappe.utils.escape_html(wh.url)}</td>
			<td style="font-size: 12px;">${(wh.enabled_events || []).map(e => frappe.utils.escape_html(e)).join(", ")}</td>
			<td>
				<button class="btn btn-xs btn-default btn-edit-wh" data-idx="${idx}">
					${__("Edit")}
				</button>
				<button class="btn btn-xs btn-danger btn-delete-wh" data-idx="${idx}">
					${__("Delete")}
				</button>
			</td>
		</tr>`
		)
		.join("");

	let d = new frappe.ui.Dialog({
		title: __("Registered Webhooks"),
		size: "extra-large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "webhooks_html",
				options: `
					<table class="table table-bordered table-sm">
						<thead><tr>
							<th>${__("ID")}</th>
							<th>${__("URL")}</th>
							<th>${__("Events")}</th>
							<th style="width: 120px;">${__("Actions")}</th>
						</tr></thead>
						<tbody>${rows}</tbody>
					</table>`,
			},
		],
	});

	d.$wrapper.on("click", ".btn-delete-wh", function () {
		let wh = webhooks[$(this).data("idx")];
		frappe.confirm(__("Delete webhook {0}?", [wh.id]), () => {
			frappe.call({
				method: "frappe_mamopay.api.delete_webhook",
				args: { webhook_id: wh.id },
				freeze: true,
				callback() {
					frappe.show_alert({ message: __("Webhook deleted"), indicator: "green" });
					d.hide();
					load_webhooks(frm);
				},
			});
		});
	});

	d.$wrapper.on("click", ".btn-edit-wh", function () {
		let wh = webhooks[$(this).data("idx")];
		d.hide();
		edit_webhook_dialog(frm, wh);
	});

	d.show();
}

function register_webhook_dialog(frm) {
	let site_url = window.location.origin;
	let default_url = `${site_url}/api/method/frappe_mamopay.api.webhook`;

	let d = new frappe.ui.Dialog({
		title: __("Register Webhook"),
		fields: [
			{
				label: __("Webhook URL"),
				fieldname: "url",
				fieldtype: "Data",
				reqd: 1,
				default: default_url,
			},
			{
				label: __("Auth Header"),
				fieldname: "auth_header",
				fieldtype: "Data",
				description: __("Authentication header value (1-50 chars). Set this as Webhook Secret in settings."),
			},
			{
				label: __("Enabled Events"),
				fieldname: "enabled_events",
				fieldtype: "MultiSelect",
				reqd: 1,
				options: AVAILABLE_EVENTS,
			},
		],
		primary_action_label: __("Register"),
		primary_action(values) {
			let events =
				typeof values.enabled_events === "string"
					? values.enabled_events.split(",").map((e) => e.trim()).filter(Boolean)
					: values.enabled_events;

			frappe.call({
				method: "frappe_mamopay.api.register_webhook",
				args: {
					url: values.url,
					enabled_events: events,
					auth_header: values.auth_header || null,
				},
				freeze: true,
				callback(r) {
					frappe.show_alert({ message: __("Webhook registered: {0}", [r.message.id]), indicator: "green" });
					d.hide();
				},
			});
		},
	});
	d.show();
}

function edit_webhook_dialog(frm, webhook) {
	let events = webhook.enabled_events || [];
	if (typeof events === "string") {
		try { events = JSON.parse(events); } catch (e) { events = []; }
	}

	let d = new frappe.ui.Dialog({
		title: __("Edit Webhook: {0}", [webhook.id]),
		fields: [
			{
				label: __("Webhook URL"),
				fieldname: "url",
				fieldtype: "Data",
				reqd: 1,
				default: webhook.url,
			},
			{
				label: __("Auth Header"),
				fieldname: "auth_header",
				fieldtype: "Data",
				default: webhook.auth_header || "",
				description: __("Authentication header value (1-50 chars)"),
			},
			{
				label: __("Enabled Events"),
				fieldname: "enabled_events",
				fieldtype: "MultiSelect",
				reqd: 1,
				options: AVAILABLE_EVENTS,
				default: events.join(", "),
			},
		],
		primary_action_label: __("Update"),
		primary_action(values) {
			let updated_events =
				typeof values.enabled_events === "string"
					? values.enabled_events.split(",").map((e) => e.trim()).filter(Boolean)
					: values.enabled_events;

			frappe.call({
				method: "frappe_mamopay.api.update_webhook",
				args: {
					webhook_id: webhook.id,
					url: values.url,
					enabled_events: updated_events,
					auth_header: values.auth_header || null,
				},
				freeze: true,
				callback() {
					frappe.show_alert({ message: __("Webhook updated"), indicator: "green" });
					d.hide();
				},
			});
		},
	});
	d.show();
}
