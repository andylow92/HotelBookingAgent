# Tour Guide Booking API — Agent Reference

You are interacting with a **Tour Guide Booking API**. It manages 12 guided tours across 6 categories, date-based availability with group size limits, pricing, and bookings.

## Authentication

All `/api/*` endpoints require an API key. Provide it via:

- **Header (recommended):** `X-API-Key: <key>`
- **Query parameter:** `?api_key=<key>`

Without a valid key, all API calls return `401`.

## Base URL

- **Behind gateway:** `https://hacketon-18march-api.orcaplatform.ai/<instance>/api/` (e.g. `/tour-guide-1/api/`)
- **Standalone:** `/api/` on the host/port where that standalone service is running

## Typical Workflow

1. Call `GET /api/categories` to see tour categories
2. Call `GET /api/tours` to browse tours, optionally filtering by category, difficulty, price, or location
3. Call `GET /api/tours/available` to check remaining spots on a specific tour and date
4. Call `GET /api/pricing` to get a price quote
5. Call `POST /api/bookings` to book
6. Call `GET /api/bookings` to list bookings
7. Call `DELETE /api/bookings/{id}` to cancel if needed

---

## Tour Categories

`cultural`, `adventure`, `food`, `nature`, `nightlife`, `historical`

## Difficulty Levels

`easy`, `moderate`, `challenging`

---

## Endpoints

### GET /api/schema

Returns a machine-readable manifest describing all endpoints. No parameters.

### GET /api/health

Returns `{"status": "ok"}`.

---

### GET /api/categories

List tour categories with tour counts.

**Response:** `200 OK`

```json
[
  {"category": "cultural", "tour_count": 2},
  {"category": "adventure", "tour_count": 2}
]
```

---

### GET /api/tours

List all tours, optionally filtered.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| category | string | No | One of: `cultural`, `adventure`, `food`, `nature`, `nightlife`, `historical` |
| difficulty | string | No | One of: `easy`, `moderate`, `challenging` |
| max_price | number | No | Maximum price per person |
| location | string | No | Partial match on location name |

**Response:** `200 OK` — Array of tour objects

```json
[
  {
    "id": 1,
    "name": "Old City Walking Tour",
    "description": "Explore centuries-old streets, markets, and hidden courtyards with a local historian.",
    "category": "cultural",
    "difficulty": "easy",
    "duration_hours": 3.0,
    "max_group_size": 20,
    "price_per_person": 45.0,
    "location": "Old Town",
    "status": "active"
  }
]
```

**Errors:**
- `400` — Invalid category or difficulty

---

### GET /api/tours/{id}

Get details of a specific tour.

**Response:** `200 OK` — Tour object

**Errors:**
- `404` — Tour not found

---

### GET /api/tours/available

Check availability for a tour on a specific date.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| tour_id | integer | Yes | Tour ID |
| date | date (YYYY-MM-DD) | Yes | Date to check |
| guests | integer (>= 1) | No | Check if this many spots are available |

**Response:** `200 OK`

```json
{
  "tour_id": 1,
  "tour_name": "Old City Walking Tour",
  "date": "2026-03-10",
  "max_group_size": 20,
  "booked_spots": 5,
  "remaining_spots": 15,
  "available": true
}
```

**Errors:**
- `404` — Tour not found

---

### GET /api/pricing

Get a price quote.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| tour_id | integer | Yes | Tour ID |
| guests | integer (>= 1) | No | Number of guests (default: 1) |

**Pricing rule:** `total_price = price_per_person * num_guests`

**Response:** `200 OK`

```json
{
  "tour_id": 1,
  "tour_name": "Old City Walking Tour",
  "category": "cultural",
  "price_per_person": 45.0,
  "num_guests": 3,
  "total_price": 135.0
}
```

**Errors:**
- `404` — Tour not found

---

### POST /api/bookings

Create a new booking for a tour on a specific date.

**Request body (JSON):**

```json
{
  "tour_id": 1,
  "tour_date": "2026-03-10",
  "guest_name": "Jane Doe",
  "guest_email": "jane@example.com",
  "num_guests": 3
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tour_id | integer | Yes | Tour ID |
| tour_date | date (YYYY-MM-DD) | Yes | Date for the tour |
| guest_name | string | Yes | Guest's full name |
| guest_email | string | Yes | Guest's email |
| num_guests | integer (>= 1) | Yes | Number of guests |

**Response:** `201 Created`

```json
{
  "id": 1,
  "tour_id": 1,
  "tour_name": "Old City Walking Tour",
  "tour_category": "cultural",
  "tour_date": "2026-03-10",
  "guest_name": "Jane Doe",
  "guest_email": "jane@example.com",
  "num_guests": 3,
  "total_price": 135.0,
  "status": "confirmed",
  "created_at": "2026-03-07T12:00:00"
}
```

**Errors:**
- `400` — Tour is not active
- `404` — Tour not found
- `409` — Not enough remaining spots for the requested number of guests

---

### GET /api/bookings

List all bookings.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| status | string | No | Filter by status: `confirmed` or `cancelled` |
| date | date (YYYY-MM-DD) | No | Filter by tour date |

**Response:** `200 OK` — Array of booking objects (same shape as POST response)

---

### GET /api/bookings/{id}

Get a single booking by ID.

**Response:** `200 OK` — Booking object

**Errors:**
- `404` — Booking not found

---

### DELETE /api/bookings/{id}

Cancel a booking. Sets status to `cancelled`.

**Response:** `200 OK` — Updated booking object with `"status": "cancelled"`

**Errors:**
- `400` — Booking is already cancelled
- `404` — Booking not found

---

## Seed Data (Available Tours)

| ID | Name | Category | Difficulty | Duration | Max Group | Price/Person | Location |
|----|------|----------|------------|----------|-----------|-------------|----------|
| 1 | Old City Walking Tour | cultural | easy | 3h | 20 | $45 | Old Town |
| 2 | Art Gallery Crawl | cultural | easy | 2.5h | 15 | $65 | Arts District |
| 3 | Mountain Hiking Trail | adventure | challenging | 6h | 12 | $89 | Mountain Range |
| 4 | Kayaking River Tour | adventure | moderate | 4h | 10 | $75 | River Valley |
| 5 | Street Food Tasting | food | easy | 3h | 15 | $55 | Market Quarter |
| 6 | Wine & Cheese Tour | food | easy | 2.5h | 12 | $95 | Wine Country |
| 7 | Sunset Safari Drive | nature | easy | 5h | 8 | $120 | National Park |
| 8 | Botanical Garden Walk | nature | easy | 2h | 20 | $35 | City Gardens |
| 9 | Rooftop Bar Hopping | nightlife | easy | 4h | 16 | $70 | Downtown |
| 10 | Live Jazz Night | nightlife | easy | 3h | 14 | $60 | Jazz Quarter |
| 11 | Ancient Ruins Expedition | historical | moderate | 5h | 15 | $85 | Ancient Site |
| 12 | War Memorial Tour | historical | easy | 2.5h | 20 | $40 | Memorial District |

## Error Response Format

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP status codes: `400` (bad request), `401` (unauthorized), `404` (not found), `409` (conflict).
