# Configuration file for Event Collection Agent
#
# This file contains all configuration variables and their associated comments
# that were previously defined in app.py

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Firecrawl Configuration for Self-Hosting ---
"""
Firecrawl SDK recent versions allow running against self-hosted without an API key.
We support both env var names: FIRECRAWL_BASE_URL and FIRECRAWL_API_URL.
If either is set, we will use it and allow empty api_key.
"""
FIRECRAWL_BASE_URL = os.environ.get("FIRECRAWL_BASE_URL") or "http://localhost:3002"
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")

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

