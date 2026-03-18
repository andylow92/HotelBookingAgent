# Hotel Reservation API — Agent Reference

You are interacting with a **Hotel Reservation API**. It manages rooms, availability, pricing, and reservations for a 10-room hotel.

## Authentication

All `/api/*` endpoints require an API key. Provide it via:

- **Header (recommended):** `X-API-Key: <key>`
- **Query parameter:** `?api_key=<key>`

Without a valid key, all API calls return `401`.

The API key is set per instance in the deployment. Check `docker-compose.yml` or ask the operator for your key.

## Base URL

- **Behind gateway:** `https://hacketon-18march-api.orcaplatform.ai/<instance>/api/` (e.g. `/hotel-1/api/`, `/hotel-2/api/`)
- **Standalone:** `/api/` on the host/port where that standalone service is running

All endpoint paths below are relative to the base URL.

## Typical Workflow

1. Call `GET /api/rooms` to see all rooms
2. Call `GET /api/rooms/available` with desired dates and guest count to find available rooms
3. Call `GET /api/pricing` to get a price quote for a specific room and dates
4. Call `POST /api/reservations` to book
5. Call `GET /api/reservations` to list bookings
6. Call `DELETE /api/reservations/{id}` to cancel if needed

---

## Endpoints

### GET /api/schema

Returns a machine-readable manifest describing all endpoints. No parameters.

### GET /api/health

Returns `{"status": "ok"}`.

---

### GET /api/rooms

List all hotel rooms.

**Parameters:** None

**Response:** `200 OK` — Array of room objects

```json
[
  {
    "id": 1,
    "room_number": "101",
    "room_type": "single",
    "capacity": 1,
    "base_price_per_night": 89.0
  }
]
```

**Room types:** `single`, `double`, `suite`

---

### GET /api/rooms/available

Find rooms available for a date range.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| check_in | date (YYYY-MM-DD) | Yes | Check-in date |
| check_out | date (YYYY-MM-DD) | Yes | Check-out date (must be after check_in) |
| guests | integer (>= 1) | No | Filter rooms with at least this capacity |

**Response:** `200 OK` — Array of available room objects (same shape as `/api/rooms` plus `"available": true`)

**Errors:**
- `400` — `check_out` is not after `check_in`

---

### GET /api/pricing

Get a detailed price quote for a room and date range.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| room_id | integer | Yes | Room ID |
| check_in | date (YYYY-MM-DD) | Yes | Check-in date |
| check_out | date (YYYY-MM-DD) | Yes | Check-out date |

**Pricing rules:**
- Base price is per night
- **Weekend surcharge:** Friday and Saturday nights cost **1.2x** the base price

**Response:** `200 OK`

```json
{
  "room_id": 3,
  "room_number": "201",
  "room_type": "double",
  "check_in": "2026-03-10",
  "check_out": "2026-03-12",
  "num_nights": 2,
  "base_price_per_night": 129.0,
  "total_price": 258.0,
  "breakdown": [
    {
      "date": "2026-03-10",
      "day": "Tuesday",
      "price": 129.0,
      "surcharge": false
    },
    {
      "date": "2026-03-11",
      "day": "Wednesday",
      "price": 129.0,
      "surcharge": false
    }
  ]
}
```

**Errors:**
- `400` — `check_out` not after `check_in`
- `404` — Room not found

---

### POST /api/reservations

Create a new reservation.

**Request body (JSON):**

```json
{
  "room_id": 3,
  "guest_name": "Jane Doe",
  "guest_email": "jane@example.com",
  "check_in": "2026-03-10",
  "check_out": "2026-03-12",
  "num_guests": 2
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| room_id | integer | Yes | ID of the room to book |
| guest_name | string | Yes | Guest's full name |
| guest_email | string | Yes | Guest's email address |
| check_in | date (YYYY-MM-DD) | Yes | Check-in date |
| check_out | date (YYYY-MM-DD) | Yes | Check-out date |
| num_guests | integer (>= 1) | Yes | Number of guests |

**Response:** `201 Created`

```json
{
  "id": 1,
  "room_id": 3,
  "room_number": "201",
  "guest_name": "Jane Doe",
  "guest_email": "jane@example.com",
  "check_in": "2026-03-10",
  "check_out": "2026-03-12",
  "num_guests": 2,
  "total_price": 258.0,
  "status": "confirmed",
  "created_at": "2026-03-07T12:00:00"
}
```

**Errors:**
- `400` — `check_out` not after `check_in`, or `num_guests` exceeds room capacity
- `404` — Room not found
- `409` — Room not available for the requested dates

---

### GET /api/reservations

List all reservations.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
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

## Seed Data (Available Rooms)

| ID | Room # | Type | Capacity | Base Price/Night |
|----|--------|------|----------|------------------|
| 1 | 101 | single | 1 | $89 |
| 2 | 102 | single | 1 | $89 |
| 3 | 201 | double | 2 | $129 |
| 4 | 202 | double | 2 | $129 |
| 5 | 203 | double | 3 | $149 |
| 6 | 301 | double | 2 | $139 |
| 7 | 302 | double | 4 | $169 |
| 8 | 401 | suite | 4 | $249 |
| 9 | 402 | suite | 3 | $229 |
| 10 | 501 | suite | 6 | $349 |

## Error Response Format

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP status codes: `400` (bad request), `401` (unauthorized), `404` (not found), `409` (conflict).
