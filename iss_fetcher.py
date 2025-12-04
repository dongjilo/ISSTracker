import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime


class ISSDataFetcher:
    """Handles API requests to fetch ISS and location data with fast Open Notify API."""

    def __init__(self):
        """Initialize the data fetcher and configure the request session."""
        # FAST API: Open Notify is much faster than wheretheiss.at
        self.iss_api_url = "http://api.open-notify.org/iss-now.json"
        self.geo_api_url = "https://nominatim.openstreetmap.org/reverse"

        # Backup API (slower but more detailed data)
        self.iss_api_url_backup = "https://api.wheretheiss.at/v1/satellites/25544"

        # Configure retry strategy for network resilience
        retry_strategy = Retry(
            total=2,  # Reduced retries for faster failure
            backoff_factor=0.5,  # Faster backoff
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)

        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_iss_position(self):
        """Fetches the current ISS position from the API."""
        try:
            # Use fast Open Notify API with short timeout
            response = self.session.get(self.iss_api_url, timeout=5)
            response.raise_for_status()
            data = response.json()

            # Open Notify response format
            if data.get('message') == 'success':
                timestamp = int(data['timestamp'])
                timestamp_obj = datetime.fromtimestamp(timestamp)
                iss_pos = data['iss_position']

                # Note: Open Notify doesn't provide altitude/velocity
                # Using estimated values (ISS orbits at ~408km, ~7.66km/s)
                return {
                    'latitude': float(iss_pos['latitude']),
                    'longitude': float(iss_pos['longitude']),
                    'altitude': 408.0,  # Estimated average altitude
                    'velocity': 27600.0,  # Estimated velocity in km/h
                    'timestamp_obj': timestamp_obj,
                    'timestamp_str': timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
                }

        except requests.RequestException as e:
            print(f"Open Notify API failed: {e}")
            # Try backup API if primary fails
            return self._get_iss_position_backup()

        return None

    def _get_iss_position_backup(self):
        """Backup method using wheretheiss.at API (slower but more detailed)."""
        try:
            response = self.session.get(self.iss_api_url_backup, timeout=10)
            response.raise_for_status()
            data = response.json()

            timestamp = int(data['timestamp'])
            timestamp_obj = datetime.fromtimestamp(timestamp)

            return {
                'latitude': float(data['latitude']),
                'longitude': float(data['longitude']),
                'altitude': float(data['altitude']),
                'velocity': float(data['velocity']),
                'timestamp_obj': timestamp_obj,
                'timestamp_str': timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
            }
        except requests.RequestException as e:
            print(f"Backup ISS API request failed: {e}")
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
            # Reduced timeout for faster response
            response = self.session.get(
                self.geo_api_url,
                params=params,
                headers=headers,
                timeout=8
            )

            if response.status_code == 400 or 'error' in response.text:
                return "Over Ocean"

            response.raise_for_status()
            data = response.json()
            address = data.get('address', {})

            if not address:
                return "Over Ocean"

            country = address.get('country')
            city = address.get('city') or address.get('town') or \
                   address.get('village') or address.get('state')

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


# Alternative: Even faster version that skips location lookup
class ISSDataFetcherFast:
    """Ultra-fast ISS fetcher - only gets position, no location details."""

    def __init__(self):
        self.iss_api_url = "http://api.open-notify.org/iss-now.json"
        self.session = requests.Session()

    def get_iss_position(self):
        """Fetches only ISS position (no location lookup) for maximum speed."""
        try:
            response = self.session.get(self.iss_api_url, timeout=3)
            response.raise_for_status()
            data = response.json()

            if data.get('message') == 'success':
                timestamp = int(data['timestamp'])
                timestamp_obj = datetime.fromtimestamp(timestamp)
                iss_pos = data['iss_position']

                return {
                    'latitude': float(iss_pos['latitude']),
                    'longitude': float(iss_pos['longitude']),
                    'altitude': 408.0,
                    'velocity': 27600.0,
                    'timestamp_obj': timestamp_obj,
                    'timestamp_str': timestamp_obj.strftime('%Y-%m-%d %H:%M:%S'),
                    'location': 'Tracking...'  # Skip slow location lookup
                }
        except Exception as e:
            print(f"ISS API error: {e}")
            return None

    def get_location_details(self, lat, lon):
        """Optional: Call this only when needed (like on manual update)."""
        return "Location lookup disabled for speed"