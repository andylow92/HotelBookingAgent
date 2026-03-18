# Car Rental API — Agent Reference

You are interacting with a **Car Rental API**. It manages a fleet of 16 vehicles across 7 categories, date-range availability, pricing, and rental reservations.

## Authentication

All `/api/*` endpoints require an API key. Provide it via:

- **Header (recommended):** `X-API-Key: <key>`
- **Query parameter:** `?api_key=<key>`

Without a valid key, all API calls return `401`.

## Base URL

- **Behind gateway:** `https://hacketon-18march-api.orcaplatform.ai/<instance>/api/` (e.g. `/car-rental-1/api/`)
- **Standalone:** `/api/` on the host/port where that standalone service is running

## Typical Workflow

1. Call `GET /api/categories` to see vehicle categories with rate ranges
2. Call `GET /api/vehicles/available` with desired dates and optional category to find available vehicles
3. Call `GET /api/pricing` to get a price quote for a specific vehicle and dates
4. Call `POST /api/rentals` to reserve
5. Call `GET /api/rentals` to list reservations
6. Call `DELETE /api/rentals/{id}` to cancel if needed

---

## Vehicle Categories

| Category | Daily Rate Range |
|----------|-----------------|
| economy | $35 – $39 |
| compact | $45 – $49 |
| midsize | $59 – $65 |
| fullsize | $75 – $79 |
| suv | $89 – $99 |
| premium | $129 – $139 |
| luxury | $189 – $199 |

---

## Endpoints

### GET /api/schema

Returns a machine-readable manifest describing all endpoints. No parameters.

### GET /api/health

Returns `{"status": "ok"}`.

---

### GET /api/categories

List all vehicle categories with their rate ranges.

**Response:** `200 OK`

```json
[
  {
    "category": "economy",
    "vehicle_count": 2,
    "min_daily_rate": 35.0,
    "max_daily_rate": 39.0
  }
]
```

---

### GET /api/vehicles

List all vehicles in the fleet.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| category | string | No | One of: `economy`, `compact`, `midsize`, `fullsize`, `suv`, `premium`, `luxury` |
| seats | integer (>= 1) | No | Minimum number of seats |

**Response:** `200 OK` — Array of vehicle objects

```json
[
  {
    "id": 1,
    "plate_number": "ECO-001",
    "make": "Toyota",
    "model": "Yaris",
    "year": 2024,
    "category": "economy",
    "seats": 5,
    "daily_rate": 35.0,
    "status": "available"
  }
]
```

**Errors:**
- `400` — Invalid category

---

### GET /api/vehicles/available

Find vehicles available for a date range.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| pickup_date | date (YYYY-MM-DD) | Yes | Pickup date |
| return_date | date (YYYY-MM-DD) | Yes | Return date (must be after pickup_date) |
| category | string | No | Filter by category |
| seats | integer (>= 1) | No | Minimum number of seats |

**Response:** `200 OK` — Array of available vehicle objects (same shape as `/api/vehicles` plus `"available": true`)

**Errors:**
- `400` — `return_date` not after `pickup_date`, or invalid category

---

### GET /api/vehicles/{id}

Get details of a specific vehicle.

**Response:** `200 OK` — Vehicle object

**Errors:**
- `404` — Vehicle not found

---

### GET /api/pricing

Get a price quote for a vehicle and date range.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| vehicle_id | integer | Yes | Vehicle ID |
| pickup_date | date (YYYY-MM-DD) | Yes | Pickup date |
| return_date | date (YYYY-MM-DD) | Yes | Return date |

**Pricing rule:** `total_price = daily_rate * number_of_days`

**Response:** `200 OK`

```json
{
  "vehicle_id": 1,
  "plate_number": "ECO-001",
  "make": "Toyota",
  "model": "Yaris",
  "category": "economy",
  "daily_rate": 35.0,
  "pickup_date": "2026-03-10",
  "return_date": "2026-03-12",
  "num_days": 2,
  "total_price": 70.0
}
```

**Errors:**
- `400` — `return_date` not after `pickup_date`
- `404` — Vehicle not found

---

### POST /api/rentals

Create a new rental reservation.

**Request body (JSON):**

```json
{
  "vehicle_id": 1,
  "customer_name": "Jane Doe",
  "customer_email": "jane@example.com",
  "pickup_date": "2026-03-10",
  "return_date": "2026-03-12"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| vehicle_id | integer | Yes | Vehicle ID |
| customer_name | string | Yes | Customer's full name |
| customer_email | string | Yes | Customer's email |
| pickup_date | date (YYYY-MM-DD) | Yes | Pickup date |
| return_date | date (YYYY-MM-DD) | Yes | Return date |

**Response:** `201 Created`

```json
{
  "id": 1,
  "vehicle_id": 1,
  "plate_number": "ECO-001",
  "make": "Toyota",
  "model": "Yaris",
  "category": "economy",
  "customer_name": "Jane Doe",
  "customer_email": "jane@example.com",
  "pickup_date": "2026-03-10",
  "return_date": "2026-03-12",
  "total_price": 70.0,
  "status": "confirmed",
  "created_at": "2026-03-07T12:00:00"
}
```

**Errors:**
- `400` — `return_date` not after `pickup_date`, or vehicle under maintenance
- `404` — Vehicle not found
- `409` — Vehicle not available for the requested dates

---

### GET /api/rentals

List all rentals.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| status | string | No | Filter by status: `confirmed`, `cancelled`, or `completed` |

**Response:** `200 OK` — Array of rental objects (same shape as POST response)

---

### GET /api/rentals/{id}

Get a single rental by ID.

**Response:** `200 OK` — Rental object

**Errors:**
- `404` — Rental not found

---

### DELETE /api/rentals/{id}

Cancel a rental. Sets status to `cancelled`.

**Response:** `200 OK` — Updated rental object with `"status": "cancelled"`

**Errors:**
- `400` — Rental is already cancelled
- `404` — Rental not found

---

## Seed Data (Vehicle Fleet)

| ID | Plate | Make | Model | Year | Category | Seats | Daily Rate |
|----|-------|------|-------|------|----------|-------|-----------|
| 1 | ECO-001 | Toyota | Yaris | 2024 | economy | 5 | $35 |
| 2 | ECO-002 | Nissan | Versa | 2024 | economy | 5 | $39 |
| 3 | CMP-001 | Honda | Civic | 2025 | compact | 5 | $45 |
| 4 | CMP-002 | Toyota | Corolla | 2025 | compact | 5 | $49 |
| 5 | MID-001 | Honda | Accord | 2025 | midsize | 5 | $59 |
| 6 | MID-002 | Toyota | Camry | 2025 | midsize | 5 | $65 |
| 7 | FUL-001 | Chevrolet | Impala | 2024 | fullsize | 5 | $75 |
| 8 | FUL-002 | Ford | Taurus | 2024 | fullsize | 5 | $79 |
| 9 | SUV-001 | Toyota | RAV4 | 2025 | suv | 5 | $89 |
| 10 | SUV-002 | Ford | Explorer | 2025 | suv | 7 | $99 |
| 11 | SUV-003 | Jeep | Grand Cherokee | 2024 | suv | 5 | $95 |
| 12 | PRE-001 | BMW | 3 Series | 2025 | premium | 5 | $129 |
| 13 | PRE-002 | Audi | A4 | 2025 | premium | 5 | $139 |
| 14 | PRE-003 | Mercedes | C-Class | 2025 | premium | 5 | $135 |
| 15 | LUX-001 | Mercedes | S-Class | 2025 | luxury | 5 | $199 |
| 16 | LUX-002 | BMW | 7 Series | 2025 | luxury | 5 | $189 |

## Error Response Format

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP status codes: `400` (bad request), `401` (unauthorized), `404` (not found), `409` (conflict).
