# Configuration file for Event Collection Agent
#
# This file contains all configuration variables and their associated comments
# that were previously defined in app.py

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Firecrawl Configuration for Self-Hosting ---
# The base URL for your self-hosted Firecrawl API.
# The default is http://localhost:3002. Change it if your setup is different.
FIRECRAWL_BASE_URL = "http://localhost:3002"

# --- Google AI Configuration ---
# Replace with your actual Google AI API key.
# You can get a key from Google AI Studio.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# --- Google Geocoding API Configuration ---
# Your Google Geocoding API key for getting location coordinates
# GEOCODING_API_KEY is now in Geolocation module

# The URLs you want to scrape
TARGET_URLS = [
    "https://www.iloveqatar.net/events",
    "https://marhaba.qa/events/photo/"
]

# The Gemini model to use
GEMINI_MODEL = 'gemini-2.5-flash-lite'

# Colors are now imported from Geolocation module
