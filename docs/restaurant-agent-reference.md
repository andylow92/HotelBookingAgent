# Restaurant Reservation API — Agent Reference

You are interacting with a **Restaurant Reservation API**. It manages tables, time-slot-based availability, and reservations for a 12-table restaurant.

## Authentication

All `/api/*` endpoints require an API key. Provide it via:

- **Header (recommended):** `X-API-Key: <key>`
- **Query parameter:** `?api_key=<key>`

Without a valid key, all API calls return `401`.

## Base URL

- **Behind gateway:** `https://hacketon-18march-api.orcaplatform.ai/<instance>/api/` (e.g. `/restaurant-1/api/`)
- **Standalone:** `/api/` on the host/port where that standalone service is running

## Typical Workflow

1. Call `GET /api/time-slots` to see valid reservation times
2. Call `GET /api/tables` to see all tables with their capacity and location
3. Call `GET /api/tables/available` with a date, time slot, and party size to find available tables
4. Call `POST /api/reservations` to book a table
5. Call `GET /api/reservations` to list bookings
6. Call `DELETE /api/reservations/{id}` to cancel if needed

---

## Endpoints

### GET /api/schema

Returns a machine-readable manifest describing all endpoints. No parameters.

### GET /api/health

Returns `{"status": "ok"}`.

---

### GET /api/time-slots

List all valid reservation time slots.

**Response:** `200 OK`

```json
{
  "time_slots": ["11:00", "12:30", "14:00", "18:00", "19:30", "21:00"],
  "note": "Each slot is a 1.5-hour dining window."
}
```

**Valid time slots:** `11:00`, `12:30`, `14:00`, `18:00`, `19:30`, `21:00`

---

### GET /api/tables

List all restaurant tables.

**Response:** `200 OK` — Array of table objects

```json
[
  {
    "id": 1,
    "table_number": "T1",
    "capacity": 2,
    "location": "indoor"
  }
]
```

**Locations:** `indoor`, `outdoor`, `patio`, `bar`

---

### GET /api/tables/available

Find tables available for a specific date and time slot.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| date | date (YYYY-MM-DD) | Yes | Reservation date |
| time_slot | string (HH:MM) | Yes | Must be one of: `11:00`, `12:30`, `14:00`, `18:00`, `19:30`, `21:00` |
| party_size | integer (>= 1) | No | Filter tables with at least this capacity |

**Response:** `200 OK` — Array of available table objects (same shape as `/api/tables` plus `"available": true`)

**Errors:**
- `400` — Invalid time slot

---

### POST /api/reservations

Create a new reservation.

**Request body (JSON):**

```json
{
  "table_id": 3,
  "guest_name": "Jane Doe",
  "guest_email": "jane@example.com",
  "date": "2026-03-10",
  "time_slot": "19:30",
  "party_size": 4,
  "special_requests": "Window seat preferred"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| table_id | integer | Yes | ID of the table to book |
| guest_name | string | Yes | Guest's full name |
| guest_email | string | Yes | Guest's email address |
| date | date (YYYY-MM-DD) | Yes | Reservation date |
| time_slot | string (HH:MM) | Yes | Must be a valid time slot |
| party_size | integer (>= 1) | Yes | Number of guests |
| special_requests | string | No | Optional special requests (defaults to empty string) |

**Response:** `201 Created`

```json
{
  "id": 1,
  "table_id": 3,
  "table_number": "T3",
  "location": "indoor",
  "guest_name": "Jane Doe",
  "guest_email": "jane@example.com",
  "date": "2026-03-10",
  "time_slot": "19:30",
  "party_size": 4,
  "special_requests": "Window seat preferred",
  "status": "confirmed",
  "created_at": "2026-03-07T12:00:00"
}
```

**Errors:**
- `400` — Invalid time slot, or party size exceeds table capacity
- `404` — Table not found
- `409` — Table already reserved for that date and time slot

---

### GET /api/reservations

List all reservations.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| date | date (YYYY-MM-DD) | No | Filter by reservation date |
| status | string | No | Filter by status: `confirmed` or `cancelled` |

**Response:** `200 OK` — Array of reservation objects (same shape as POST response)

---

### GET /api/reservations/{id}

Get a single reservation by ID.

**Response:** `200 OK` — Reservation object

**Errors:**
- `404` — Reservation not found

---

### DELETE /api/reservations/{id}

Cancel a reservation. Sets status to `cancelled`.

**Response:** `200 OK` — Updated reservation object with `"status": "cancelled"`

**Errors:**
- `400` — Reservation is already cancelled
- `404` — Reservation not found

---

## Seed Data (Available Tables)

| ID | Table # | Capacity | Location |
|----|---------|----------|----------|
| 1 | T1 | 2 | indoor |
| 2 | T2 | 2 | indoor |
| 3 | T3 | 4 | indoor |
| 4 | T4 | 4 | indoor |
| 5 | T5 | 6 | indoor |
| 6 | T6 | 2 | bar |
| 7 | T7 | 2 | bar |
| 8 | T8 | 4 | patio |
| 9 | T9 | 4 | patio |
| 10 | T10 | 6 | patio |
| 11 | T11 | 4 | outdoor |
| 12 | T12 | 8 | outdoor |

## Error Response Format

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP status codes: `400` (bad request), `401` (unauthorized), `404` (not found), `409` (conflict).
