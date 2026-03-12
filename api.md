# Frappe Mamo Pay - API Documentation

Base URL: `https://your-site.com`

All authenticated endpoints require a Frappe session (cookie-based) or OAuth Bearer token in the `Authorization` header. Additionally, endpoints marked with **Role: System Manager** require the user to have write permission on `Mamo Pay Payment`.

---

## 1. Create Payment Link

Creates a Mamo Pay payment link and returns the URL to redirect the customer.

**Endpoint:** `POST /api/method/frappe_mamopay.api.create_payment_link`

**Auth:** Bearer token (OAuth) or session cookie
**Role:** System Manager (or any role with `Mamo Pay Payment` write permission)

### Request Body

| Parameter | Type | Required | Validation |
|---|---|---|---|
| `title` | string | Yes | 1-50 chars |
| `amount` | number | Yes | Must be > 0 |
| `amount_currency` | string | No | `AED`, `USD`, `EUR`, `GBP`, `SAR`. Defaults to Mamo Pay Settings value |
| `description` | string | No | Max 75 chars |
| `reference_doctype` | string | No | Frappe DocType to link this payment to (e.g. `Sales Order`) |
| `reference_name` | string | No | Document name of the reference DocType |
| `customer_email` | string | No | Must be a valid email format |
| `customer_name` | string | No | Auto-split into first/last name for Mamo Pay |
| `return_url` | string | No | Must start with `https://` or `http://`. Defaults to Mamo Pay Settings value |
| `failure_return_url` | string | No | Must start with `https://` or `http://`. Defaults to Mamo Pay Settings value |
| `custom_data` | object | No | JSON object, max 10 KB |

### Example Request

```bash
curl -X POST https://your-site.com/api/method/frappe_mamopay.api.create_payment_link \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Order #1234",
    "amount": 150.00,
    "amount_currency": "AED",
    "description": "Payment for Order #1234",
    "customer_email": "customer@example.com",
    "customer_name": "John Doe",
    "reference_doctype": "Sales Order",
    "reference_name": "SO-0001",
    "custom_data": {"order_id": "1234"}
  }'
```

### Success Response (200)

```json
{
  "message": {
    "name": "MAMO-00001",
    "payment_url": "https://sandbox.dev.business.mamopay.com/pay/mamo-abc123",
    "payment_link_id": "MB-LINK-37D90AAF51"
  }
}
```

### Errors

| Code | Reason |
|---|---|
| `403` | User does not have `Mamo Pay Payment` write permission |
| `417` | Mamo Pay is not enabled, invalid amount, invalid email, or invalid URL |

### After Payment Redirect

After the customer completes payment, Mamo Pay redirects to your `return_url` with query parameters:

```
https://your-app.com/payment/success?paymentLinkId=MB-LINK-37D90AAF51&status=captured&transactionId=MPB-CHRG-BEE56990A9&createdAt=2026-03-10-12-00-00
```

| Parameter | Description |
|---|---|
| `paymentLinkId` | The Mamo Pay link ID |
| `status` | `captured` or `failed` |
| `transactionId` | The charge/transaction ID |
| `createdAt` | Timestamp of the transaction |

---

## 2. Verify Payment

Verifies payment status server-side with Mamo Pay API. **Call this after the customer is redirected back** — never trust redirect query params alone.

**Endpoint:** `POST /api/method/frappe_mamopay.api.verify_payment`

**Auth:** Bearer token (OAuth) or session cookie
**Role:** Any logged-in user

### Request Body

| Parameter | Type | Required | Description |
|---|---|---|---|
| `payment_link_id` | string | Yes | Mamo Pay link ID (from redirect `paymentLinkId` param) |
| `transaction_id` | string | No | Transaction/charge ID (from redirect `transactionId` param) |

### Example Request

```bash
curl -X POST https://your-site.com/api/method/frappe_mamopay.api.verify_payment \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_link_id": "MB-LINK-37D90AAF51",
    "transaction_id": "MPB-CHRG-BEE56990A9"
  }'
```

### Success Response (200)

```json
{
  "message": {
    "name": "MAMO-00001",
    "status": "Captured",
    "amount": 150.0,
    "amount_currency": "AED",
    "transaction_id": "MPB-CHRG-BEE56990A9"
  }
}
```

### Status Values

| Status | Description |
|---|---|
| `Created` | Payment link created, customer hasn't paid yet |
| `Captured` | Payment successfully captured |
| `Failed` | Payment failed |
| `Authorized` | Payment authorized but not yet captured |
| `Refunded` | Payment has been refunded |
| `Refund Initiated` | Refund is being processed |

---

## 3. Webhook

Receives webhook notifications from Mamo Pay. This endpoint is called by Mamo Pay servers, not by your frontend.

**Endpoint:** `POST /api/method/frappe_mamopay.api.webhook`

**Auth:** Guest access. Validated via `Authorization` header matching the **Webhook Secret** configured in Mamo Pay Settings. **A webhook secret must be configured** — requests are rejected if no secret is set.

### Setup

1. Set a **Webhook Secret** in Mamo Pay Settings (Frappe desk) — this is **mandatory**
2. Register this webhook URL with Mamo Pay (via the Register Webhook button in Settings or the API below), using the same secret as the `auth_header`

### Supported Events

| Event | Action |
|---|---|
| `charge.succeeded` | Sets payment status to `Captured` |
| `charge.failed` | Sets payment status to `Failed` |
| `charge.refunded` | Sets payment status to `Refunded` |
| `charge.refund_initiated` | Sets payment status to `Refund Initiated` |
| `charge.refund_failed` | Reverts payment status to `Captured` |
| `charge.authorized` | Sets payment status to `Authorized` |

### Webhook Payload (from Mamo Pay)

```json
{
  "event_type": "charge.succeeded",
  "data": {
    "id": "MPB-CHRG-BEE56990A9",
    "payment_link_id": "MB-LINK-37D90AAF51",
    "status": "captured",
    "amount": 150.00,
    "amount_currency": "AED"
  }
}
```

### Response (200)

```json
{
  "message": {
    "status": "ok"
  }
}
```

### Errors

| Code | Reason |
|---|---|
| `401` | Missing or invalid `Authorization` header, or webhook secret not configured |
| `417` | Invalid JSON payload or payload too large (max 1 MB) |

### Security Notes

- Webhook secret is **mandatory** — if not configured, all webhooks are rejected and an error is logged
- The `Authorization` header is compared using `hmac.compare_digest()` to prevent timing attacks
- Maximum payload size is 1 MB
- Unmatched webhooks log only identifiers (not full payload with customer data)

### Reference Document Hook

When a payment status changes via webhook, the system calls `on_payment_authorized(status)` on the linked reference document (if `reference_doctype` and `reference_name` were set during payment creation). Implement this method on your DocType to handle business logic:

```python
class SalesOrder(Document):
    def on_payment_authorized(self, status):
        if status == "Captured":
            self.status = "Paid"
            self.save()
```

---

## 4. Refund Payment

Initiates a full refund for a captured payment.

**Endpoint:** `POST /api/method/frappe_mamopay.api.refund_payment`

**Auth:** Bearer token (OAuth) or session cookie
**Role:** System Manager (or any role with `Mamo Pay Payment` write permission)

### Request Body

| Parameter | Type | Required | Description |
|---|---|---|---|
| `payment_name` | string | Yes | Mamo Pay Payment document name (e.g. `MAMO-00001`) |

### Example Request

```bash
curl -X POST https://your-site.com/api/method/frappe_mamopay.api.refund_payment \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_name": "MAMO-00001"
  }'
```

### Success Response (200)

```json
{
  "message": {
    "name": "MAMO-00001",
    "status": "Refund Initiated"
  }
}
```

### Errors

| Code | Reason |
|---|---|
| `403` | User does not have `Mamo Pay Payment` write permission |
| `417` | Payment status is not `Captured`, or Transaction ID not found |

The final refund status (`Refunded` or `Captured` if refund fails) is updated via webhook.

---

## 5. Register Webhook

Registers a new webhook with Mamo Pay to receive event notifications.

**Endpoint:** `POST /api/method/frappe_mamopay.api.register_webhook`

**Auth:** Bearer token (OAuth) or session cookie
**Role:** System Manager (or any role with `Mamo Pay Payment` write permission)

> **Note:** Mamo Pay validates the webhook URL during registration — it must be publicly accessible. For local development, use a tunnel like ngrok.

### Request Body

| Parameter | Type | Required | Description |
|---|---|---|---|
| `url` | string | Yes | The webhook URL that will receive notifications |
| `enabled_events` | array | Yes | List of event types to subscribe to (see available events below) |
| `auth_header` | string | No | Authentication header value (1-50 chars). Set this same value as Webhook Secret in Mamo Pay Settings |

### Available Events

| Event | Description |
|---|---|
| `charge.succeeded` | Payment captured successfully |
| `charge.failed` | Payment failed |
| `charge.authorized` | Payment authorized (not yet captured) |
| `charge.refund_initiated` | Refund process started |
| `charge.refunded` | Refund completed |
| `charge.refund_failed` | Refund failed |
| `charge.card_verified` | Card verification completed |
| `subscription.succeeded` | Subscription payment succeeded |
| `subscription.failed` | Subscription payment failed |
| `payment_link.create` | Payment link created |
| `payout.processed` | Payout processed |
| `payout.failed` | Payout failed |
| `expense.create` | Expense created |
| `expense.update` | Expense updated |
| `card_transaction.create` | Card transaction created |
| `card_transaction.update` | Card transaction updated |

### Example Request

```bash
curl -X POST https://your-site.com/api/method/frappe_mamopay.api.register_webhook \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-site.com/api/method/frappe_mamopay.api.webhook",
    "enabled_events": ["charge.succeeded", "charge.failed", "charge.refunded", "charge.refund_initiated", "charge.refund_failed"],
    "auth_header": "your-webhook-secret"
  }'
```

### Success Response (200)

```json
{
  "message": {
    "id": "MB-WH-D8B07FB8D7",
    "url": "https://your-site.com/api/method/frappe_mamopay.api.webhook",
    "enabled_events": ["charge.succeeded", "charge.failed"],
    "auth_header": "your-webhook-secret"
  }
}
```

### Errors

| Code | Reason |
|---|---|
| `403` | User does not have `Mamo Pay Payment` write permission |
| `422` | Webhook URL is unreachable (Mamo Pay validates the URL) |

---

## 6. List Webhooks

Lists all webhooks registered with Mamo Pay.

**Endpoint:** `POST /api/method/frappe_mamopay.api.list_webhooks`

**Auth:** Bearer token (OAuth) or session cookie
**Role:** System Manager (or any role with `Mamo Pay Payment` write permission)

### Example Request

```bash
curl -X POST https://your-site.com/api/method/frappe_mamopay.api.list_webhooks \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN"
```

### Success Response (200)

```json
{
  "message": [
    {
      "id": "MB-WH-D8B07FB8D7",
      "url": "https://your-site.com/api/method/frappe_mamopay.api.webhook",
      "enabled_events": ["charge.succeeded", "charge.failed"],
      "auth_header": "your-webhook-secret"
    }
  ]
}
```

---

## 7. Update Webhook

Updates an existing webhook's URL, events, or auth header.

**Endpoint:** `POST /api/method/frappe_mamopay.api.update_webhook`

**Auth:** Bearer token (OAuth) or session cookie
**Role:** System Manager (or any role with `Mamo Pay Payment` write permission)

### Request Body

| Parameter | Type | Required | Description |
|---|---|---|---|
| `webhook_id` | string | Yes | Mamo Pay webhook ID (e.g. `MB-WH-D8B07FB8D7`) |
| `url` | string | Yes | Updated webhook URL |
| `enabled_events` | array | Yes | Updated list of event types |
| `auth_header` | string | No | Updated authentication header (1-50 chars) |

### Example Request

```bash
curl -X POST https://your-site.com/api/method/frappe_mamopay.api.update_webhook \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_id": "MB-WH-D8B07FB8D7",
    "url": "https://your-site.com/api/method/frappe_mamopay.api.webhook",
    "enabled_events": ["charge.succeeded", "charge.failed", "charge.refunded"],
    "auth_header": "new-secret"
  }'
```

### Success Response (200)

```json
{
  "message": {
    "id": "MB-WH-D8B07FB8D7",
    "url": "https://your-site.com/api/method/frappe_mamopay.api.webhook",
    "enabled_events": ["charge.succeeded", "charge.failed", "charge.refunded"],
    "auth_header": "new-secret"
  }
}
```

---

## 8. Delete Webhook

Deletes a registered webhook from Mamo Pay.

**Endpoint:** `POST /api/method/frappe_mamopay.api.delete_webhook`

**Auth:** Bearer token (OAuth) or session cookie
**Role:** System Manager (or any role with `Mamo Pay Payment` write permission)

### Request Body

| Parameter | Type | Required | Description |
|---|---|---|---|
| `webhook_id` | string | Yes | Mamo Pay webhook ID to delete |

### Example Request

```bash
curl -X POST https://your-site.com/api/method/frappe_mamopay.api.delete_webhook \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_id": "MB-WH-D8B07FB8D7"
  }'
```

### Success Response (200)

```json
{
  "message": {
    "success": true
  }
}
```

---

## Integration Flow

```
1. Frontend                              Frappe                              Mamo Pay
   |                                       |                                   |
   |-- create_payment_link --------------->|                                   |
   |                                       |-- POST /links ------------------->|
   |                                       |<-- {payment_url, id} -------------|
   |<-- {payment_url, name} ---------------|                                   |
   |                                       |                                   |
   |-- redirect to payment_url ----------->|---------------------------------->|
   |                                       |                     customer pays |
   |<-- redirect to return_url ------------|<----------------------------------|
   |    ?paymentLinkId=...&status=...      |                                   |
   |                                       |                                   |
   |-- verify_payment -------------------->|                                   |
   |                                       |-- GET /links/{id} --------------->|
   |                                       |-- GET /charges/{id} ------------->|
   |                                       |<-- charge details ----------------|
   |<-- {status: "Captured"} --------------|                                   |
   |                                       |                                   |
   |                                       |<-- webhook (charge.succeeded) ----|
   |                                       |-- validate Authorization header   |
   |                                       |-- update status + call hook       |
   |                                       |-- return 200 -------------------->|
```

---

## Permissions Summary

| Endpoint | Access Level |
|---|---|
| `create_payment_link` | Authenticated + `Mamo Pay Payment` write |
| `verify_payment` | Authenticated (any logged-in user) |
| `refund_payment` | Authenticated + `Mamo Pay Payment` write |
| `register_webhook` | Authenticated + `Mamo Pay Payment` write |
| `list_webhooks` | Authenticated + `Mamo Pay Payment` write |
| `update_webhook` | Authenticated + `Mamo Pay Payment` write |
| `delete_webhook` | Authenticated + `Mamo Pay Payment` write |
| `webhook` | Guest (validated by mandatory webhook secret) |

---

## Configuration

Before using the API, configure **Mamo Pay Settings** in Frappe desk:

| Setting | Required | Description |
|---|---|---|
| Enabled | Yes | Must be checked to use the API |
| Sandbox Mode | No | Use Mamo Pay sandbox environment for testing |
| API Key | Yes | Your Mamo Pay API key (Bearer token) |
| Webhook Secret | Yes | Shared secret for webhook verification. Webhooks are rejected without this |
| Default Currency | No | Fallback currency (AED, USD, EUR, GBP, SAR) |
| Success Return URL | No | Default redirect URL after successful payment |
| Failure Return URL | No | Default redirect URL after failed payment |

### Test Cards (Sandbox)

| Card Number | Result |
|---|---|
| `4242 4242 4242 4242` | Success |
| `4659 1055 6905 1157` | Success |
| `4111 1111 1111 1111` | Success |
| `4567 3613 2598 1788` | Failure |
| `4095 2548 0264 2505` | Failure |

**CVV:** `123` | **Expiry:** `01/28` | **3DS Password:** `Checkout1!`
