# Frappe Mamo Pay - API Documentation

Base URL: `https://your-site.com`

All authenticated endpoints require a Frappe OAuth Bearer token in the `Authorization` header.

---

## 1. Create Payment Link

Creates a Mamo Pay payment link and returns the URL to redirect the customer.

**Endpoint:** `POST /api/method/frappe_mamopay.api.create_payment_link`

**Auth:** Bearer token (OAuth)

### Request Body

| Parameter | Type | Required | Description |
|---|---|---|---|
| `title` | string | Yes | Payment link title (1-50 chars) |
| `amount` | number | Yes | Payment amount (min 2) |
| `amount_currency` | string | No | Currency code. Options: `AED`, `USD`, `EUR`, `GBP`, `SAR`. Defaults to value in Mamo Pay Settings |
| `description` | string | No | Payment description shown at checkout (max 75 chars) |
| `reference_doctype` | string | No | Frappe DocType to link this payment to (e.g. `Sales Order`) |
| `reference_name` | string | No | Document name of the reference DocType |
| `customer_email` | string | No | Customer email (pre-fills checkout) |
| `customer_name` | string | No | Customer full name (auto-split into first/last name) |
| `return_url` | string | No | Redirect URL after successful payment. Defaults to value in Mamo Pay Settings |
| `failure_return_url` | string | No | Redirect URL after failed payment. Defaults to value in Mamo Pay Settings |
| `custom_data` | object | No | Key-value pairs for custom metadata |

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

**Auth:** Bearer token (OAuth)

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

**Auth:** None (guest access). Validated via `Authorization` header matching the webhook secret configured in Mamo Pay Settings.

### Setup

1. Set a **Webhook Secret** in Mamo Pay Settings (Frappe desk)
2. Register this webhook URL with Mamo Pay using their API or dashboard, with the same secret as the `auth_header`

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

Initiates a refund for a captured payment.

**Endpoint:** `POST /api/method/frappe_mamopay.api.refund_payment`

**Auth:** Bearer token (OAuth)

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

- `400` — Payment status is not `Captured`
- `400` — Transaction ID not found on the payment record

The final refund status (`Refunded` or `Captured` if refund fails) is updated via webhook.

---

## 5. Register Webhook

Registers a new webhook with Mamo Pay to receive event notifications.

**Endpoint:** `POST /api/method/frappe_mamopay.api.register_webhook`

**Auth:** Bearer token (OAuth)

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

---

## 6. List Webhooks

Lists all webhooks registered with Mamo Pay.

**Endpoint:** `POST /api/method/frappe_mamopay.api.list_webhooks`

**Auth:** Bearer token (OAuth)

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

**Auth:** Bearer token (OAuth)

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

**Auth:** Bearer token (OAuth)

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

## Integration Flow (Next.js Example)

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
   |                                       |-- update status + call hook       |
   |                                       |-- return 200 -------------------->|
```

---

## Configuration

Before using the API, configure **Mamo Pay Settings** in Frappe desk:

| Setting | Description |
|---|---|
| Enabled | Must be checked to use the API |
| Sandbox Mode | Use Mamo Pay sandbox environment for testing |
| API Key | Your Mamo Pay API key (Bearer token) |
| Webhook Secret | Shared secret for webhook verification |
| Default Currency | Fallback currency (AED, USD, EUR, GBP, SAR) |
| Success Return URL | Default redirect URL after successful payment |
| Failure Return URL | Default redirect URL after failed payment |

### Test Cards (Sandbox)

| Card Number | Result |
|---|---|
| `4242 4242 4242 4242` | Success |
| `4659 1055 6905 1157` | Success |
| `4111 1111 1111 1111` | Success |
| `4567 3613 2598 1788` | Failure |
| `4095 2548 0264 2505` | Failure |

**CVV:** `123` | **Expiry:** `01/28` | **3DS Password:** `Checkout1!`
