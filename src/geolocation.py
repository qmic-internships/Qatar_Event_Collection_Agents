"""
Geolocation Module

This module provides geolocation functionality with caching support for the Event Collection Agent.
It handles coordinate lookup using Google Geocoding API with local JSON cache to avoid redundant API calls.
"""

import os
import json
import requests
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Google Geocoding API Key
GEOCODING_API_KEY = os.environ.get("GEOCODING_API_KEY")

# --- CLI Colors ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    INFO = '\033[96m'
    SUCCESS = '\033[92m'

# --- Geolocation Cache ---
# Ensure cache file is in cache folder
_project_root = os.path.dirname(os.path.dirname(__file__))
_cache_dir = os.path.join(_project_root, 'cache')
GEOLOCATION_CACHE_FILE = os.path.join(_cache_dir, 'geolocation_cache.json')
_geolocation_cache = None
_geolocation_cache_lock = threading.Lock()

def load_geolocation_cache():
    """Load geolocation cache from JSON file with thread safety."""
    global _geolocation_cache
    if _geolocation_cache is not None:
        return _geolocation_cache
    if os.path.exists(GEOLOCATION_CACHE_FILE):
        with open(GEOLOCATION_CACHE_FILE, 'r', encoding='utf-8') as f:
            try:
                _geolocation_cache = json.load(f)
            except Exception:
                _geolocation_cache = {}
    else:
        _geolocation_cache = {}
    return _geolocation_cache

def save_geolocation_cache():
    """Save geolocation cache to JSON file with thread safety."""
    global _geolocation_cache
    with _geolocation_cache_lock:
        with open(GEOLOCATION_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_geolocation_cache, f, ensure_ascii=False, indent=2)

def get_location_coordinates(location_name):
    """
    Get coordinates for a location using Google Geocoding API.

    Returns a dictionary with: {"lat": latitude, "lng": longitude, "name": location_name}
    Uses a JSON file cache to avoid redundant API calls.

    Args:
        location_name (str): The location name to geocode

    Returns:
        dict: Dictionary containing lat, lng, and name
    """
    if not location_name or location_name.strip() == "":
        return {"lat": None, "lng": None, "name": location_name}

    # Skip geocoding for invalid/placeholder location names
    invalid_locations = ["N/A", "TBD", "To be announced", "TBA", "To be determined", "Location TBA", "Venue TBA"]
    if location_name.strip() in invalid_locations:
        print(f"{Colors.WARNING}⚠️  Skipping geocoding for invalid location: {location_name}{Colors.END}")
        return {"lat": None, "lng": None, "name": location_name}

    # --- Caching logic ---
    cache = load_geolocation_cache()
    if location_name in cache:
        print(f"{Colors.INFO}📦 Using cached coordinates for: {location_name}{Colors.END}")
        return cache[location_name]

    try:
        # Add "Qatar" to improve geocoding accuracy for Qatar locations
        search_query = f"{location_name}, Qatar"
        # Google Geocoding API URL
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': search_query,
            'key': GEOCODING_API_KEY
        }
        print(f"{Colors.INFO}🔍 Geocoding: {location_name}{Colors.END}")
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'OK' and data['results']:
            result = data['results'][0]
            location = result['geometry']['location']
            lat = location['lat']
            lng = location['lng']

            # Additional validation: check if the result is actually in Qatar
            if 24.5 <= lat <= 26.5 and 50.5 <= lng <= 52.5:
                location_data = {"lat": lat, "lng": lng, "name": location_name}
                print(f"{Colors.SUCCESS}✅ Found coordinates for {location_name}: {lat:.6f}, {lng:.6f}{Colors.END}")
                # Save to cache
                cache[location_name] = location_data
                save_geolocation_cache()
                return location_data
            else:
                print(f"{Colors.WARNING}⚠️  Coordinates outside Qatar for {location_name}: {lat:.6f}, {lng:.6f}{Colors.END}")
                return {"lat": None, "lng": None, "name": location_name}
        else:
            print(f"{Colors.WARNING}⚠️  No coordinates found for: {location_name}{Colors.END}")
            return {"lat": None, "lng": None, "name": location_name}

    except requests.exceptions.Timeout:
        print(f"{Colors.ERROR}❌ Timeout while geocoding: {location_name}{Colors.END}")
        return {"lat": None, "lng": None, "name": location_name}
    except requests.exceptions.ConnectionError:
        print(f"{Colors.ERROR}❌ Connection error while geocoding: {location_name}{Colors.END}")
        return {"lat": None, "lng": None, "name": location_name}
    except requests.exceptions.RequestException as e:
        print(f"{Colors.ERROR}❌ Request error while geocoding {location_name}: {e}{Colors.END}")
        return {"lat": None, "lng": None, "name": location_name}
    except KeyboardInterrupt:
        print(f"{Colors.WARNING}⚠️  Geocoding interrupted by user for: {location_name}{Colors.END}")
        return {"lat": None, "lng": None, "name": location_name}
    except Exception as e:
        print(f"{Colors.ERROR}❌ Unexpected error geocoding {location_name}: {e}{Colors.END}")
        return {"lat": None, "lng": None, "name": location_name}
