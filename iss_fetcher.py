import requests
import json
from datetime import datetime


class ISSDataFetcher:
    """Handles API requests to fetch ISS and location data."""

    def __init__(self):
        """Initialize the data fetcher."""
        self.iss_api_url = "https://api.wheretheiss.at/v1/satellites/25544"
        self.geo_api_url = "https://nominatim.openstreetmap.org/reverse"

    def get_iss_position(self):
        """Fetches the current ISS position from the API."""
        try:
            response = requests.get(self.iss_api_url, timeout=5)
            response.raise_for_status()
            data = response.json()

            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
            altitude = float(data['altitude'])
            velocity_kmh = float(data['velocity'])
            timestamp = int(data['timestamp'])

            timestamp_obj = datetime.fromtimestamp(timestamp)

            return {
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'velocity': velocity_kmh,
                'timestamp_obj': timestamp_obj,
                'timestamp_str': timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
            }
        except requests.RequestException as e:
            print(f"ISS API request failed: {e}")
            return None

    def get_location_details(self, lat, lon):
        """Fetches nearest city/country using OpenStreetMap (Nominatim)."""
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'zoom': 10,
            'accept-language': 'en'
        }

        headers = {
            'User-Agent': 'ISS_Tracker_App_2025 (student_project)'
        }
        try:
            response = requests.get(self.geo_api_url, params=params, headers=headers, timeout=5)
            if response.status_code == 400 or 'error' in response.text:
                return "Over Ocean"

            response.raise_for_status()
            data = response.json()
            address = data.get('address', {})

            if not address:
                return "Over Ocean"

            country = address.get('country')
            city = address.get('city') or address.get('town') or address.get('village') or address.get('state')

            if city and country:
                return f"{city}, {country}"
            elif country:
                return country
            else:
                return "Over Ocean"

        except requests.RequestException as e:
            print(f"Geo API request failed: {e}")
            return "N/A"
        except json.JSONDecodeError:
            print("Failed to decode Geo API response.")
            return "N/A"