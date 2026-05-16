# Frappe Mamo Pay - CLAUDE.md

## Project Overview

Frappe app integrating [Mamo Pay](https://mamopay.com) payment gateway with ERPNext. Handles payment links, webhooks, refunds, and auto-creates Payment Entries for Sales Orders.

**Publisher:** Upscape Technologies (info@upscapetech.com)
**License:** MIT
**Branches:** `main` (Frappe v16), `version-15` (Frappe v15) — keep in sync via cherry-picks.

## Project Structure

```
frappe_mamopay/
├── frappe_mamopay/
│   ├── api.py                          # All whitelisted API endpoints
│   ├── mamopay_client.py               # HTTP client wrapping Mamo Pay REST API
│   ├── hooks.py                        # Frappe app hooks
│   ├── frappe_mamopay/
│   │   ├── doctype/
│   │   │   ├── mamo_pay_settings/      # Single DocType — API keys, accounts config
│   │   │   └── mamo_pay_payment/       # Standard DocType — payment records (MAMO-.#####)
│   │   └── custom/
│   │       ├── sales_order.json        # Custom fields: custom_mamo_pay_payment, custom_mamo_pay_status
│   │       ├── sales_order_item.json
│   │       └── packed_item.json
│   ├── www/
│   │   └── mamopay-test.*              # Test page at /mamopay-test
│   └── templates/
├── api.md                              # Full API documentation
└── README.md
```

## Key Files

- **`api.py`** — Whitelisted endpoints: `create_payment_link`, `verify_payment`, `webhook`, `refund_payment`, `register_webhook`, `list_webhooks`, `update_webhook`, `delete_webhook`
- **`mamopay_client.py`** — `MamoPayClient` class wrapping Mamo Pay REST API with Integration Request logging
- **`mamo_pay_payment.py`** — Payment document controller with webhook processing, Sales Order auto-submit, and Payment Entry creation
- **`mamo_pay_settings.py`** — Settings singleton with `get_api_key()`, `get_webhook_secret()` (both Password fields using `get_password()`)

## Architecture & Payment Flow

```
Create Link → Payment → Webhook/Verify → Update Status → Hook on Reference Doc
                                              ↓
                              (Sales Order) → Auto-submit SO → Create Payment Entry
                              (Other)      → Call on_payment_authorized(status)
```

### Event Status Map

| Webhook Event            | Payment Status   |
|--------------------------|------------------|
| `charge.succeeded`       | Captured         |
| `charge.failed`          | Failed           |
| `charge.authorized`      | Authorized       |
| `charge.refunded`        | Refunded         |
| `charge.refund_initiated`| Refund Initiated |
| `charge.refund_failed`   | Captured         |

### Sales Order Integration

When `reference_doctype` is "Sales Order":
1. Updates `custom_mamo_pay_payment` and `custom_mamo_pay_status` on SO via `db_set`
2. Auto-submits SO if still Draft (`docstatus == 0`)
3. Creates Payment Entry with Mamo Pay processing fee deductions when status is "Captured"
4. Duplicate PE prevented by checking `reference_no == self.name`
5. PE creation runs as Administrator (`frappe.set_user("Administrator")` with `try/finally` restore)

### Payment Entry Deductions

```python
deduction = (so.grand_total * mamo_charge_percent / 100) + mamo_charge_amount
```

Only added if deduction > 0 and `default_deduction_account` is set in Mamo Pay Settings.

## Mamo Pay Settings Fields

| Field                      | Type     | Purpose                                    |
|----------------------------|----------|--------------------------------------------|
| `enabled`                  | Check    | Toggle integration on/off                  |
| `is_sandbox`               | Check    | Sandbox vs production (different API keys) |
| `api_key`                  | Password | Mamo Pay API key                           |
| `webhook_secret`           | Password | Mandatory secret for webhook auth          |
| `default_currency`         | Select   | AED, USD, EUR, GBP, SAR                   |
| `return_url`               | Data     | Success redirect URL                       |
| `failure_return_url`       | Data     | Failure redirect URL                       |
| `default_payment_account`  | Link     | Account for Payment Entry `paid_to`        |
| `default_deduction_account`| Link     | Account for Mamo Pay fee deduction row     |
| `mamo_charge_percent`      | Percent  | Processing fee percentage                  |
| `mamo_charge_amount`       | Float    | Fixed processing fee amount                |

## API URLs

- **Sandbox:** `https://sandbox.dev.business.mamopay.com/manage_api/v1/`
- **Production:** `https://business.mamopay.com/manage_api/v1/`

## Security Notes

- Webhook endpoint (`allow_guest=True`) validates `Authorization` header via `hmac.compare_digest`
- Webhook secret is **mandatory** — requests rejected if not configured
- All other endpoints require `Mamo Pay Payment` write permission (System Manager by default)
- `verify_payment` always checks server-side with Mamo Pay API — never trusts client redirect params
- Payload size limit: 1 MB for webhooks, 10 KB for custom_data
- PE creation uses `frappe.set_user("Administrator")` — always wrapped in `try/finally`

## Development Notes

- Uses `pre-commit` with ruff, eslint, prettier, pyupgrade
- DocType JSON files are auto-generated — edit via Frappe desk or carefully by hand
- `get_payment_entry()` from ERPNext checks permissions internally — that's why Administrator escalation is needed
- Non-charge webhook events (e.g., `payment_link.create`) are filtered early via `EVENT_STATUS_MAP`
- Test page at `/mamopay-test` for sandbox testing

## Sandbox Test Cards

| Card Number             | Result  |
|-------------------------|---------|
| `4242 4242 4242 4242`   | Success |
| `4659 1055 6905 1157`   | Success |
| `4111 1111 1111 1111`   | Success |
| `4567 3613 2598 1788`   | Failure |
| `4095 2548 0264 2505`   | Failure |

**CVV:** `123` | **Expiry:** `01/28` | **3DS Password:** `Checkout1!`
