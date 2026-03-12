# Frappe Mamo Pay

Payment gateway integration for [Mamo Pay](https://mamopay.com) built on the [Frappe Framework](https://frappeframework.com).

Create payment links, process payments, handle webhooks, and manage refunds — all from within your Frappe/ERPNext site.

## Features

- **Payment Links** — Create Mamo Pay payment links via API and track them as Frappe documents
- **Server-Side Verification** — Verify payment status directly with Mamo Pay API (never trust client-side redirects)
- **Webhook Handler** — Receive and process real-time payment notifications from Mamo Pay
- **Refunds** — Initiate refunds for captured payments
- **Reference Document Hooks** — Automatically trigger `on_payment_authorized()` on linked documents (e.g., Sales Order, Custom DocType)
- **Sandbox Support** — Toggle between sandbox and production environments
- **Integration Request Logging** — All API calls are logged in Frappe's Integration Request for debugging

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/your-org/frappe_mamopay --branch main
bench --site your-site.localhost install-app frappe_mamopay
bench --site your-site.localhost migrate
```

### Requirements

- Python >= 3.14
- Frappe Framework >= v16

## Configuration

1. Go to **Mamo Pay Settings** in Frappe desk (`/app/mamo-pay-settings`)
2. Fill in the following:

| Setting | Description |
|---|---|
| **Enabled** | Check to activate the integration |
| **Sandbox Mode** | Check to use Mamo Pay sandbox environment (for testing) |
| **API Key** | Your Mamo Pay API key (from [Mamo Pay Business Dashboard](https://business.mamopay.com)) |
| **Webhook Secret** | Shared secret for verifying incoming webhooks |
| **Default Currency** | Fallback currency — `AED`, `USD`, `EUR`, `GBP`, or `SAR` |
| **Success Return URL** | Where customers are redirected after successful payment |
| **Failure Return URL** | Where customers are redirected after failed payment |

3. Click **Save**

> **Note:** Sandbox and production use different API keys. Get your sandbox key from [sandbox.dev.business.mamopay.com](https://sandbox.dev.business.mamopay.com).

## Usage

### Creating a Payment Link

```python
import frappe

result = frappe.call(
    "frappe_mamopay.api.create_payment_link",
    title="Invoice #1001",
    amount=150.00,
    amount_currency="AED",
    description="Payment for services",
    customer_email="customer@example.com",
    customer_name="John Doe",
    reference_doctype="Sales Order",
    reference_name="SO-0001",
)

# result = {
#     "name": "MAMO-00001",
#     "payment_url": "https://sandbox.dev.business.mamopay.com/pay/...",
#     "payment_link_id": "MB-LINK-..."
# }
```

### Verifying a Payment

After the customer completes payment and is redirected back:

```python
result = frappe.call(
    "frappe_mamopay.api.verify_payment",
    payment_link_id="MB-LINK-37D90AAF51",
    transaction_id="MPB-CHRG-BEE56990A9",
)

# result = {
#     "name": "MAMO-00001",
#     "status": "Captured",
#     "amount": 150.0,
#     "amount_currency": "AED",
#     "transaction_id": "MPB-CHRG-BEE56990A9"
# }
```

### Processing Refunds

```python
result = frappe.call(
    "frappe_mamopay.api.refund_payment",
    payment_name="MAMO-00001",
)
```

### Handling Payment Status in Your DocType

Implement `on_payment_authorized` on any document linked via `reference_doctype` / `reference_name`:

```python
class SalesOrder(Document):
    def on_payment_authorized(self, status):
        if status == "Captured":
            self.status = "Paid"
            self.save()
        elif status == "Failed":
            frappe.sendmail(...)
```

## Webhook Setup

1. Set a **Webhook Secret** in Mamo Pay Settings
2. Register the webhook URL with Mamo Pay:
   ```
   POST https://your-site.com/api/method/frappe_mamopay.api.webhook
   ```
3. Mamo Pay will send events for: `charge.succeeded`, `charge.failed`, `charge.refunded`, `charge.refund_initiated`, `charge.refund_failed`, `charge.authorized`

The webhook handler validates the `Authorization` header against your configured secret.

## Payment Lifecycle

```
Created  -->  Authorized  -->  Captured  -->  Refund Initiated  -->  Refunded
                  |                |
                  v                v
               Failed        Refund Failed (reverts to Captured)
```

## DocTypes

| DocType | Type | Description |
|---|---|---|
| **Mamo Pay Settings** | Single | API configuration, credentials, and defaults |
| **Mamo Pay Payment** | Standard | Payment transaction records (auto-named `MAMO-.#####`) |

## API Reference

See [api.md](api.md) for full API documentation with endpoints, request/response examples, and integration flow diagrams.

## Test Page

A built-in test page is available at `/mamopay-test` on your site. It provides a UI to:
- Create payment links
- Verify payments
- Process refunds
- View API request/response logs

## Sandbox Test Cards

| Card Number | Result |
|---|---|
| `4242 4242 4242 4242` | Success |
| `4659 1055 6905 1157` | Success |
| `4111 1111 1111 1111` | Success |
| `4567 3613 2598 1788` | Failure |
| `4095 2548 0264 2505` | Failure |

**CVV:** `123` | **Expiry:** `01/28` | **3DS Password:** `Checkout1!`

## Contributing

This app uses `pre-commit` for code formatting and linting:

```bash
cd apps/frappe_mamopay
pre-commit install
```

Tools: ruff, eslint, prettier, pyupgrade

## License

MIT
