# main.py
#
# Description:
# This script demonstrates how to use a self-hosted, open-source instance of 
# Firecrawl to scrape a website and then uses Google's Gemini model 
# (gemini-2.5-flash-lite) to process the scraped content.
#
# Installation:
# Make sure you have the required Python packages installed:
# pip install firecrawl-py google-generativeai requests
#
# Note on API Keys:
# This script connects to a local Firecrawl instance and does not require a
# Firecrawl API key. However, you WILL need a Google AI API key to use the 
# Gemini model. It is highly recommended to use a more secure method for 
# handling API keys, such as environment variables, in a real application.
import os
import json
import time
import signal
import requests
import argparse
from urllib.parse import urlparse
import google.generativeai as genai
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
import re
import threading
# Load environment variables from .env file
load_dotenv()
# Global flag to track if script is interrupted
interrupted = False
def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    global interrupted
    interrupted = True
    print(f"\n{Colors.WARNING}⚠️  Interrupt signal received. Exiting immediately...{Colors.END}")
    exit(0)
# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
# --- Configuration ---
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
GEOCODING_API_KEY = os.environ.get("GEOCODING_API_KEY")
# The URLs you want to scrape
TARGET_URLS = [
    "https://marhaba.qa/events/photo/",
    "https://www.iloveqatar.net/events"
]
# Visit Qatar API endpoint
VISIT_QATAR_API_URL = "https://visitqatar.com/api/en/events.v2.json"
# The Gemini model to use
GEMINI_MODEL = 'gemini-2.5-flash-lite'
# --- CLI Colors ---
class Colors:
    HEADER = '\033[95m'
    INFO = '\033[96m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    BLUE = '\033[94m'
# --- Helper Functions ---
def save_scraped_content(content, url, raw_content_dir):
    """Save scraped content to a file with metadata header."""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace('.', '_').replace(':', '_')
    path = parsed_url.path.replace('/', '_').replace(':', '_')
    if not path or path == '_':
        path = 'home'
    filename = f"{domain}{path}_scraped_content.md"
    filepath = os.path.join(raw_content_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# Scraped Content from: {url}\n")
        f.write(f"Scraped at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Content length: {len(content)} characters\n")
        f.write("\n" + "="*50 + "\n\n")
        f.write(content)
    
    print(f"{Colors.INFO}Saved content to: {filepath}{Colors.END}")
    return filepath

def get_normalized_name(name):
    """Converts a name to a simplified, comparable format for deduplication."""
    if not name:
        return ""
    # Convert to lowercase and keep only letters and numbers
    return re.sub(r'[^a-z0-9]+', '', name.lower())

def intelligent_deduplication(events):
    """
    Groups events by location and date, then selects the best event from each group.
    The "best" event is the one with the longest description.
    """
    if not events:
        return []

    print(f"\n{Colors.HEADER}🧠 Performing intelligent deduplication on {len(events)} events...{Colors.END}")
    
    event_groups = {}

    for event in events:
        # Use a reliable key: location coordinates + date
        # This handles cases where the key exists but is None, or is missing entirely.
        location = event.get('location') or ''
        date = event.get('date') or ''
        
        # Extract coordinates if available for a more robust key
        coord_match = re.search(r'\(([^)]+)\)', location)
        if coord_match:
            # Use the coordinates as the primary location key
            key_location = coord_match.group(1).strip()
        else:
            # Fallback to a normalized location name if no coordinates exist
            key_location = get_normalized_name(location)

        # Create a unique key for each event group
        group_key = f"{key_location}_{date}"

        if group_key not in event_groups:
            event_groups[group_key] = []
        
        event_groups[group_key].append(event)

    final_unique_events = []
    duplicates_found = 0

    for group_key, group_events in event_groups.items():
        if len(group_events) > 1:
            duplicates_found += len(group_events) - 1
            # This is a group of duplicates. Select the best one.
            # The rule: the event with the longest description is the "best".
            best_event = sorted(group_events, key=lambda x: len(x.get('description', '')), reverse=True)[0]
            final_unique_events.append(best_event)
        else:
            # This is already a unique event, add it directly.
            final_unique_events.append(group_events[0])
            
    if duplicates_found > 0:
        print(f"{Colors.SUCCESS}✅ Merged {duplicates_found} duplicate events.{Colors.END}")
    else:
        print(f"{Colors.INFO}No duplicates were found to merge.{Colors.END}")
        
    print(f"{Colors.INFO}Total unique events after deduplication: {len(final_unique_events)}{Colors.END}")
    
    return final_unique_events

def add_coordinates_to_events(events):
    """Add coordinates to event locations using Google Geocoding API."""
    if not events:
        return events
        
    print(f"\n{Colors.HEADER}🗺️  Adding coordinates to event locations...{Colors.END}")
    print(f"{Colors.INFO}Processing {len(events)} events for geocoding...{Colors.END}")
    
    try:
        for i, event in enumerate(events, 1):
            if interrupted:
                print(f"{Colors.WARNING}⚠️  Stopping geocoding due to interrupt signal...{Colors.END}")
                break
                
            if 'location' in event and event['location']:
                # Check if location already has coordinates
                if not str(event['location']).startswith('Location ('):
                    print(f"{Colors.INFO}[{i}/{len(events)}] Processing event: {event.get('name', 'Unknown')}{Colors.END}")
                    original_location = event['location']
                    event['location'] = get_location_coordinates(original_location)
                    time.sleep(0.5)
                else:
                    print(f"{Colors.INFO}[{i}/{len(events)}] Event already has coordinates: {event.get('name', 'Unknown')}{Colors.END}")
                    
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}⚠️  Geocoding process interrupted by user. Continuing with available data...{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.ERROR}❌ Error during geocoding process: {e}{Colors.END}")
        print(f"{Colors.WARNING}Continuing with available data...{Colors.END}")
    
    return events
def extract_events_with_gemini(content, prompt_template, post_process_func=None):
    """Extract events from content using Gemini."""
    try:
        # Configure Gemini (idempotent; safe to call multiple times)
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Create prompt using template
        prompt = prompt_template.format(content=content[:50000])
        
        # Call Gemini API
        response = model.generate_content(prompt)
        
        # Extract and clean the JSON response
        json_content = response.text.strip()
        
        # Remove markdown code block markers if present
        if json_content.startswith('```json'):
            json_content = json_content[7:]
        if json_content.endswith('```'):
            json_content = json_content[:-3]
        
        json_content = json_content.strip()
        
        # Parse the events
        events = json.loads(json_content)
        
        # Apply post-processing function if provided
        if post_process_func and isinstance(events, list):
            events = post_process_func(events)
            
        return events if isinstance(events, list) else []
        
    except json.JSONDecodeError as e:
        print(f"{Colors.ERROR}Error parsing events from Gemini: {e}{Colors.END}")
        print(f"{Colors.WARNING}Raw response:{Colors.END}")
        print(json_content)
        return []
    except Exception as e:
        print(f"{Colors.ERROR}Error extracting events with Gemini: {e}{Colors.END}")
        return []
def scrape_with_pagination(app, starting_url, raw_content_dir, url_extractor, 
                           page_url_constructor=None, max_pages=200):
    """
    Generic function to scrape listing pages with pagination.
    
    Args:
        app: FirecrawlApp instance
        starting_url: Base URL to start scraping
        raw_content_dir: Directory to save scraped content
        url_extractor: Function to extract event URLs from page content
        page_url_constructor: Function to construct pagination URLs
        max_pages: Maximum number of pages to scrape
    """
    print(f"{Colors.HEADER}🧭 Pagination scraping starting at: {starting_url}{Colors.END}")
    collected_event_urls = []
    seen_event_urls = set()
    
    for page_number in range(1, max_pages + 1):
        if interrupted:
            print(f"{Colors.WARNING}⚠️  Stopping pagination due to interrupt signal...{Colors.END}")
            break
            
        page_url = page_url_constructor(starting_url, page_number) if page_url_constructor else starting_url
        print(f"{Colors.INFO}🔎 Scraping listing page {page_number}: {page_url}{Colors.END}")
        
        try:
            scraped = app.scrape_url(page_url, timeout=30000)
            if not scraped or not getattr(scraped, 'markdown', None):
                print(f"{Colors.WARNING}No markdown content for listing page: {page_url}{Colors.END}")
                if page_number > 1:
                    print(f"{Colors.INFO}Assuming end of pagination after page {page_number}.{Colors.END}")
                    break
                continue
                
            markdown_content = scraped.markdown
            
            # Save the listing page markdown
            save_scraped_content(markdown_content, page_url, raw_content_dir)
            
            # Extract event URLs from this listing page
            page_event_urls = url_extractor(markdown_content)
            print(f"{Colors.INFO}Found {len(page_event_urls)} event links on page {page_number}.{Colors.END}")
            
            # Stop condition: if no events found and we're past the first page, stop
            if len(page_event_urls) == 0 and page_number > 1:
                print(f"{Colors.INFO}No events found on page {page_number}. Stopping pagination.{Colors.END}")
                break
                
            for url in page_event_urls:
                if url not in seen_event_urls:
                    seen_event_urls.add(url)
                    collected_event_urls.append(url)
            
            # Be polite between pages
            time.sleep(0.3)
            
        except Exception as ex:
            print(f"{Colors.WARNING}Failed to scrape listing page {page_url} | {ex}{Colors.END}")
            if page_number > 1:
                print(f"{Colors.INFO}Assuming end of pagination after page {page_number}.{Colors.END}")
                break
    
    # Scrape each collected event detail page and save markdown
    print(f"{Colors.HEADER}📝 Scraping {len(collected_event_urls)} event detail pages...{Colors.END}")
    for index, event_url in enumerate(collected_event_urls, 1):
        if interrupted:
            print(f"{Colors.WARNING}⚠️  Stopping event detail scraping due to interrupt signal...{Colors.END}")
            break
            
        print(f"{Colors.INFO}[{index}/{len(collected_event_urls)}] Scraping event: {event_url}{Colors.END}")
        try:
            event_scraped = app.scrape_url(event_url, timeout=30000)
            if not event_scraped or not getattr(event_scraped, 'markdown', None):
                print(f"{Colors.WARNING}No markdown content for event: {event_url}{Colors.END}")
                continue
                
            event_markdown = event_scraped.markdown
            save_scraped_content(event_markdown, event_url, raw_content_dir)
            
            # Small delay to avoid hammering
            time.sleep(0.2)
            
        except Exception as event_ex:
            print(f"{Colors.WARNING}Failed to scrape event detail page: {event_url} | {event_ex}{Colors.END}")
    
    print(f"{Colors.SUCCESS}✅ Pagination scraping completed. Total events collected: {len(collected_event_urls)}{Colors.END}")
    return collected_event_urls
# --- Visit Qatar API Function ---
def fetch_visit_qatar_events():
    """
    Fetch events from the Visit Qatar API endpoint and process with Gemini.
    Returns a list of events with coordinates added.
    """
    print(f"{Colors.HEADER}🌐 Fetching events from Visit Qatar API...{Colors.END}")
    print(f"{Colors.INFO}API URL: {VISIT_QATAR_API_URL}{Colors.END}")
    
    try:
        # Fetch data from the API
        response = requests.get(VISIT_QATAR_API_URL, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"{Colors.SUCCESS}✅ Successfully fetched data from Visit Qatar API{Colors.END}")
        
        # Check if we have events data
        if 'events' not in data or not isinstance(data['events'], list):
            print(f"{Colors.WARNING}⚠️  No 'events' field found in API response{Colors.END}")
            print(f"{Colors.INFO}API response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}{Colors.END}")
            return []
        
        raw_events = data['events']
        print(f"{Colors.INFO}Found {len(raw_events)} events in the API response{Colors.END}")
        
        # Create a prompt for Gemini to process the events
        prompt_template = """
        Based on the following JSON data from the Visit Qatar API, extract and format all events.
        
        Each event should have these exact fields:
        - name: The event title/name
        - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
        - time: The event time(s) in format "HH:MM AM/PM" or similar
        - location: The event venue/location (with coordinates if available)
        - description: A brief description of the event
        - category: The event category (cultural, entertainment, sports, food, education, etc.)
        - url: The event URL if available
        
        For locations:
        - If the API data contains latitude and longitude coordinates, format as: "Location (lat, lng) venue_name"
        - If no coordinates are available, just use the venue name (coordinates will be added later via geocoding)
        - Look for location data in fields like 'venue', 'location', 'address', or similar
        
        Raw API Data:
        {content}
        
        Please return ONLY valid JSON array without any additional text or formatting.
        """
        
        # Process events with Gemini
        processed_events = extract_events_with_gemini(
            json.dumps(raw_events[:50], indent=2),  # Limit to first 50 events to avoid token limits
            prompt_template,
            lambda events: [dict(event, source='Visit Qatar API') for event in events]
        )
        
        print(f"{Colors.SUCCESS}✅ Successfully processed {len(processed_events)} events with Gemini{Colors.END}")
        
        # Add coordinates to events
        events_with_coords = add_coordinates_to_events(processed_events)
        
        return events_with_coords
        
    except requests.exceptions.Timeout:
        print(f"{Colors.ERROR}❌ Timeout while fetching from Visit Qatar API{Colors.END}")
        return []
    except requests.exceptions.ConnectionError:
        print(f"{Colors.ERROR}❌ Connection error while fetching from Visit Qatar API{Colors.END}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"{Colors.ERROR}❌ Request error while fetching from Visit Qatar API: {e}{Colors.END}")
        return []
    except json.JSONDecodeError as e:
        print(f"{Colors.ERROR}❌ JSON decode error from Visit Qatar API: {e}{Colors.END}")
        return []
    except Exception as e:
        print(f"{Colors.ERROR}❌ Unexpected error fetching from Visit Qatar API: {e}{Colors.END}")
        return []
# --- Geolocation Cache ---
GEOLOCATION_CACHE_FILE = 'geolocation_cache.json'
_geolocation_cache = None
_geolocation_cache_lock = threading.Lock()
def load_geolocation_cache():
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
    global _geolocation_cache
    with _geolocation_cache_lock:
        with open(GEOLOCATION_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_geolocation_cache, f, ensure_ascii=False, indent=2)
def get_location_coordinates(location_name):
    """
    Get coordinates for a location using Google Geocoding API.
    Returns formatted string: "Location (Lat, Lng) the name of the location then the coordinates"
    Uses a JSON file cache to avoid redundant API calls.
    """
    if not location_name or location_name.strip() == "":
        return location_name
    # Skip geocoding for invalid/placeholder location names
    invalid_locations = ["N/A", "TBD", "To be announced", "TBA", "To be determined", "Location TBA", "Venue TBA"]
    if location_name.strip() in invalid_locations:
        print(f"{Colors.WARNING}⚠️  Skipping geocoding for invalid location: {location_name}{Colors.END}")
        return location_name
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
                formatted_location = f"Location ({lat:.6f}, {lng:.6f}) {location_name}"
                print(f"{Colors.SUCCESS}✅ Found coordinates for {location_name}: {lat:.6f}, {lng:.6f}{Colors.END}")
                # Save to cache
                cache[location_name] = formatted_location
                save_geolocation_cache()
                return formatted_location
            else:
                print(f"{Colors.WARNING}⚠️  Coordinates outside Qatar for {location_name}: {lat:.6f}, {lng:.6f}{Colors.END}")
                return location_name
        else:
            print(f"{Colors.WARNING}⚠️  No coordinates found for: {location_name}{Colors.END}")
            return location_name
    except requests.exceptions.Timeout:
        print(f"{Colors.ERROR}❌ Timeout while geocoding: {location_name}{Colors.END}")
        return location_name
    except requests.exceptions.ConnectionError:
        print(f"{Colors.ERROR}❌ Connection error while geocoding: {location_name}{Colors.END}")
        return location_name
    except requests.exceptions.RequestException as e:
        print(f"{Colors.ERROR}❌ Request error while geocoding {location_name}: {e}{Colors.END}")
        return location_name
    except KeyboardInterrupt:
        print(f"{Colors.WARNING}⚠️  Geocoding interrupted by user for: {location_name}{Colors.END}")
        return location_name
    except Exception as e:
        print(f"{Colors.ERROR}❌ Unexpected error geocoding {location_name}: {e}{Colors.END}")
        return location_name
def extract_marhaba_event_urls(markdown_content):
    """
    Extract all unique Marhaba Qatar event detail URLs from the main page markdown content.
    """
    # Regex to match event detail URLs
    url_pattern = r"https://marhaba\.qa/event/[^)\s]+/"
    urls = re.findall(url_pattern, markdown_content)
    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    return unique_urls
def extract_ilq_event_urls(markdown_content):
    """
    Extract only iLoveQatar EVENT DETAIL URLs from listing content.
    Rules:
      - Must be under /events/<category>/<slug>
      - Exclude: /events, /events/<category>, /events/filter, any with query-only filters
    """
    # Broadly match ILQ events links then filter precisely
    url_pattern = r"https://www\.iloveqatar\.net/events/[^)\s]+"
    raw_urls = re.findall(url_pattern, markdown_content)
    def is_detail_url(u: str) -> bool:
        try:
            parsed = urlparse(u)
            path_parts = [p for p in parsed.path.split('/') if p]
            # Known ILQ event categories
            category_slugs = {
                'entertainment', 'sports', 'food-dining', 'arts-culture', 'night',
                'community', 'social-responsibility', 'education', 'other', 'volunteer'
            }
            # Expect at least ['events', '<category>', '<slug>']
            if len(path_parts) < 3:
                return False
            if path_parts[0] != 'events':
                return False
            # Exclude filter and tag collections
            if any(part in {'filter', 'tag', 'tags'} for part in path_parts):
                return False
            # Exclude pure category pages like /events/<category>
            if len(path_parts) == 2:
                return False
            # Defensive: ensure second part is a known category and third is a slug
            if path_parts[1] not in category_slugs:
                return False
            return True
        except Exception:
            return False
    def _is_ilq_u17_individual_match_url(u: str) -> bool:
        try:
            parsed = urlparse(u)
            path_parts = [p for p in parsed.path.split('/') if p]
            if len(path_parts) < 3 or path_parts[0] != 'events':
                return False
            slug = '/'.join(path_parts[2:]).lower()
            # Apply only for U-17 references
            if ('u-17' not in slug) and ('u17' not in slug):
                return False
            # Patterns indicating individual fixtures
            if '-vs-' in slug:
                return True
            if re.search(r'(^|-)group(-|\d|[a-z])', slug):
                return True
            if any(term in slug for term in ['quarter-final', 'quarterfinal', 'semi-final', 'semifinal', 'round-of-']):
                return True
            return False
        except Exception:
            return False
    # Deduplicate while preserving order and apply filter
    seen = set()
    unique_urls = []
    for url in raw_urls:
            # Keep only detail URLs and exclude U-17 individual matches early
        if is_detail_url(url) and not _is_ilq_u17_individual_match_url(url) and url not in seen:
            seen.add(url)
            unique_urls.append(url)
    return unique_urls
def _normalize_tokens(text: str) -> set:
    text = text.lower()
    # Replace non-alphanumeric with space (ASCII-focused for robustness)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t]
    return set(tokens)
def _select_primary_event_by_slug_tokens(events: list, slug_tokens: list[str]) -> dict | None:
    """
    From a list of event dicts, select the one whose name best matches the slug tokens.
    Requires at least 2-token overlap; if none meets threshold, return first event.
    """
    if not events:
        return None
    threshold = 2
    slug_token_set = set([t for t in slug_tokens if t])
    best = None
    best_overlap = -1
    for evt in events:
        name = (evt.get('name') or '').strip()
        if not name:
            continue
        name_tokens = _normalize_tokens(name)
        overlap = len(name_tokens & slug_token_set)
        if overlap > best_overlap:
            best_overlap = overlap
            best = evt
    if best is None:
        return events[0]
    if best_overlap < threshold:
        return events[0]
    return best
def _ilq_reconstruct_event_path_from_filename(filename: str, ilq_event_prefix: str) -> str:
    """Convert filename-based slug to path 'category/slug' by replacing first '_' with '/'."""
    raw = filename[len(ilq_event_prefix):-len('_scraped_content.md')].rstrip('_')
    return raw.replace('_', '/', 1)
def _is_u17_world_cup_individual_match(event_name: str) -> bool:
    """
    Return True if the event name looks like an individual FIFA U-17 World Cup match (e.g., contains 'vs', 'Group X:', rounds),
    and False for overarching events like 'FIFA U-17 World Cup Qatar 2025'.
    """
    if not event_name:
        return False
    name = event_name.lower()
    # Must reference u-17 to apply this filter
    if 'u-17' not in name and 'u17' not in name:
        return False
    # Patterns that indicate individual matches or specific fixtures
    if ' vs ' in name or ' vs. ' in name:
        return True
    if re.search(r"\bgroup\s*[a-z0-9]+\b", name):
        return True
    if any(term in name for term in ['quarterfinal', 'quarter-final', 'round of', 'semifinal', 'semi-final', 'final']):
        return True
    return False
def extract_event_source_url(markdown_content):
    """
    Extract the first valid external website link from the event markdown content after a 'Website:' label.
    Returns the URL as a string, or None if not found.
    """
    # Look for a line starting with 'Website:'
    website_section = re.search(r'Website:\s*\n\[* ?(https?://[^)\]\s]+)', markdown_content)
    if website_section:
        return website_section.group(1)
    return None
def extract_ilq_visit_website_url(markdown_content: str) -> str | None:
    """
    Extract the external link labeled 'Visit Website' from an iLoveQatar event page markdown.
    Returns the URL string if found, else None.
    """
    try:
        # Match markdown links like: [Visit Website](https://example.com ...) case-insensitively
        match = re.search(r"\[\s*Visit\s+Website\s*\]\((https?://[^)\s]+)", markdown_content, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    except Exception:
        return None
def filter_events_with_gemini(input_file, output_file, batch_size=20):
    """
    Filter events using Gemini to remove events inappropriate for Qatari culture and expired events.
    Processes events in batches to improve reliability and quality.

    Args:
        input_file: Path to the input JSON file containing all events.
        output_file: Path to the output JSON file for filtered events.
        batch_size: The number of events to process in each API call.
    """
    if not os.path.exists(input_file):
        print(f"{Colors.ERROR}Input file {input_file} does not exist.{Colors.END}")
        return 0

    print(f"{Colors.HEADER}🔍 Loading events from {input_file} for filtering...{Colors.END}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            events = json.load(f)

        if not events:
            print(f"{Colors.WARNING}No events found in {input_file}.{Colors.END}")
            return 0

        print(f"{Colors.INFO}Loaded {len(events)} events for filtering.{Colors.END}")

        # Configure Gemini
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)

        all_filtered_events = []
        event_batches = [events[i:i + batch_size] for i in range(0, len(events), batch_size)]
        num_batches = len(event_batches)

        print(f"{Colors.INFO}Splitting events into {num_batches} batches of up to {batch_size} events each.{Colors.END}")

        for i, batch in enumerate(event_batches, 1):
            if interrupted:
                print(f"{Colors.WARNING}⚠️  Stopping filtering due to interrupt signal...{Colors.END}")
                break

            print(f"\n{Colors.INFO}Processing batch {i}/{num_batches}...{Colors.END}")

            prompt = f"""
            You are a cultural content filter for events in Qatar. Your task is to review the following events and filter out:
            1. Music concerts (any live music performances).
            2. Bar/nightclub events (any events at bars, nightclubs, or venues primarily serving alcohol)
            3. Expired events (events that have already occurred - today's date is {time.strftime('%Y-%m-%d')})
            4. Events that are related to BTS or any other Bands or Artists.

            For each event, determine if it should be included or excluded based on the criteria above.

            IMPORTANT: Return ONLY a JSON array containing the events that SHOULD be included (not filtered out).
            Each event must maintain all its original fields exactly as they appear in the input.

            DO NOT add or remove any fields from the events. Just return the events that pass the filter.

            Events to filter:
            {json.dumps(batch, ensure_ascii=False)}

            Please return ONLY valid JSON without any additional text or formatting.
            """

            json_content = ""
            try:
                # Call Gemini API
                response = model.generate_content(prompt)
                json_content = response.text.strip()

                # Remove markdown code block markers if present
                if json_content.startswith('```json'):
                    json_content = json_content[7:]
                if json_content.endswith('```'):
                    json_content = json_content[:-3]

                json_content = json_content.strip()

                # Parse the filtered events for this batch
                filtered_batch = json.loads(json_content)

                if not isinstance(filtered_batch, list):
                    print(f"{Colors.ERROR}Batch {i}/{num_batches}: Unexpected response format. Expected a list.{Colors.END}")
                    continue

                # Validate and add to the main list
                valid_batch_events = []
                for event in filtered_batch:
                    if isinstance(event, dict) and 'name' in event and 'date' in event:
                        valid_batch_events.append(event)
                    else:
                        print(f"{Colors.WARNING}Batch {i}/{num_batches}: Skipping invalid event structure: {event}{Colors.END}")

                all_filtered_events.extend(valid_batch_events)
                print(f"{Colors.SUCCESS}✅ Batch {i}/{num_batches}: Successfully processed. Found {len(valid_batch_events)} valid events.{Colors.END}")

            except json.JSONDecodeError as e:
                print(f"{Colors.ERROR}Batch {i}/{num_batches}: Error parsing filtered events from Gemini: {e}{Colors.END}")
                print(f"{Colors.WARNING}Raw response for batch {i}:{Colors.END}\n{json_content}")
            except Exception as e:
                print(f"{Colors.ERROR}Batch {i}/{num_batches}: Error filtering events with Gemini: {e}{Colors.END}")

            # Be polite to the API
            time.sleep(1)

        print(f"\n{Colors.SUCCESS}✅ Successfully finished processing all batches.{Colors.END}")
        print(f"{Colors.INFO}Original events: {len(events)}{Colors.END}")
        print(f"{Colors.INFO}Total valid filtered events: {len(all_filtered_events)}{Colors.END}")
        print(f"{Colors.INFO}Filtered out: {len(events) - len(all_filtered_events)} events{Colors.END}")

        # Save the final consolidated list of filtered events
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_filtered_events, f, indent=2, ensure_ascii=False)

        print(f"{Colors.INFO}Filtered events saved to: {output_file}{Colors.END}")

        # Show a sample of filtered events
        if all_filtered_events:
            print(f"\n{Colors.HEADER}🗺️  Sample filtered events:{Colors.END}")
            for i, event in enumerate(all_filtered_events[:3]):
                print(f"{Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{Colors.END}")
                print(f"   📍 {event.get('location', 'N/A')}")
                print(f"   🗓️ {event.get('date', 'N/A')}")
                print()

        return len(all_filtered_events)

    except Exception as e:
        print(f"{Colors.ERROR}An unexpected error occurred in the filtering process: {e}{Colors.END}")
        return 0
# --- Main Script ---
def main():
    """
    Main function to scrape multiple URLs with a local Firecrawl instance and 
    process them with Google's Gemini model.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Qatar Events Scraper and Analyzer')
    parser.add_argument('--visit-qatar', action='store_true', 
                       help='Fetch events from Visit Qatar API instead of scraping websites')
    parser.add_argument('--iloveqatar', action='store_true',
                       help='Run ONLY the iLoveQatar special handling (pagination + event detail scraping).')
    parser.add_argument('--iloveqatar-pages', type=int, default=12,
                       help='Max pages to scrape in --iloveqatar mode (default: 12).')
    parser.add_argument('--filter-events', action='store_true',
                       help='Filter events in doha_events.json for cultural appropriateness and expiration, then deduplicate.')
    args = parser.parse_args()
    
    if args.filter_events:
        # --- NEW: Event Filtering and Deduplication Mode ---
        print(f"{Colors.HEADER}{Colors.BOLD}🚀 Starting Event Filtering & Deduplication Mode 🚀{Colors.END}")
        _filter_run_start = time.time()
        
        input_filename = 'doha_events.json'
        intermediate_filename = 'doha_filtered_events.json'
        final_filename = 'doha_final_events.json'

        # Step 1: Filter events using Gemini
        filtered_count = filter_events_with_gemini(input_filename, intermediate_filename)
        
        if filtered_count > 0:
            # Step 2: Load the filtered events
            print(f"\n{Colors.HEADER}🔄 Loading filtered events for deduplication...{Colors.END}")
            try:
                with open(intermediate_filename, 'r', encoding='utf-8') as f:
                    events_to_deduplicate = json.load(f)
                
                # Step 3: Run intelligent deduplication
                final_events = intelligent_deduplication(events_to_deduplicate)
                
                # Step 4: Save the final, clean list
                with open(final_filename, 'w', encoding='utf-8') as f:
                    json.dump(final_events, f, indent=2, ensure_ascii=False)
                
                print(f"\n{Colors.SUCCESS}✅ Final, deduplicated events saved to: {final_filename}{Colors.END}")

                # Show a sample of final events
                if final_events:
                    print(f"\n{Colors.HEADER}🗺️  Sample final events:{Colors.END}")
                    for i, event in enumerate(final_events[:3]):
                        print(f"{Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{Colors.END}")
                        print(f"   📍 {event.get('location', 'N/A')}")
                        print(f"   🗓️ {event.get('date', 'N/A')}")
                        print()

            except FileNotFoundError:
                print(f"{Colors.ERROR}Could not find intermediate file {intermediate_filename} to deduplicate.{Colors.END}")
            except Exception as e:
                print(f"{Colors.ERROR}An error occurred during deduplication: {e}{Colors.END}")
        else:
            print(f"{Colors.WARNING}Filtering produced no events. Skipping deduplication.{Colors.END}")

        _dur = int(time.time() - _filter_run_start)
        print(f"{Colors.INFO}⏱️ Run duration: {_dur//60}:{_dur%60:02d}{Colors.END}")
        print(f"\n{Colors.HEADER}{Colors.BOLD}--- Event filtering & deduplication mode finished ---{Colors.END}")
        return
    
    if args.iloveqatar:
        # Run iLoveQatar-only mode (fast test of special handling)
        print(f"{Colors.HEADER}{Colors.BOLD}🚀 Starting iLoveQatar special-handling test mode 🚀{Colors.END}")
        _ilq_run_start = time.time()
        try:
            app = FirecrawlApp(api_url=FIRECRAWL_BASE_URL)
        except Exception as e:
            print(f"{Colors.ERROR}Error initializing Firecrawl client: {e}{Colors.END}")
            print(f"{Colors.WARNING}Ensure Firecrawl is running and accessible at {FIRECRAWL_BASE_URL}.{Colors.END}")
            return
        raw_content_dir = "scraped_pages"
        if not os.path.exists(raw_content_dir):
            os.makedirs(raw_content_dir)
            print(f"{Colors.INFO}Created directory: {raw_content_dir}{Colors.END}")
        starting_url = "https://www.iloveqatar.net/events"
        
        # Define page URL constructor for ILQ
        def ilq_page_url_constructor(base_url, page_num):
            if page_num == 1:
                return base_url
            sep = '&page=' if '?' in base_url else '?page='
            return f"{base_url}{sep}{page_num}"
        
        try:
            collected = scrape_with_pagination(
                app=app,
                starting_url=starting_url,
                raw_content_dir=raw_content_dir,
                url_extractor=extract_ilq_event_urls,
                page_url_constructor=ilq_page_url_constructor,
                max_pages=args.iloveqatar_pages,
            )
            print(f"{Colors.SUCCESS}✅ iLoveQatar test mode complete. Event URLs collected: {len(collected)}{Colors.END}")
        except Exception as e:
            print(f"{Colors.ERROR}Error during iLoveQatar test scrape: {e}{Colors.END}")
        
        # Configure Gemini for event extraction
        if not GOOGLE_API_KEY:
            print(f"{Colors.ERROR}GOOGLE_API_KEY environment variable is not set. Cannot extract events for iLoveQatar mode.{Colors.END}")
            _dur = int(time.time() - _ilq_run_start)
            print(f"{Colors.INFO}⏱️ Run duration: {_dur//60}:{_dur%60:02d}{Colors.END}")
            print(f"\n{Colors.HEADER}{Colors.BOLD}--- iLoveQatar test mode finished ---{Colors.END}")
            return
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)
        except Exception as e:
            print(f"{Colors.ERROR}Error initializing Gemini model: {e}{Colors.END}")
            _dur = int(time.time() - _ilq_run_start)
            print(f"{Colors.INFO}⏱️ Run duration: {_dur//60}:{_dur%60:02d}{Colors.END}")
            print(f"\n{Colors.HEADER}{Colors.BOLD}--- iLoveQatar test mode finished ---{Colors.END}")
            return
        
        # Process scraped ILQ event pages → extract events with Gemini
        print(f"\n{Colors.HEADER}🗓️  Processing iLoveQatar raw content for event extraction...{Colors.END}")
        all_events: list[dict] = []
        scraped_files = [f for f in os.listdir(raw_content_dir) if f.endswith('_scraped_content.md')]
        ilq_event_prefix = 'www_iloveqatar_net_events_'
        ilq_listing_filename = 'www_iloveqatar_net_events_scraped_content.md'
        scraped_files = [f for f in scraped_files if f.startswith(ilq_event_prefix) and f != ilq_listing_filename]
        if not scraped_files:
            print(f"{Colors.WARNING}No iLoveQatar event files found to process in '{raw_content_dir}'.{Colors.END}")
        for filename in scraped_files:
            filepath = os.path.join(raw_content_dir, filename)
            print(f"{Colors.INFO}Processing ILQ raw content from: {filename}{Colors.END}")
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                # Extract the actual content (skip the header metadata)
                content_start = raw_content.find('==================================================')
                actual_content = raw_content[content_start + 52:] if content_start != -1 else raw_content
                # Build a targeted prompt to extract only the main event
                event_path = _ilq_reconstruct_event_path_from_filename(filename, ilq_event_prefix)
                event_slug_only = event_path.split('/', 1)[1] if '/' in event_path else event_path
                event_slug_tokens = _normalize_tokens(event_slug_only)
                
                prompt_template = """
                You are given the scraped markdown of a SINGLE event page from iLoveQatar.net.
                Extract ONLY the primary event on this page and return a JSON array with exactly one object.
                Do NOT include related or other events listed on the page.
                Fields:
                - name: The event title/name
                - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
                - time: The event time(s) in format "HH:MM AM/PM" or similar
                - location: The event venue/location
                - description: A brief description of the event
                - category: The event category
                - url: The event URL if available, or website URL if not
                Content to analyze:
                ---
                {content}
                ---
                Return ONLY valid JSON array without any additional text or formatting.
                """
                
                # Extract events with Gemini
                events = extract_events_with_gemini(
                    actual_content,
                    prompt_template,
                    lambda events: [
                        dict(
                            event,
                            url=(
                                extract_ilq_visit_website_url(actual_content)
                                or f"https://www.iloveqatar.net/events/{_ilq_reconstruct_event_path_from_filename(filename, ilq_event_prefix)}"
                            )
                        )
                        for event in (
                            _select_primary_event_by_slug_tokens(events, list(event_slug_tokens)) if len(events) > 1 else events
                        )
                    ]
                )
                
                all_events.extend(events)
                print(f"{Colors.SUCCESS}Extracted {len(events)} event(s) from {filename}{Colors.END}")
            except Exception as e:
                print(f"{Colors.ERROR}Error processing {filename}: {e}{Colors.END}")
        
        # Deduplicate and geocode
        unique_events: list[dict] = []
        if all_events:
            seen_events = set()
            for event in all_events:
                if isinstance(event, dict) and 'name' in event and 'date' in event:
                    event_key = f"{event['name']}_{event['date']}"
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        unique_events.append(event)
            
            # Exclude individual FIFA U-17 World Cup matches; keep overarching events only
            before_count = len(unique_events)
            unique_events = [e for e in unique_events if not _is_u17_world_cup_individual_match(e.get('name', ''))]
            removed = before_count - len(unique_events)
            if removed > 0:
                print(f"{Colors.INFO}Filtered out {removed} individual U-17 World Cup match events.{Colors.END}")
            
            # Add coordinates to events
            unique_events = add_coordinates_to_events(unique_events)
        
        # Save output
        if unique_events:
            with open('doha_events.json', 'w', encoding='utf-8') as f:
                json.dump(unique_events, f, indent=2, ensure_ascii=False)
            print(f"\n{Colors.SUCCESS}✅ Successfully extracted {len(unique_events)} unique ILQ events with coordinates!{Colors.END}")
            print(f"{Colors.INFO}Events saved to: doha_events.json{Colors.END}")
            print(f"\n{Colors.HEADER}🗺️  Sample events with coordinates:{Colors.END}")
            for i, event in enumerate(unique_events[:3]):
                print(f"{Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{Colors.END}")
                print(f"   📍 {event.get('location', 'N/A')}")
                print(f"   🗓️ {event.get('date', 'N/A')}")
                print()
        else:
            print(f"\n{Colors.WARNING}No unique events were extracted from iLoveQatar pages.{Colors.END}")
        _dur = int(time.time() - _ilq_run_start)
        print(f"{Colors.INFO}⏱️ Run duration: {_dur//60}:{_dur%60:02d}{Colors.END}")
        print(f"\n{Colors.HEADER}{Colors.BOLD}--- iLoveQatar test mode finished ---{Colors.END}")
        return
    
    if args.visit_qatar:
        # Run Visit Qatar API mode
        print(f"{Colors.HEADER}{Colors.BOLD}🚀 Starting Visit Qatar API Events Fetcher 🚀{Colors.END}")
        _vq_run_start = time.time()
        
        # Fetch events from Visit Qatar API
        events = fetch_visit_qatar_events()
        
        if events:
            # Save events to JSON file
            with open('visit_qatar_events.json', 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
            
            print(f"\n{Colors.SUCCESS}✅ Successfully fetched {len(events)} events from Visit Qatar API!{Colors.END}")
            print(f"{Colors.INFO}Events saved to: visit_qatar_events.json{Colors.END}")
            
            # Show a sample of events
            print(f"\n{Colors.HEADER}🗺️  Sample events:{Colors.END}")
            for i, event in enumerate(events[:3]):  # Show first 3 events
                print(f"{Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{Colors.END}")
                print(f"   📍 {event.get('location', 'N/A')}")
                print(f"   🗓️ {event.get('date', 'N/A')}")
                print()
        else:
            print(f"\n{Colors.WARNING}No events were fetched from the Visit Qatar API.{Colors.END}")
        
        _dur = int(time.time() - _vq_run_start)
        print(f"{Colors.INFO}⏱️ Run duration: {_dur//60}:{_dur%60:02d}{Colors.END}")
        print(f"\n{Colors.HEADER}{Colors.BOLD}--- Visit Qatar API mode finished ---{Colors.END}")
        return
    
    # Original scraping mode
    print(f"{Colors.HEADER}{Colors.BOLD}🚀 Starting the Scraper & Analyzer Script 🚀{Colors.END}")
    _overall_run_start = time.time()
    # --- 1. Initialize the Firecrawl and Gemini clients ---
    # It's good practice to check if the API key is a placeholder.
    if not GOOGLE_API_KEY:
        print(f"{Colors.ERROR}GOOGLE_API_KEY environment variable is not set. Please set it with your actual key from Google AI Studio.{Colors.END}")
        return
    
    if "YOUR_GOOGLE_AI_API_KEY" in GOOGLE_API_KEY:
        print(f"{Colors.ERROR}Please replace the placeholder GOOGLE_API_KEY with your actual key from Google AI Studio.{Colors.END}")
        return
    try:
        # Initialize the FirecrawlApp to connect to your local instance.
        # No api_key is needed when providing an api_url.
        app = FirecrawlApp(api_url=FIRECRAWL_BASE_URL)
        # Configure the Google AI client
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
    except Exception as e:
        print(f"{Colors.ERROR}Error initializing clients: {e}{Colors.END}")
        print(f"{Colors.WARNING}For Firecrawl, ensure your local instance is running and accessible at the specified URL.{Colors.END}")
        return
    all_results = []
    failed_urls = []
    raw_content_dir = "scraped_pages"
    
    # Create directory for raw scraped content
    if not os.path.exists(raw_content_dir):
        os.makedirs(raw_content_dir)
        print(f"{Colors.INFO}Created directory: {raw_content_dir}{Colors.END}")
    
    # --- 2. Scrape each website using Firecrawl ---
    for i, target_url in enumerate(TARGET_URLS, 1):
        _url_run_start = time.time()
        try:
            print(f"\n{Colors.HEADER}🔎 Scraping Website {i}/{len(TARGET_URLS)}{Colors.END}")
            print(f"{Colors.INFO}URL: {target_url}{Colors.END}")

            # Special handling for Marhaba Qatar listings with pagination
            if 'marhaba.qa/events/' in target_url:
                try:
                    # Define page URL constructor for Marhaba
                    def marhaba_page_url_constructor(base_url, page_num):
                        if page_num == 1:
                            return base_url
                        return f"{base_url}page/{page_num}/"

                    scrape_with_pagination(
                        app=app,
                        starting_url=target_url,
                        raw_content_dir=raw_content_dir,
                        url_extractor=extract_marhaba_event_urls,
                        page_url_constructor=marhaba_page_url_constructor,
                    )
                except Exception as e:
                    print(f"{Colors.ERROR}An error occurred during Marhaba pagination scrape: {e}{Colors.END}")
                    failed_urls.append(target_url)
                # Skip generic scraping and analysis for listing pages
                continue
            # Special handling for iLoveQatar listings with pagination
            if 'iloveqatar.net/events' in target_url:
                try:
                    # Define page URL constructor for ILQ
                    def ilq_page_url_constructor(base_url, page_num):
                        if page_num == 1:
                            return base_url
                        sep = '&page=' if '?' in base_url else '?page='
                        return f"{base_url}{sep}{page_num}"

                    scrape_with_pagination(
                        app=app,
                        starting_url=target_url,
                        raw_content_dir=raw_content_dir,
                        url_extractor=extract_ilq_event_urls,
                        page_url_constructor=ilq_page_url_constructor,
                        max_pages=12,
                    )
                except Exception as e:
                    print(f"{Colors.ERROR}An error occurred during iLoveQatar pagination scrape: {e}{Colors.END}")
                    failed_urls.append(target_url)
                # Skip generic scraping and analysis for listing pages
                continue
            try:
                scraped_data = app.scrape_url(target_url, timeout=30000)
                if not scraped_data:
                    print(f"{Colors.ERROR}Failed to scrape {target_url} - no data returned.{Colors.END}")
                    failed_urls.append(target_url)
                    continue
                try:
                    markdown_content = scraped_data.markdown
                    if not markdown_content:
                        print(f"{Colors.WARNING}No markdown content found in the response for {target_url}.{Colors.END}")
                        failed_urls.append(target_url)
                        continue
                    print(f"{Colors.SUCCESS}Successfully scraped {len(markdown_content)} characters from {target_url}.{Colors.END}")

                    # Save raw scraped content to file (main page)
                    save_scraped_content(markdown_content, target_url, raw_content_dir)

                    # No special handling in generic flow anymore
                    pass
                except AttributeError:
                    print(f"{Colors.ERROR}Could not access markdown content from the response for {target_url}.{Colors.END}")
                    print(f"Available attributes: {dir(scraped_data)}")
                    failed_urls.append(target_url)
                    continue
            except Exception as e:
                print(f"{Colors.ERROR}An error occurred during scraping {target_url}: {e}{Colors.END}")
                failed_urls.append(target_url)
                continue
            # --- 3. Process the content with the Gemini LLM ---
            print(f"{Colors.INFO}🤖 Sending content to Gemini ({GEMINI_MODEL}) for general analysis...{Colors.END}")
            try:
                # Create a prompt for the LLM to extract structured information
                prompt_template = """
                Based on the following content from the events page, please extract key information 
                and return it in a structured JSON format. Include the following fields:
                - website_name: The name of the website
                - website_url: The URL of the website
                - page_type: The type of page (events, community, etc.)
                - current_events_status: Information about current events availability
                - main_sections: An array of main sections/categories on the website
                - navigation_menu: An array of navigation menu items
                - features: An array of main features or services offered
                - social_media: An array of social media platforms mentioned
                - contact_info: Any contact or support information
                - additional_notes: Any other relevant information about the events page
                Website Content:
                ---
                {content}
                ---
                Please return ONLY valid JSON without any additional text or formatting.
                """

                # Extract structured data with Gemini
                parsed_data = extract_events_with_gemini(markdown_content, prompt_template)

                if parsed_data:
                    print(f"\n{Colors.HEADER}📊 Extracted Information for {target_url} (JSON){Colors.END}")
                    print(f"{Colors.BLUE}{json.dumps(parsed_data[0] if parsed_data else {}, indent=2)}{Colors.END}")
                    print("-----------------------------------")
                    all_results.append(parsed_data[0] if parsed_data else {})
                else:
                    print(f"{Colors.WARNING}No structured data extracted for {target_url}{Colors.END}")

            except Exception as e:
                print(f"{Colors.ERROR}An error occurred while processing {target_url} with the Gemini model: {e}{Colors.END}")
                continue
        finally:
            _dur = int(time.time() - _url_run_start)
            print(f"{Colors.INFO}⏱️ Duration for this source: {_dur//60}:{_dur%60:02d}{Colors.END}")
    
    # --- 4. Process raw scraped content for event extraction ---
    print(f"\n{Colors.HEADER}🗓️  Processing all raw content for specific event extraction...{Colors.END}")
    all_events = []
    
    # Process each raw markdown file
    scraped_files = [f for f in os.listdir(raw_content_dir) if f.endswith('_scraped_content.md')]
    # Filter for Marhaba and iLoveQatar: include ONLY event detail pages, exclude listing root pages
    marhaba_event_prefix = 'marhaba_qa_event_'
    marhaba_listing_prefix = 'marhaba_qa_events_'
    ilq_event_prefix = 'www_iloveqatar_net_events_'
    ilq_listing_filename = 'www_iloveqatar_net_events_scraped_content.md'
    filtered_scraped_files = []
    for f in scraped_files:
        # Include Marhaba event detail pages only
        if f.startswith(marhaba_event_prefix):
            filtered_scraped_files.append(f)
        # Exclude Marhaba listing pages (events/...)
        elif f.startswith(marhaba_listing_prefix):
            continue
        # Include iLoveQatar event detail pages only; exclude the listing page filename
        elif f == ilq_listing_filename:
            continue
        elif f.startswith(ilq_event_prefix):
            filtered_scraped_files.append(f)
        # Include all non-Marhaba files
        else:
            filtered_scraped_files.append(f)
    scraped_files = filtered_scraped_files
    
    if not scraped_files:
        print(f"{Colors.WARNING}No scraped content files found in '{raw_content_dir}' to process.{Colors.END}")
        
    for filename in scraped_files:
        filepath = os.path.join(raw_content_dir, filename)
        print(f"{Colors.INFO}Processing raw content from: {filename}{Colors.END}")
        
        try:
            # Read the raw markdown content
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            # Extract the actual content (skip the header metadata)
            content_start = raw_content.find('==================================================')
            if content_start != -1:
                actual_content = raw_content[content_start + 52:]  # Skip the separator line
            else:
                actual_content = raw_content
            
            # Determine the source and apply appropriate extraction
            if filename.startswith(marhaba_event_prefix):
                # This is a Marhaba Qatar event detail page
                print(f"{Colors.INFO}Processing as Marhaba Qatar event detail page{Colors.END}")
                
                # Extract Marhaba event URLs from the raw content
                marhaba_event_urls = extract_marhaba_event_urls(raw_content)
                print(f"{Colors.INFO}Found {len(marhaba_event_urls)} Marhaba event URLs in {filename}{Colors.END}")
                for url in marhaba_event_urls:
                    print(f"    - {url}")
                
                # Create a Marhaba-specific prompt
                prompt_template = """
                Based on the following scraped content from a Marhaba Qatar event page, extract the event details and return them in a JSON array format.
                
                The event should have these exact fields:
                - name: The event title/name
                - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
                - time: The event time(s) in format "HH:MM AM/PM" or similar
                - location: The event venue/location
                - description: A brief description of the event
                - category: The event category (cultural, entertainment, sports, food, education, etc.)
                - url: The event URL if available, or website URL if not
                
                Content to analyze:
                ---
                {content}
                ---
                Return ONLY valid JSON array without any additional text or formatting.
                """
                
                # Extract events with Gemini
                events = extract_events_with_gemini(
                    actual_content,
                    prompt_template,
                    lambda events: [dict(event, source='Marhaba Qatar') for event in events]
                )
                
                all_events.extend(events)
                print(f"{Colors.SUCCESS}Extracted {len(events)} event(s) from {filename}{Colors.END}")
                
            elif filename.startswith(ilq_event_prefix):
                # This is an iLoveQatar event detail page
                print(f"{Colors.INFO}Processing as iLoveQatar event detail page{Colors.END}")
                
                # Extract iLoveQatar event URLs from the raw content
                ilq_event_urls = extract_ilq_event_urls(raw_content)
                print(f"{Colors.INFO}Found {len(ilq_event_urls)} iLoveQatar event URLs in {filename}{Colors.END}")
                for url in ilq_event_urls:
                    print(f"    - {url}")
                
                # Create an iLoveQatar-specific prompt
                prompt_template = """
                Based on the following scraped content from an iLoveQatar event page, extract the event details and return them in a JSON array format.
                
                The event should have these exact fields:
                - name: The event title/name
                - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
                - time: The event time(s) in format "HH:MM AM/PM" or similar
                - location: The event venue/location
                - description: A brief description of the event
                - category: The event category (cultural, entertainment, sports, food, education, etc.)
                - url: The event URL if available, or website URL if not
                
                Content to analyze:
                ---
                {content}
                ---
                Return ONLY valid JSON array without any additional text or formatting.
                """
                
                # Extract events with Gemini
                events = extract_events_with_gemini(
                    actual_content,
                    prompt_template,
                    lambda events: [dict(event, source='iLoveQatar') for event in events]
                )
                
                all_events.extend(events)
                print(f"{Colors.SUCCESS}Extracted {len(events)} event(s) from {filename}{Colors.END}")
                
            else:
                # Generic event extraction for other sources
                print(f"{Colors.INFO}Processing as generic event page{Colors.END}")
                
                # Create a generic prompt
                prompt_template = """
                Based on the following scraped content from an events page, extract all event details and return them in a JSON array format.
                
                Each event should have these exact fields:
                - name: The event title/name
                - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
                - time: The event time(s) in format "HH:MM AM/PM" or similar
                - location: The event venue/location
                - description: A brief description of the event
                - category: The event category (cultural, entertainment, sports, food, education, etc.)
                - url: The event URL if available, or website URL if not
                
                Content to analyze:
                ---
                {content}
                ---
                Return ONLY valid JSON array without any additional text or formatting.
                """
                
                # Extract events with Gemini
                events = extract_events_with_gemini(
                    actual_content,
                    prompt_template,
                    lambda events: [dict(event, source='Generic') for event in events]
                )
                
                all_events.extend(events)
                print(f"{Colors.SUCCESS}Extracted {len(events)} event(s) from {filename}{Colors.END}")
                
        except Exception as e:
            print(f"{Colors.ERROR}Error processing {filename}: {e}{Colors.END}")

    # --- 4.5. Geocode all newly extracted events before consolidation ---
    if all_events:
        print(f"\n{Colors.HEADER}🗺️  Geocoding all newly extracted events...{Colors.END}")
        all_events = add_coordinates_to_events(all_events)
    
    # --- 5. Consolidate all events into doha_events.json ---
    print(f"\n{Colors.HEADER}📝 Consolidating all events into doha_events.json...{Colors.END}")
    
    # Check if we have any event files to consolidate
    event_files = []
    if os.path.exists('doha_events.json'):
        event_files.append('doha_events.json')
    if os.path.exists('visit_qatar_events.json'):
        event_files.append('visit_qatar_events.json')

    # Also check for any event files in the raw_content_dir
    raw_event_files = [f for f in os.listdir(raw_content_dir) if f.endswith('_events.json')]
    for f in raw_event_files:
        event_files.append(os.path.join(raw_content_dir, f))

    consolidated_events = []

    for event_file in event_files:
        try:
            with open(event_file, 'r', encoding='utf-8') as f:
                events = json.load(f)
                if isinstance(events, list):
                    consolidated_events.extend(events)
                    print(f"{Colors.INFO}Added {len(events)} events from {event_file}{Colors.END}")
        except Exception as e:
            print(f"{Colors.ERROR}Error reading events from {event_file}: {e}{Colors.END}")

    # Add events extracted in this run
    if all_events:
        consolidated_events.extend(all_events)
        print(f"{Colors.INFO}Added {len(all_events)} events extracted in this run{Colors.END}")

    # Remove duplicates based on name and date
    unique_events = []
    seen_events = set()

    for event in consolidated_events:
        if isinstance(event, dict) and 'name' in event and 'date' in event:
            event_key = f"{event['name']}_{event['date']}"
            if event_key not in seen_events:
                seen_events.add(event_key)
                unique_events.append(event)

    if unique_events:
        with open('doha_events.json', 'w', encoding='utf-8') as f:
            json.dump(unique_events, f, indent=2, ensure_ascii=False)
        
        print(f"{Colors.SUCCESS}✅ Successfully consolidated {len(unique_events)} unique events into doha_events.json{Colors.END}")
        
        # Show a sample of events
        print(f"\n{Colors.HEADER}🗺️  Sample events:{Colors.END}")
        for i, event in enumerate(unique_events[:3]):
            print(f"{Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{Colors.END}")
            print(f"   � {event.get('location', 'N/A')}")
            print(f"   🗓️ {event.get('date', 'N/A')}")
            print()
    else:
        print(f"{Colors.WARNING}No events found to consolidate.{Colors.END}")
    
    # --- 6. Final summary ---
    print(f"\n{Colors.HEADER}{Colors.BOLD}📊 Scraping and Analysis Summary{Colors.END}")
    print(f"{Colors.INFO}Total websites processed: {len(TARGET_URLS)}{Colors.END}")
    print(f"{Colors.INFO}Total events extracted: {len(unique_events)}{Colors.END}")
    print(f"{Colors.INFO}Failed URLs: {len(failed_urls)}{Colors.END}")
    if failed_urls:
        print(f"{Colors.WARNING}Failed URLs:{Colors.END}")
        for url in failed_urls:
            print(f"  - {url}")
    
    _overall_dur = int(time.time() - _overall_run_start)
    print(f"{Colors.INFO}⏱️ Total run duration: {_overall_dur//60}:{_overall_dur%60:02d}{Colors.END}")
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- Script execution finished ---{Colors.END}")

if __name__ == "__main__":
    main()