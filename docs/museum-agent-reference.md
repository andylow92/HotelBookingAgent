# Museum Ticket Booking API — Agent Reference

You are interacting with a **Museum Ticket Booking API**. It manages timed-entry tickets across 4 daily time slots, with visitor capacity limits, multiple ticket types, and booking management.

## Authentication

All `/api/*` endpoints require an API key. Provide it via:

- **Header (recommended):** `X-API-Key: <key>`
- **Query parameter:** `?api_key=<key>`

Without a valid key, all API calls return `401`.

## Base URL

- **Behind gateway:** `https://hacketon-18march-api.orcaplatform.ai/<instance>/api/` (e.g. `/museum-1/api/`)
- **Standalone:** `/api/` on the host/port where that standalone service is running

## Typical Workflow

1. Call `GET /api/time-slots` to see available entry windows
2. Call `GET /api/ticket-types` to see ticket types and prices
3. Call `GET /api/availability` with a date to check remaining spots per slot
4. Call `GET /api/pricing` to get a price quote for a ticket type and number of visitors
5. Call `POST /api/tickets` to book
6. Call `GET /api/tickets` to list bookings
7. Call `DELETE /api/tickets/{id}` to cancel if needed

---

## Time Slots

| ID | Window | Capacity |
|----|--------|----------|
| 1 | 09:00 – 11:00 | 50 visitors |
| 2 | 11:00 – 13:00 | 50 visitors |
| 3 | 13:00 – 15:00 | 50 visitors |
| 4 | 15:00 – 17:00 | 50 visitors |

## Ticket Types & Prices

| Type | Price per Person |
|------|-----------------|
| adult | $25.00 |
| child | $12.00 |
| senior | $18.00 |
| student | $15.00 |

---

## Endpoints

### GET /api/schema

Returns a machine-readable manifest describing all endpoints. No parameters.

### GET /api/health

Returns `{"status": "ok"}`.

---

### GET /api/time-slots

List all time slots with their capacity.

**Response:** `200 OK` — Array of time slot objects

```json
[
  {
    "id": 1,
    "label": "09:00-11:00",
    "start_time": "09:00",
    "end_time": "11:00",
    "max_visitors": 50
  }
]
```

---

### GET /api/ticket-types

List all ticket types with prices.

**Response:** `200 OK`

```json
[
  {"type": "adult", "price_per_person": 25.0},
  {"type": "child", "price_per_person": 12.0},
  {"type": "senior", "price_per_person": 18.0},
  {"type": "student", "price_per_person": 15.0}
]
```

---

### GET /api/availability

Check visitor availability for a date. Returns remaining spots per time slot.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| date | date (YYYY-MM-DD) | Yes | Date to check |
| time_slot_id | integer | No | Check a specific slot only (returns single object instead of array) |
| visitors | integer (>= 1) | No | Check if this many spots are available |

**Response (all slots):** `200 OK` — Array of availability objects

```json
[
  {
    "time_slot_id": 1,
    "label": "09:00-11:00",
    "start_time": "09:00",
    "end_time": "11:00",
    "max_visitors": 50,
    "booked_visitors": 10,
    "remaining_spots": 40,
    "available": true
  }
]
```

**Response (single slot with `time_slot_id`):** `200 OK` — Single availability object (not an array)

**Errors:**
- `404` — Time slot not found (when `time_slot_id` is provided)

---

### GET /api/pricing

Get a price quote.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| ticket_type | string | No | One of: `adult` (default), `child`, `senior`, `student` |
| visitors | integer (>= 1) | No | Number of visitors (default: 1) |

**Pricing rule:** `total_price = price_per_person * num_visitors`

**Response:** `200 OK`

```json
{
  "ticket_type": "adult",
  "price_per_person": 25.0,
  "num_visitors": 2,
  "total_price": 50.0
}
```

**Errors:**
- `400` — Invalid ticket type

---

### POST /api/tickets

Book museum tickets.

**Request body (JSON):**

```json
{
  "time_slot_id": 1,
  "visit_date": "2026-03-10",
  "visitor_name": "Jane Doe",
  "visitor_email": "jane@example.com",
  "num_visitors": 2,
  "ticket_type": "adult"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| time_slot_id | integer | Yes | Time slot ID (1–4) |
| visit_date | date (YYYY-MM-DD) | Yes | Date of visit |
| visitor_name | string | Yes | Visitor's full name |
| visitor_email | string | Yes | Visitor's email |
| num_visitors | integer (>= 1) | Yes | Number of visitors |
| ticket_type | string | No | One of: `adult` (default), `child`, `senior`, `student` |

**Response:** `201 Created`

```json
{
  "id": 1,
  "time_slot_id": 1,
  "time_slot_label": "09:00-11:00",
  "visit_date": "2026-03-10",
  "visitor_name": "Jane Doe",
  "visitor_email": "jane@example.com",
  "num_visitors": 2,
  "ticket_type": "adult",
  "total_price": 50.0,
  "status": "confirmed",
  "created_at": "2026-03-07T12:00:00"
}
```

**Errors:**
- `400` — Invalid ticket type
- `404` — Time slot not found
- `409` — Not enough remaining spots for the requested number of visitors

---

### GET /api/tickets

List all tickets.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| date | date (YYYY-MM-DD) | No | Filter by visit date |
| status | string | No | Filter by status: `confirmed` or `cancelled` |

**Response:** `200 OK` — Array of ticket objects (same shape as POST response)

---

### GET /api/tickets/{id}

Get a single ticket by ID.

**Response:** `200 OK` — Ticket object

**Errors:**
- `404` — Ticket not found

---

### DELETE /api/tickets/{id}

Cancel a ticket. Sets status to `cancelled` and frees up the spots.

**Response:** `200 OK` — Updated ticket object with `"status": "cancelled"`

**Errors:**
- `400` — Ticket is already cancelled
- `404` — Ticket not found

---

## Error Response Format

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP status codes: `400` (bad request), `401` (unauthorized), `404` (not found), `409` (conflict).
