import logging
import requests
from typing import Optional, Dict, Any, List
from orca import create_agent_app, ChatMessage, OrcaHandler, Variables
import anthropic

logger = logging.getLogger(__name__)

class BaseAPI:
    """Base API Wrapper for all Agents"""
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {"X-API-Key": self.api_key}

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_schema(self) -> Dict[str, Any]:
        """Returns API schema"""
        return self._request("GET", "api/schema")

    def get_health(self) -> Dict[str, Any]:
        """Returns health status"""
        return self._request("GET", "api/health")

class HotelAPI(BaseAPI):
    """Wrapper for the Hotel Reservation API"""
    def get_rooms(self) -> List[Dict[str, Any]]:
        """List all hotel rooms."""
        return self._request("GET", "api/rooms")

    def get_available_rooms(self, check_in: str, check_out: str, guests: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find rooms available for a date range."""
        params = {"check_in": check_in, "check_out": check_out}
        if guests is not None:
            params["guests"] = guests
        return self._request("GET", "api/rooms/available", params=params)

    def get_pricing(self, room_id: int, check_in: str, check_out: str) -> Dict[str, Any]:
        """Get a detailed price quote for a room and date range."""
        params = {"room_id": room_id, "check_in": check_in, "check_out": check_out}
        return self._request("GET", "api/pricing", params=params)

    def create_reservation(self, room_id: int, guest_name: str, guest_email: str, check_in: str, check_out: str, num_guests: int) -> Dict[str, Any]:
        """Create a new reservation."""
        payload = {
            "room_id": room_id,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "check_in": check_in,
            "check_out": check_out,
            "num_guests": num_guests
        }
        return self._request("POST", "api/reservations", json=payload)

    def get_reservations(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all reservations."""
        params = {}
        if status:
            params["status"] = status
        return self._request("GET", "api/reservations", params=params)

    def get_reservation(self, reservation_id: int) -> Dict[str, Any]:
        """Get a single reservation by ID."""
        return self._request("GET", f"api/reservations/{reservation_id}")

    def cancel_reservation(self, reservation_id: int) -> Dict[str, Any]:
        """Cancel a reservation."""
        return self._request("DELETE", f"api/reservations/{reservation_id}")

class CarRentalAPI(BaseAPI):
    """Wrapper for the Car Rental API"""
    def get_categories(self) -> List[Dict[str, Any]]:
        return self._request("GET", "api/categories")

    def get_vehicles(self, category: Optional[str] = None, seats: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {}
        if category: params["category"] = category
        if seats is not None: params["seats"] = seats
        return self._request("GET", "api/vehicles", params=params)

    def get_available_vehicles(self, pickup_date: str, return_date: str, category: Optional[str] = None, seats: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"pickup_date": pickup_date, "return_date": return_date}
        if category: params["category"] = category
        if seats is not None: params["seats"] = seats
        return self._request("GET", "api/vehicles/available", params=params)
        
    def get_vehicle(self, vehicle_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/vehicles/{vehicle_id}")

    def get_pricing(self, vehicle_id: int, pickup_date: str, return_date: str) -> Dict[str, Any]:
        params = {"vehicle_id": vehicle_id, "pickup_date": pickup_date, "return_date": return_date}
        return self._request("GET", "api/pricing", params=params)

    def create_rental(self, vehicle_id: int, customer_name: str, customer_email: str, pickup_date: str, return_date: str) -> Dict[str, Any]:
        payload = {
            "vehicle_id": vehicle_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "pickup_date": pickup_date,
            "return_date": return_date
        }
        return self._request("POST", "api/rentals", json=payload)

    def get_rentals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if status: params["status"] = status
        return self._request("GET", "api/rentals", params=params)

    def get_rental(self, rental_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/rentals/{rental_id}")

    def cancel_rental(self, rental_id: int) -> Dict[str, Any]:
        return self._request("DELETE", f"api/rentals/{rental_id}")

class FlightAPI(BaseAPI):
    """Wrapper for the Flight Reservation API"""
    def get_destinations(self) -> Dict[str, Any]:
        return self._request("GET", "api/destinations")

    def get_flights(self, origin: Optional[str] = None, destination: Optional[str] = None, date: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if origin: params["origin"] = origin
        if destination: params["destination"] = destination
        if date: params["date"] = date
        return self._request("GET", "api/flights", params=params)

    def search_flights(self, origin: str, destination: str, date: Optional[str] = None, passengers: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"origin": origin, "destination": destination}
        if date: params["date"] = date
        if passengers is not None: params["passengers"] = passengers
        return self._request("GET", "api/flights/search", params=params)
        
    def get_flight(self, flight_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/flights/{flight_id}")

    def get_pricing(self, flight_id: int, seat_class: Optional[str] = None, passengers: Optional[int] = None) -> Dict[str, Any]:
        params = {"flight_id": flight_id}
        if seat_class: params["seat_class"] = seat_class
        if passengers is not None: params["passengers"] = passengers
        return self._request("GET", "api/pricing", params=params)

    def create_booking(self, flight_id: int, passenger_name: str, passenger_email: str, num_passengers: int, seat_class: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "flight_id": flight_id,
            "passenger_name": passenger_name,
            "passenger_email": passenger_email,
            "num_passengers": num_passengers
        }
        if seat_class:
            payload["seat_class"] = seat_class
        return self._request("POST", "api/bookings", json=payload)

    def get_bookings(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if status: params["status"] = status
        return self._request("GET", "api/bookings", params=params)

    def get_booking(self, booking_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/bookings/{booking_id}")

    def cancel_booking(self, booking_id: int) -> Dict[str, Any]:
        return self._request("DELETE", f"api/bookings/{booking_id}")

class MuseumAPI(BaseAPI):
    """Wrapper for the Museum Ticket Booking API"""
    def get_time_slots(self) -> List[Dict[str, Any]]:
        return self._request("GET", "api/time-slots")

    def get_ticket_types(self) -> List[Dict[str, Any]]:
        return self._request("GET", "api/ticket-types")

    def get_availability(self, date: str, time_slot_id: Optional[int] = None, visitors: Optional[int] = None) -> Any:
        params = {"date": date}
        if time_slot_id is not None: params["time_slot_id"] = time_slot_id
        if visitors is not None: params["visitors"] = visitors
        return self._request("GET", "api/availability", params=params)

    def get_pricing(self, ticket_type: Optional[str] = None, visitors: Optional[int] = None) -> Dict[str, Any]:
        params = {}
        if ticket_type: params["ticket_type"] = ticket_type
        if visitors is not None: params["visitors"] = visitors
        return self._request("GET", "api/pricing", params=params)

    def create_ticket(self, time_slot_id: int, visit_date: str, visitor_name: str, visitor_email: str, num_visitors: int, ticket_type: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "time_slot_id": time_slot_id,
            "visit_date": visit_date,
            "visitor_name": visitor_name,
            "visitor_email": visitor_email,
            "num_visitors": num_visitors
        }
        if ticket_type:
            payload["ticket_type"] = ticket_type
        return self._request("POST", "api/tickets", json=payload)

    def get_tickets(self, date: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if date: params["date"] = date
        if status: params["status"] = status
        return self._request("GET", "api/tickets", params=params)

    def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/tickets/{ticket_id}")

    def cancel_ticket(self, ticket_id: int) -> Dict[str, Any]:
        return self._request("DELETE", f"api/tickets/{ticket_id}")

class RestaurantAPI(BaseAPI):
    """Wrapper for the Restaurant Reservation API"""
    def get_time_slots(self) -> Dict[str, Any]:
        return self._request("GET", "api/time-slots")

    def get_tables(self) -> List[Dict[str, Any]]:
        return self._request("GET", "api/tables")

    def get_available_tables(self, date: str, time_slot: str, party_size: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"date": date, "time_slot": time_slot}
        if party_size is not None: params["party_size"] = party_size
        return self._request("GET", "api/tables/available", params=params)

    def create_reservation(self, table_id: int, guest_name: str, guest_email: str, date: str, time_slot: str, party_size: int, special_requests: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "table_id": table_id,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "date": date,
            "time_slot": time_slot,
            "party_size": party_size
        }
        if special_requests:
            payload["special_requests"] = special_requests
        return self._request("POST", "api/reservations", json=payload)

    def get_reservations(self, date: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if date: params["date"] = date
        if status: params["status"] = status
        return self._request("GET", "api/reservations", params=params)

    def get_reservation(self, reservation_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/reservations/{reservation_id}")

    def cancel_reservation(self, reservation_id: int) -> Dict[str, Any]:
        return self._request("DELETE", f"api/reservations/{reservation_id}")

class TourGuideAPI(BaseAPI):
    """Wrapper for the Tour Guide Booking API"""
    def get_categories(self) -> List[Dict[str, Any]]:
        return self._request("GET", "api/categories")

    def get_tours(self, category: Optional[str] = None, difficulty: Optional[str] = None, max_price: Optional[float] = None, location: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if category: params["category"] = category
        if difficulty: params["difficulty"] = difficulty
        if max_price is not None: params["max_price"] = max_price
        if location: params["location"] = location
        return self._request("GET", "api/tours", params=params)

    def get_tour(self, tour_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/tours/{tour_id}")

    def get_available_tours(self, tour_id: int, date: str, guests: Optional[int] = None) -> Dict[str, Any]:
        params = {"tour_id": tour_id, "date": date}
        if guests is not None: params["guests"] = guests
        return self._request("GET", "api/tours/available", params=params)

    def get_pricing(self, tour_id: int, guests: Optional[int] = None) -> Dict[str, Any]:
        params = {"tour_id": tour_id}
        if guests is not None: params["guests"] = guests
        return self._request("GET", "api/pricing", params=params)

    def create_booking(self, tour_id: int, tour_date: str, guest_name: str, guest_email: str, num_guests: int) -> Dict[str, Any]:
        payload = {
            "tour_id": tour_id,
            "tour_date": tour_date,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "num_guests": num_guests
        }
        return self._request("POST", "api/bookings", json=payload)

    def get_bookings(self, status: Optional[str] = None, date: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if status: params["status"] = status
        if date: params["date"] = date
        return self._request("GET", "api/bookings", params=params)

    def get_booking(self, booking_id: int) -> Dict[str, Any]:
        return self._request("GET", f"api/bookings/{booking_id}")

    def cancel_booking(self, booking_id: int) -> Dict[str, Any]:
        return self._request("DELETE", f"api/bookings/{booking_id}")

async def process_message(data: ChatMessage):
    handler = OrcaHandler()
    session = handler.begin(data)

    try:
        variables = Variables(data.variables)
        # API keys are provided as Orca variables — retrieve them like this:
        #api_key = variables.get("API_KEY", "")
        #api_base_url = variables.get("API_BASE_URL", "http://localhost:8080")
        anthropic_key = variables.get("MADHACK-ANTHROPIC-KEY")

        # --- Your provider agent logic goes here ---
        
        # Connect with Hotel API wrapper
        #hotel_api = HotelAPI(api_key=api_key, base_url=api_base_url)

        # 2. Use any LLM (OpenAI, Anthropic, etc.) to understand incoming requests
        client = anthropic.Anthropic(api_key=anthropic_key)
        print("anthropic_key", anthropic_key)
        response = client.messages.create(
            model="claude-haiku-4-5",  # The current latest Haiku model
            max_tokens=1000,
            temperature=0.7,
            messages=[
                {
                    "role": "user", 
                    "content": "Write a haiku about artificial intelligence."
                }
            ]
        )
        # 3. Print the response
        print(response.content[0].text)
        session.stream(response.content[0].text)

        # 3. Map user intent to API actions (search, book, cancel, list, etc.)
        # 4. Return concise, structured results
        
        #session.stream("Provider agent is not implemented yet, but the HotelAPI wrapper class is ready.")
        session.close()

    except Exception as e:
        logger.exception("Error processing message")
        session.error("Something went wrong.", exception=e)

app, orca = create_agent_app(
    process_message_func=process_message,
    title="Provider Agent",
    description="Travel API provider agent",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
