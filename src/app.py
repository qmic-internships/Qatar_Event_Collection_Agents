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
import re
import threading
from datetime import datetime

try:
    # Try relative imports first (when run as part of a package)
    from .timestamp_utils import (
        parse_time_to_minutes,
        extract_date_range,
        extract_time_range_from_complex_string,
        convert_datetime_to_timestamps,
        convert_events_to_timestamps,
        save_raw_events_with_timestamps,
        save_events_in_correct_order
    )
    from . import geolocation
    # Import configuration from config.py
    from .config import (
        FIRECRAWL_BASE_URL,
        GOOGLE_API_KEY,
        TARGET_URLS,
        GEMINI_MODEL
    )
    # Import filtering functionality
    from .filters import (
        run_filter_and_deduplicate,
        ensure_location_fields
    )
    # Import URL extraction functionality
    from .URL_Extraction import (
        extract_marhaba_event_urls,
        extract_ilq_event_urls,
        extract_event_source_url,
        extract_ilq_visit_website_url,
        _normalize_tokens,
        _select_primary_event_by_slug_tokens,
        _ilq_reconstruct_event_path_from_filename,
        _is_u17_world_cup_individual_match
    )
except ImportError:
    # Fall back to direct imports (when run directly)
    from timestamp_utils import (
        parse_time_to_minutes,
        extract_date_range,
        extract_time_range_from_complex_string,
        convert_datetime_to_timestamps,
        convert_events_to_timestamps,
        save_raw_events_with_timestamps,
        save_events_in_correct_order
    )
    import geolocation
    # Import configuration from config.py
    from config import (
        FIRECRAWL_BASE_URL,
        GOOGLE_API_KEY,
        TARGET_URLS,
        GEMINI_MODEL
    )
    # Import filtering functionality
    from filters import (
        run_filter_and_deduplicate,
        ensure_location_fields
    )
    # Import URL extraction functionality
    from URL_Extraction import (
        extract_marhaba_event_urls,
        extract_ilq_event_urls,
        extract_event_source_url,
        extract_ilq_visit_website_url,
        _normalize_tokens,
        _select_primary_event_by_slug_tokens,
        _ilq_reconstruct_event_path_from_filename,
        _is_u17_world_cup_individual_match
    )

# Global flag to track if script is interrupted
interrupted = False
def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    global interrupted
    interrupted = True
    print(f"\n{geolocation.Colors.WARNING}⚠️  Interrupt signal received. Exiting immediately...{geolocation.Colors.END}")
    exit(0)
# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
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
        f.write(f"Scraped at: {time.strftime('%Y-%m-%d %H:%M:%S')}{geolocation.Colors.END}\n")
        f.write(f"Content length: {len(content)} characters\n")
        f.write("\n" + "="*50 + "\n\n")
        f.write(content)
    
    print(f"{geolocation.Colors.INFO}Saved content to: {filepath}{geolocation.Colors.END}")
    return filepath





def add_coordinates_to_events(events):
    """Add coordinates to event locations using Google Geocoding API."""
    if not events:
        return events
        
    print(f"\n{geolocation.Colors.HEADER}🗺️  Adding coordinates to event locations...{geolocation.Colors.END}")
    print(f"{geolocation.Colors.INFO}Processing {len(events)} events for geocoding...{geolocation.Colors.END}")
    
    try:
        for i, event in enumerate(events, 1):
            if interrupted:
                print(f"{geolocation.Colors.WARNING}⚠️  Stopping geocoding due to interrupt signal...{geolocation.Colors.END}")
                break
                
            # Use locationName as primary field, fallback to location for backward compatibility
            location_to_geocode = event.get('locationName') or event.get('location')
            
            if location_to_geocode:
                # Check if location already has coordinates (old format check)
                if not str(location_to_geocode).startswith('Location ('):
                    print(f"{geolocation.Colors.INFO}[{i}/{len(events)}] Processing event: {event.get('name', 'Unknown')}{geolocation.Colors.END}")
                    original_location = location_to_geocode
                    location_data = geolocation.get_location_coordinates(original_location)
                    
                    # Create the new location fields
                    event['locationLat'] = location_data['lat']
                    event['locationLng'] = location_data['lng']
                    event['locationName'] = location_data['name']
                    
                    time.sleep(0.5)
                else:
                    print(f"{geolocation.Colors.INFO}[{i}/{len(events)}] Event already has coordinates: {event.get('name', 'Unknown')}{geolocation.Colors.END}")
                    # Convert old format to new format if possible
                    old_location = location_to_geocode
                    # Try to extract coordinates from old format "Location (lat, lng) name"
                    import re
                    coord_match = re.search(r'Location \(([^,]+), ([^)]+)\) (.+)', old_location)
                    if coord_match:
                        try:
                            lat = float(coord_match.group(1))
                            lng = float(coord_match.group(2))
                            name = coord_match.group(3)
                            event['locationLat'] = lat
                            event['locationLng'] = lng
                            event['locationName'] = name
                        except ValueError:
                            event['locationLat'] = None
                            event['locationLng'] = None
                            event['locationName'] = old_location
                    else:
                        event['locationLat'] = None
                        event['locationLng'] = None
                        event['locationName'] = old_location
            else:
                # No location field, set defaults
                event['locationLat'] = None
                event['locationLng'] = None
                event['locationName'] = None
                    
            # Remove the location field from final output
            if 'location' in event:
                del event['location']
                    
    except KeyboardInterrupt:
        print(f"\n{geolocation.Colors.WARNING}⚠️  Geocoding process interrupted by user. Continuing with available data...{geolocation.Colors.END}")
    except Exception as e:
        print(f"\n{geolocation.Colors.ERROR}❌ Error during geocoding process: {e}{geolocation.Colors.END}")
        print(f"{geolocation.Colors.WARNING}Continuing with available data...{geolocation.Colors.END}")
    
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
        print(f"{geolocation.Colors.ERROR}Error parsing events from Gemini: {e}{geolocation.Colors.END}")
        print(f"{geolocation.Colors.WARNING}Raw response:{geolocation.Colors.END}")
        print(json_content)
        return []
    except Exception as e:
        print(f"{geolocation.Colors.ERROR}Error extracting events with Gemini: {e}{geolocation.Colors.END}")
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
    print(f"{geolocation.Colors.HEADER}🧭 Pagination scraping starting at: {starting_url}{geolocation.Colors.END}")
    collected_event_urls = []
    seen_event_urls = set()
    
    for page_number in range(1, max_pages + 1):
        if interrupted:
            print(f"{geolocation.Colors.WARNING}⚠️  Stopping pagination due to interrupt signal...{geolocation.Colors.END}")
            break
            
        page_url = page_url_constructor(starting_url, page_number) if page_url_constructor else starting_url
        print(f"{geolocation.Colors.INFO}🔎 Scraping listing page {page_number}: {page_url}{geolocation.Colors.END}")
        
        try:
            scraped = app.scrape_url(page_url, timeout=30000)
            if not scraped or not getattr(scraped, 'markdown', None):
                print(f"{geolocation.Colors.WARNING}No markdown content for listing page: {page_url}{geolocation.Colors.END}")
                if page_number > 1:
                    print(f"{geolocation.Colors.INFO}Assuming end of pagination after page {page_number}.{geolocation.Colors.END}")
                    break
                continue
                
            markdown_content = scraped.markdown
            
            # Save the listing page markdown
            save_scraped_content(markdown_content, page_url, raw_content_dir)
            
            # Extract event URLs from this listing page
            page_event_urls = url_extractor(markdown_content)
            print(f"{geolocation.Colors.INFO}Found {len(page_event_urls)} event links on page {page_number}.{geolocation.Colors.END}")
            
            # Stop condition: if no events found and we're past the first page, stop
            if len(page_event_urls) == 0 and page_number > 1:
                print(f"{geolocation.Colors.INFO}No events found on page {page_number}. Stopping pagination.{geolocation.Colors.END}")
                break
                
            for url in page_event_urls:
                if url not in seen_event_urls:
                    seen_event_urls.add(url)
                    collected_event_urls.append(url)
            
            # Be polite between pages
            time.sleep(0.3)
            
        except Exception as ex:
            print(f"{geolocation.Colors.WARNING}Failed to scrape listing page {page_url} | {ex}{geolocation.Colors.END}")
            if page_number > 1:
                print(f"{geolocation.Colors.INFO}Assuming end of pagination after page {page_number}.{geolocation.Colors.END}")
                break
    
    # Scrape each collected event detail page and save markdown
    print(f"{geolocation.Colors.HEADER}📝 Scraping {len(collected_event_urls)} event detail pages...{geolocation.Colors.END}")
    for index, event_url in enumerate(collected_event_urls, 1):
        if interrupted:
            print(f"{geolocation.Colors.WARNING}⚠️  Stopping event detail scraping due to interrupt signal...{geolocation.Colors.END}")
            break
            
        print(f"{geolocation.Colors.INFO}[{index}/{len(collected_event_urls)}] Scraping event: {event_url}{geolocation.Colors.END}")
        try:
            event_scraped = app.scrape_url(event_url, timeout=30000)
            if not event_scraped or not getattr(event_scraped, 'markdown', None):
                print(f"{geolocation.Colors.WARNING}No markdown content for event: {event_url}{geolocation.Colors.END}")
                continue
                
            event_markdown = event_scraped.markdown
            save_scraped_content(event_markdown, event_url, raw_content_dir)
            
            # Small delay to avoid hammering
            time.sleep(0.2)
            
        except Exception as event_ex:
            print(f"{geolocation.Colors.WARNING}Failed to scrape event detail page: {event_url} | {event_ex}{geolocation.Colors.END}")
    
    print(f"{geolocation.Colors.SUCCESS}✅ Pagination scraping completed. Total events collected: {len(collected_event_urls)}{geolocation.Colors.END}")
    return collected_event_urls

# Geolocation functionality has been moved to Geolocation.py module














# --- Main Script ---
def main():
    """
    Main function to scrape multiple URLs with a local Firecrawl instance and 
    process them with Google's Gemini model.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Qatar Events Scraper and Analyzer')
    parser.add_argument('--filter-events', action='store_true',
                       help='Filter events in doha_events.json for cultural appropriateness and expiration, then deduplicate.')
    args = parser.parse_args()
    
    if args.filter_events:
        # --- NEW: Event Filtering and Deduplication Mode ---
        run_filter_and_deduplicate()
        return
    
    # Original scraping mode
    print(f"{geolocation.Colors.HEADER}{geolocation.Colors.BOLD}🚀 Starting the Scraper & Analyzer Script 🚀{geolocation.Colors.END}")
    _overall_run_start = time.time()
    # --- 1. Initialize the Firecrawl and Gemini clients ---
    # It's good practice to check if the API key is a placeholder.
    if not GOOGLE_API_KEY:
        print(f"{geolocation.Colors.ERROR}GOOGLE_API_KEY environment variable is not set. Please set it with your actual key from Google AI Studio.{geolocation.Colors.END}")
        return
    
    if "YOUR_GOOGLE_AI_API_KEY" in GOOGLE_API_KEY:
        print(f"{geolocation.Colors.ERROR}Please replace the placeholder GOOGLE_API_KEY with your actual key from Google AI Studio.{geolocation.Colors.END}")
        return
    try:
        # Initialize the FirecrawlApp to connect to your local instance.
        # No api_key is needed when providing an api_url.
        app = FirecrawlApp(api_url=FIRECRAWL_BASE_URL)
        # Configure the Google AI client
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
    except Exception as e:
        print(f"{geolocation.Colors.ERROR}Error initializing clients: {e}{geolocation.Colors.END}")
        print(f"{geolocation.Colors.WARNING}For Firecrawl, ensure your local instance is running and accessible at the specified URL.{geolocation.Colors.END}")
        return
    all_results = []
    failed_urls = []
    # Ensure scraped_pages directory is created in project root, not src
    project_root = os.path.dirname(os.path.dirname(__file__))
    raw_content_dir = os.path.join(project_root, "scraped_pages")
    
    # Create directory for raw scraped content
    if not os.path.exists(raw_content_dir):
        os.makedirs(raw_content_dir)
        print(f"{geolocation.Colors.INFO}Created directory: {raw_content_dir}{geolocation.Colors.END}")
    
    # --- 2. Scrape each website using Firecrawl ---
    for i, target_url in enumerate(TARGET_URLS, 1):
        _url_run_start = time.time()
        try:
            print(f"\n{geolocation.Colors.HEADER}🔎 Scraping Website {i}/{len(TARGET_URLS)}{geolocation.Colors.END}")
            print(f"{geolocation.Colors.INFO}URL: {target_url}{geolocation.Colors.END}")

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
                    print(f"{geolocation.Colors.ERROR}An error occurred during Marhaba pagination scrape: {e}{geolocation.Colors.END}")
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
                    print(f"{geolocation.Colors.ERROR}An error occurred during iLoveQatar pagination scrape: {e}{geolocation.Colors.END}")
                    failed_urls.append(target_url)
                # Skip generic scraping and analysis for listing pages
                continue
            try:
                scraped_data = app.scrape_url(target_url, timeout=30000)
                if not scraped_data:
                    print(f"{geolocation.Colors.ERROR}Failed to scrape {target_url} - no data returned.{geolocation.Colors.END}")
                    failed_urls.append(target_url)
                    continue
                try:
                    markdown_content = scraped_data.markdown
                    if not markdown_content:
                        print(f"{geolocation.Colors.WARNING}No markdown content found in the response for {target_url}.{geolocation.Colors.END}")
                        failed_urls.append(target_url)
                        continue
                    print(f"{geolocation.Colors.SUCCESS}Successfully scraped {len(markdown_content)} characters from {target_url}.{geolocation.Colors.END}")

                    # Save raw scraped content to file (main page)
                    save_scraped_content(markdown_content, target_url, raw_content_dir)

                    # No special handling in generic flow anymore
                    pass
                except AttributeError:
                    print(f"{geolocation.Colors.ERROR}Could not access markdown content from the response for {target_url}.{geolocation.Colors.END}")
                    print(f"Available attributes: {dir(scraped_data)}")
                    failed_urls.append(target_url)
                    continue
            except Exception as e:
                print(f"{geolocation.Colors.ERROR}An error occurred during scraping {target_url}: {e}{geolocation.Colors.END}")
                failed_urls.append(target_url)
                continue
            # --- 3. Process the content with the Gemini LLM ---
            print(f"{geolocation.Colors.INFO}🤖 Sending content to Gemini ({GEMINI_MODEL}) for general analysis...{geolocation.Colors.END}")
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
                    print(f"\n{geolocation.Colors.HEADER}📊 Extracted Information for {target_url} (JSON){geolocation.Colors.END}")
                    print(f"{geolocation.Colors.BLUE}{json.dumps(parsed_data[0] if parsed_data else {}, indent=2)}{geolocation.Colors.END}")
                    print("-----------------------------------")
                    all_results.append(parsed_data[0] if parsed_data else {})
                else:
                    print(f"{geolocation.Colors.WARNING}No structured data extracted for {target_url}{geolocation.Colors.END}")

            except Exception as e:
                print(f"{geolocation.Colors.ERROR}An error occurred while processing {target_url} with the Gemini model: {e}{geolocation.Colors.END}")
                continue
        finally:
            _dur = int(time.time() - _url_run_start)
            print(f"{geolocation.Colors.INFO}⏱️ Duration for this source: {_dur//60}:{_dur%60:02d}{geolocation.Colors.END}")
    
    # --- 4. Process raw scraped content for event extraction ---
    print(f"\n{geolocation.Colors.HEADER}🗓️  Processing all raw content for specific event extraction...{geolocation.Colors.END}")
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
        print(f"{geolocation.Colors.WARNING}No scraped content files found in '{raw_content_dir}' to process.{geolocation.Colors.END}")
        
    for filename in scraped_files:
        filepath = os.path.join(raw_content_dir, filename)
        print(f"{geolocation.Colors.INFO}Processing raw content from: {filename}{geolocation.Colors.END}")
        
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
                print(f"{geolocation.Colors.INFO}Processing as Marhaba Qatar event detail page{geolocation.Colors.END}")
                
                # Extract Marhaba event URLs from the raw content
                marhaba_event_urls = extract_marhaba_event_urls(raw_content)
                print(f"{geolocation.Colors.INFO}Found {len(marhaba_event_urls)} Marhaba event URLs in {filename}{geolocation.Colors.END}")
                for url in marhaba_event_urls:
                    print(f"    - {url}")
                
                # Create a Marhaba-specific prompt
                prompt_template = """
                Based on the following scraped content from a Marhaba Qatar event page, extract the event details and return them in a JSON array format.
                
                The event should have these exact fields:
                - name: The event title/name
                - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
                - time: The event time(s) in format "HH:MM AM/PM" or similar
                - locationName: The event venue/location name
                - locationLat: Set to null initially (will be populated with latitude coordinates)
                - locationLng: Set to null initially (will be populated with longitude coordinates)
                - description: A brief description of the event
                - category: The event category (cultural, entertainment, sports, food, education, etc.)
                - website: The event organizer's original website URL from the direct link button (not the Marhaba page)
                - image: The URL of the main event image/poster (extract from img tags, look for event-specific images, not logos or icons)
                
                IMPORTANT: For the description field, include detailed location information such as:
                - Full venue address
                - Contact phone numbers
                - Any specific location details
                - This will be used to populate locationDescription and locationPhone fields
                
                For the image field:
                - Extract the main event image URL from img tags in the content
                - Look for images that represent the event itself (posters, banners, promotional images)
                - Ignore logos, icons, social media icons, and advertisement images
                - If multiple event images exist, choose the largest or most prominent one
                - If no event-specific image is found, set to null
                
                Content to analyze:
                ---
                {content}
                ---
                
                Important: Look for a button or link that goes directly to the event organizer's official website. 
                Do NOT use the Marhaba event page URL. If no direct link to the official website is found, set website to null.
                
                IMPORTANT: Preserve the original date and time text exactly as provided. These will be converted to Unix timestamps later.
                Do not modify or strip any time specification details from the description field.
                
                Return ONLY valid JSON array without any additional text or formatting.
                """
                
                # Extract events with Gemini
                events = extract_events_with_gemini(
                    actual_content,
                    prompt_template,
                    lambda events: [dict(event, source='Marhaba Qatar') for event in events]
                )
                
                all_events.extend(events)
                print(f"{geolocation.Colors.SUCCESS}Extracted {len(events)} event(s) from {filename}{geolocation.Colors.END}")
                
            elif filename.startswith(ilq_event_prefix):
                # This is an iLoveQatar event detail page
                print(f"{geolocation.Colors.INFO}Processing as iLoveQatar event detail page{geolocation.Colors.END}")
                
                # Extract iLoveQatar event URLs from the raw content
                ilq_event_urls = extract_ilq_event_urls(raw_content)
                print(f"{geolocation.Colors.INFO}Found {len(ilq_event_urls)} iLoveQatar event URLs in {filename}{geolocation.Colors.END}")
                for url in ilq_event_urls:
                    print(f"    - {url}")
                
                # Create an iLoveQatar-specific prompt
                prompt_template = """
                Based on the following scraped content from an iLoveQatar event page, extract the events details and return them in a JSON array format.
                
                The event should have these exact fields:
                - name: The event title/name
                - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
                - time: The event time(s) in format "HH:MM AM/PM" or similar
                - locationName: The event venue/location name
                - locationLat: Set to null initially (will be populated with latitude coordinates)
                - locationLng: Set to null initially (will be populated with longitude coordinates)
                - description: A brief description of the event
                - category: The event category (cultural, entertainment, sports, food, education, etc.)
                - website: The event organizer's original website URL from the direct link button (not the iLoveQatar page)
                - image: The URL of the main event image/poster (extract from img tags, look for event-specific images, not logos or icons)
                
                IMPORTANT: For the description field, include detailed location information such as:
                - Full venue address
                - Contact phone numbers
                - Any specific location details
                - This will be used to populate locationDescription and locationPhone fields
                
                For the image field:
                - Extract the main event image URL from img tags in the content
                - Look for images that represent the event itself (posters, banners, promotional images)
                - Ignore logos, icons, social media icons, and advertisement images
                - If multiple event images exist, choose the largest or most prominent one
                - If no event-specific image is found, set to null
                
                Content to analyze:
                ---
                {content}
                ---
                
                Important: Look for a button or link that goes directly to the event organizer's official website. 
                Do NOT use the iLoveQatar event page URL. If no direct link to the official website is found, set website to null.
                
                IMPORTANT: Preserve the original date and time text exactly as provided. These will be converted to Unix timestamps later.
                Do not modify or strip any time specification details from the description field.
                
                Return ONLY valid JSON array without any additional text or formatting.
                """
                
                # Extract events with Gemini
                events = extract_events_with_gemini(
                    actual_content,
                    prompt_template,
                    lambda events: [dict(event, source='iLoveQatar') for event in events]
                )
                
                all_events.extend(events)
                print(f"{geolocation.Colors.SUCCESS}Extracted {len(events)} event(s) from {filename}{geolocation.Colors.END}")
                
            else:
                # Generic event extraction for other sources
                print(f"{geolocation.Colors.INFO}Processing as generic event page{geolocation.Colors.END}")
                
                # Create a generic prompt
                prompt_template = """
                Based on the following scraped content from an events page, extract all event details and return them in a JSON array format.
                
                Each event should have these exact fields:
                - name: The event title/name
                - date: The event date(s) in format "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD" for multi-day events
                - time: The event time(s) in format "HH:MM AM/PM" or similar
                - locationName: The event venue/location name
                - locationLat: Set to null initially (will be populated with latitude coordinates)
                - locationLng: Set to null initially (will be populated with longitude coordinates)
                - description: A brief description of the event
                - category: The event category (cultural, entertainment, sports, food, education, etc.)
                - website: The event organizer's original website URL (not the current page URL)
                - image: The URL of the main event image/poster (extract from img tags, look for event-specific images, not logos or icons)
                
                IMPORTANT: For the description field, include detailed location information such as:
                - Full venue address
                - Contact phone numbers
                - Any specific location details
                - This will be used to populate locationDescription and locationPhone fields
                
                For the image field:
                - Extract the main event image URL from img tags in the content
                - Look for images that represent the event itself (posters, banners, promotional images)
                - Ignore logos, icons, social media icons, and advertisement images
                - If multiple event images exist, choose the largest or most prominent one
                - If no event-specific image is found, set to null
                
                Content to analyze:
                ---
                {content}
                ---
                
                Important: Look for links that go directly to the event organizer's official website. 
                Do NOT use the current page URL. If no direct link to the official website is found, set website to null.
                
                IMPORTANT: Preserve the original date and time text exactly as provided. These will be converted to Unix timestamps later.
                Do not modify or strip any time specification details from the description field.
                
                Return ONLY valid JSON array without any additional text or formatting.
                """
                
                # Extract events with Gemini
                events = extract_events_with_gemini(
                    actual_content,
                    prompt_template,
                    lambda events: [dict(event, source='Generic') for event in events]
                )
                
                all_events.extend(events)
                print(f"{geolocation.Colors.SUCCESS}Extracted {len(events)} event(s) from {filename}{geolocation.Colors.END}")
                
        except Exception as e:
            print(f"{geolocation.Colors.ERROR}Error processing {filename}: {e}{geolocation.Colors.END}")

    # --- 4.5. Geocode all newly extracted events before consolidation ---
    if all_events:
        print(f"\n{geolocation.Colors.HEADER}🗺️  Geocoding all newly extracted events...{geolocation.Colors.END}")
        all_events = add_coordinates_to_events(all_events)
    
    # --- 5. Consolidate all events using two-step processing ---
    print(f"\n{geolocation.Colors.HEADER}📝 Consolidating all events using two-step processing...{geolocation.Colors.END}")
    
    # Check if we have any event files to consolidate
    project_root = os.path.dirname(os.path.dirname(__file__))
    collected_events_dir = os.path.join(project_root, 'Collected Events')
    os.makedirs(collected_events_dir, exist_ok=True)
    event_files = []
    events_01_raw_path = os.path.join(collected_events_dir, 'events_01_raw.json')
    
    if os.path.exists(events_01_raw_path):
        event_files.append(events_01_raw_path)

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
                    print(f"{geolocation.Colors.INFO}Added {len(events)} events from {event_file}{geolocation.Colors.END}")
        except Exception as e:
            print(f"{geolocation.Colors.ERROR}Error reading events from {event_file}: {e}{geolocation.Colors.END}")

    # Add events extracted in this run
    if all_events:
        consolidated_events.extend(all_events)
        print(f"{geolocation.Colors.INFO}Added {len(all_events)} events extracted in this run{geolocation.Colors.END}")

    # Ensure all events have the new location fields
    if consolidated_events:
        print(f"\n{geolocation.Colors.HEADER}🔧 Ensuring all events have required location fields...{geolocation.Colors.END}")
        consolidated_events = ensure_location_fields(consolidated_events)

    # Remove duplicates based on name and date (for raw events)
    unique_events = []
    seen_events = set()

    for event in consolidated_events:
        if isinstance(event, dict) and 'name' in event:
            # Use date if available, otherwise use startTimestamp for deduplication
            if 'date' in event:
                event_key = f"{event['name']}_{event['date']}"
            elif 'startTimestamp' in event:
                event_key = f"{event['name']}_{event['startTimestamp']}"
            else:
                # Skip events without date or timestamp
                continue
                
            if event_key not in seen_events:
                seen_events.add(event_key)
                unique_events.append(event)

    if unique_events:
        # Use the new two-step processing function
        filtered_count = save_raw_events_with_timestamps(unique_events)
        
        # Also save events in the correct order for events_01_raw.json
        save_events_in_correct_order(unique_events, os.path.join(collected_events_dir, 'events_01_raw.json'))
        
        print(f"{geolocation.Colors.SUCCESS}✅ Successfully processed {len(unique_events)} raw events and created filtered version with {filtered_count} valid events{geolocation.Colors.END}")
        print(f"{geolocation.Colors.SUCCESS}✅ Also saved events in correct order to events_01_raw.json{geolocation.Colors.END}")
        
        # Show a sample of raw events
        print(f"\n{geolocation.Colors.HEADER}🗺️  Sample raw events (with original date/time):{geolocation.Colors.END}")
        for i, event in enumerate(unique_events[:3]):
            print(f"{geolocation.Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{geolocation.Colors.END}")
            print(f"   📍 Location: {event.get('locationName', 'N/A')}")
            print(f"   🗺️  Coordinates: {event.get('locationLat', 'N/A')}, {event.get('locationLng', 'N/A')}")
            print(f"   🗓️  Date: {event.get('date', 'N/A')}")
            print(f"   🕐 Time: {event.get('time', 'N/A')}")
            print(f"   🕐 Start Timestamp: {event.get('startTimestamp', 'N/A')}")
            print()
        
        # --- Automatically run filtering and deduplication on the filtered file ---
        print(f"\n{geolocation.Colors.HEADER}🔄 Running filtering and deduplication on timestamped events...{geolocation.Colors.END}")
        run_filter_and_deduplicate()
    else:
        print(f"{geolocation.Colors.WARNING}No events found to consolidate.{geolocation.Colors.END}")
    
    # --- 6. Final summary ---
    print(f"\n{geolocation.Colors.HEADER}{geolocation.Colors.BOLD}📊 Scraping and Analysis Summary{geolocation.Colors.END}")
    print(f"{geolocation.Colors.INFO}Total websites processed: {len(TARGET_URLS)}{geolocation.Colors.END}")
    print(f"{geolocation.Colors.INFO}Total events extracted: {len(unique_events)}{geolocation.Colors.END}")
    print(f"{geolocation.Colors.INFO}Failed URLs: {len(failed_urls)}{geolocation.Colors.END}")
    if failed_urls:
        print(f"{geolocation.Colors.WARNING}Failed URLs:{geolocation.Colors.END}")
        for url in failed_urls:
            print(f"  - {url}")
    
    _overall_dur = int(time.time() - _overall_run_start)
    print(f"{geolocation.Colors.INFO}⏱️ Total run duration: {_overall_dur//60}:{_overall_dur%60:02d}{geolocation.Colors.END}")
    print(f"\n{geolocation.Colors.HEADER}{geolocation.Colors.BOLD}--- Script execution finished ---{geolocation.Colors.END}")

if __name__ == "__main__":
    main()