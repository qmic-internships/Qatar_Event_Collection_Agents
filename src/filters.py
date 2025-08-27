# filters.py
#
# Event filtering and deduplication functionality
# This module contains all filtering operations that were previously in app.py

import os
import json
import time
import re
from datetime import datetime
import google.generativeai as genai

try:
    # Try relative imports first (when run as part of a package)
    from . import geolocation
    from .config import GOOGLE_API_KEY, GEMINI_MODEL
    from .timestamp_utils import convert_events_to_correct_order
except ImportError:
    # Fall back to direct imports (when run directly)
    import geolocation
    from config import GOOGLE_API_KEY, GEMINI_MODEL
    from timestamp_utils import convert_events_to_correct_order

# Global flag to track if script is interrupted (shared with main app)
interrupted = False

def get_normalized_name(name):
    """Converts a name to a simplified, comparable format for deduplication."""
    if not name:
        return ""
    # Convert to lowercase and keep only letters and numbers
    return re.sub(r'[^a-z0-9]+', '', name.lower())

def intelligent_deduplication(events):
    """
    Groups events by location and startTimestamp, then selects the best event from each group.
    The "best" event is the one with the longest description.
    """
    if not events:
        return []

    print(f"\n{geolocation.Colors.HEADER}🧠 Performing intelligent deduplication on {len(events)} events...{geolocation.Colors.END}")
    
    event_groups = {}

    for event in events:
        # Use a reliable key: location coordinates + startTimestamp
        # This handles cases where the key exists but is None, or is missing entirely.
        location_name = event.get('locationName') or event.get('location') or ''
        start_timestamp = event.get('startTimestamp')
        
        # Extract coordinates if available for a more robust key
        lat = event.get('locationLat')
        lng = event.get('locationLng')
        
        if lat is not None and lng is not None:
            # Use the coordinates as the primary location key
            key_location = f"{lat:.6f}_{lng:.6f}"
        else:
            # Fallback to a normalized location name if no coordinates exist
            key_location = get_normalized_name(location_name)

        # Create a unique key for each event group using startTimestamp + location
        if start_timestamp is not None:
            group_key = f"{key_location}_{start_timestamp}"
        else:
            # Fallback to date + location for events without timestamps
            date = event.get('date') or ''
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
        print(f"{geolocation.Colors.SUCCESS}✅ Merged {duplicates_found} duplicate events.{geolocation.Colors.END}")
    else:
        print(f"{geolocation.Colors.INFO}No duplicates were found to merge.{geolocation.Colors.END}")
        
    print(f"{geolocation.Colors.INFO}Total unique events after deduplication: {len(final_unique_events)}{geolocation.Colors.END}")
    
    return final_unique_events

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
        print(f"{geolocation.Colors.ERROR}Input file {input_file} does not exist.{geolocation.Colors.END}")
        return 0

    print(f"{geolocation.Colors.HEADER}🔍 Loading events from {input_file} for filtering...{geolocation.Colors.END}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            events = json.load(f)

        if not events:
            print(f"{geolocation.Colors.WARNING}No events found in {input_file}.{geolocation.Colors.END}")
            return 0

        # Ensure all events have the new location fields
        print(f"{geolocation.Colors.INFO}Ensuring all events have required location fields...{geolocation.Colors.END}")
        events = ensure_location_fields(events)

        print(f"{geolocation.Colors.INFO}Loaded {len(events)} events for filtering.{geolocation.Colors.END}")

        # Configure Gemini
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)

        all_filtered_events = []
        event_batches = [events[i:i + batch_size] for i in range(0, len(events), batch_size)]
        num_batches = len(event_batches)

        print(f"{geolocation.Colors.INFO}Splitting events into {num_batches} batches of up to {batch_size} events each.{geolocation.Colors.END}")

        for i, batch in enumerate(event_batches, 1):
            if interrupted:
                print(f"{geolocation.Colors.WARNING}⚠️  Stopping filtering due to interrupt signal...{geolocation.Colors.END}")
                break

            print(f"\n{geolocation.Colors.INFO}Processing batch {i}/{num_batches}...{geolocation.Colors.END}")

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
                    print(f"{geolocation.Colors.ERROR}Batch {i}/{num_batches}: Unexpected response format. Expected a list.{geolocation.Colors.END}")
                    continue

                # Validate and add to the main list
                valid_batch_events = []
                for event in filtered_batch:
                    if isinstance(event, dict) and 'name' in event:
                        # Check if event has either date or startTimestamp
                        if 'date' in event or 'startTimestamp' in event:
                            valid_batch_events.append(event)
                        else:
                            print(f"{geolocation.Colors.WARNING}Batch {i}/{num_batches}: Skipping event missing both date and startTimestamp: {event}{geolocation.Colors.END}")
                    else:
                        print(f"{geolocation.Colors.WARNING}Batch {i}/{num_batches}: Skipping invalid event structure: {event}{geolocation.Colors.END}")

                all_filtered_events.extend(valid_batch_events)
                print(f"{geolocation.Colors.SUCCESS}✅ Batch {i}/{num_batches}: Successfully processed. Found {len(valid_batch_events)} valid events.{geolocation.Colors.END}")

            except json.JSONDecodeError as e:
                print(f"{geolocation.Colors.ERROR}Batch {i}/{num_batches}: Error parsing filtered events from Gemini: {e}{geolocation.Colors.END}")
                print(f"{geolocation.Colors.WARNING}Raw response for batch {i}:{geolocation.Colors.END}\n{json_content}")
            except Exception as e:
                print(f"{geolocation.Colors.ERROR}Batch {i}/{num_batches}: Error filtering events with Gemini: {e}{geolocation.Colors.END}")

            # Be polite to the API
            time.sleep(1)

        print(f"\n{geolocation.Colors.SUCCESS}✅ Successfully finished processing all batches.{geolocation.Colors.END}")
        print(f"{geolocation.Colors.INFO}Original events: {len(events)}{geolocation.Colors.END}")
        print(f"{geolocation.Colors.INFO}Total valid filtered events: {len(all_filtered_events)}{geolocation.Colors.END}")
        print(f"{geolocation.Colors.INFO}Filtered out: {len(events) - len(all_filtered_events)} events{geolocation.Colors.END}")

        # Save the final consolidated list of filtered events
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_filtered_events, f, indent=2, ensure_ascii=False)

        print(f"{geolocation.Colors.INFO}Filtered events saved to: {output_file}{geolocation.Colors.END}")

        # Show a sample of filtered events
        if all_filtered_events:
            print(f"\n{geolocation.Colors.HEADER}🗺️  Sample filtered events:{geolocation.Colors.END}")
            for i, event in enumerate(all_filtered_events[:3]):
                print(f"{geolocation.Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{geolocation.Colors.END}")
                print(f"   📍 Location: {event.get('locationName', 'N/A')}")
                print(f"   🗺️  Coordinates: {event.get('locationLat', 'N/A')}, {event.get('locationLng', 'N/A')}")
                print(f"   🗓️  Date: {event.get('date', 'N/A')}")
                print()

        return len(all_filtered_events)

    except Exception as e:
        print(f"{geolocation.Colors.ERROR}An unexpected error occurred in the filtering process: {e}{geolocation.Colors.END}")
        return 0

def ensure_location_fields(events):
    """Ensure all events have the required fields including the new location fields."""
    if not events:
        return events
        
    for event in events:
        if isinstance(event, dict):
            # Ensure all required fields exist in the correct order
            # 1. name: event name
            if 'name' not in event:
                event['name'] = ''
                
            # 2. description: event description 
            if 'description' not in event:
                event['description'] = ''
                
            # 3. categoryId: event category name
            if 'categoryId' not in event:
                # Try to get from category field for backward compatibility
                if 'category' in event:
                    event['categoryId'] = event['category']
                else:
                    event['categoryId'] = ''
            # Ensure categoryId is properly set from category if it exists
            elif 'category' in event and event['category'] and not event['categoryId']:
                event['categoryId'] = event['category']
                    
            # 4. startTimestamp: event start time in seconds
            if 'startTimestamp' not in event:
                event['startTimestamp'] = None
                
            # 5. endTimestamp: event end time in seconds 
            if 'endTimestamp' not in event:
                event['endTimestamp'] = None
                
            # 6. locationLat: event location latitude
            if 'locationLat' not in event:
                event['locationLat'] = None
                
            # 7. locationLng: event location longitude
            if 'locationLng' not in event:
                event['locationLng'] = None
                
            # 8. locationDescription: event location description (optional)
            if 'locationDescription' not in event:
                # Try to extract location description from description field
                location_description = None
                if 'description' in event and event['description']:
                    desc = event['description']
                    # Look for location-related information in the description
                    if 'Location:' in desc or 'Venue:' in desc or 'Address:' in desc:
                        location_match = re.search(r'(?:Location|Venue|Address):\s*([^\n]+)', desc)
                        if location_match:
                            location_description = location_match.group(1).strip()
                event['locationDescription'] = location_description
                
            # 9. locationName: event location name 
            if 'locationName' not in event:
                # Try to get from location field for backward compatibility
                if 'location' in event and event['location']:
                    event['locationName'] = event['location']
                else:
                    event['locationName'] = ''
                    
            # 10. locationPhone: event location phone number
            if 'locationPhone' not in event:
                # Try to extract phone number from description field
                location_phone = None
                if 'description' in event and event['description']:
                    desc = event['description']
                    # Look for phone numbers
                    phone_match = re.search(r'(?:Phone|Tel|Contact):\s*([+\d\s\-\(\)]+)', desc)
                    if phone_match:
                        location_phone = phone_match.group(1).strip()
                    # Also look for WhatsApp numbers
                    whatsapp_match = re.search(r'WhatsApp:\s*([+\d\s\-\(\)]+)', desc)
                    if whatsapp_match:
                        location_phone = f"WhatsApp: {whatsapp_match.group(1).strip()}"
                event['locationPhone'] = location_phone
                
            # 11. website: event website
            if 'website' not in event:
                # Handle field name change from "url" to "website" for backward compatibility
                if 'url' in event:
                    event['website'] = event['url']
                    del event['url']
                else:
                    event['website'] = ''
                    
            # 12. image: event image URL
            if 'image' not in event:
                event['image'] = None
                    
            # If we have coordinates but no name, try to get it from the location field
            if event['locationLat'] and event['locationLng'] and not event['locationName']:
                if 'location' in event and event['location']:
                    event['locationName'] = event['location']
                    
            # Remove the location field from final output
            if 'location' in event:
                del event['location']
                    
    return events

def run_filter_and_deduplicate():
    """Runs the event filtering and deduplication process on timestamped events."""
    print(f"\n{geolocation.Colors.HEADER}{geolocation.Colors.BOLD}🚀 Starting Event Filtering & Deduplication on Timestamped Events 🚀{geolocation.Colors.END}")
    _filter_run_start = time.time()
    
    # Ensure JSON files are created in 'Collected Events' folder, not src
    project_root = os.path.dirname(os.path.dirname(__file__))
    collected_events_dir = os.path.join(project_root, 'Collected Events')
    os.makedirs(collected_events_dir, exist_ok=True)
    input_filename = os.path.join(collected_events_dir, 'events_02_processed.json')  # Use the processed events file
    intermediate_filename = os.path.join(collected_events_dir, 'events_03_curated.json')
    final_filename = os.path.join(collected_events_dir, 'events_04_final.json')

    # Step 1: Filter events using Gemini (cultural appropriateness and expiration)
    filtered_count = filter_events_with_gemini(input_filename, intermediate_filename)
    
    if filtered_count > 0:
        # Step 2: Load the filtered events
        print(f"\n{geolocation.Colors.HEADER}🔄 Loading culturally filtered events for deduplication...{geolocation.Colors.END}")
        try:
            with open(intermediate_filename, 'r', encoding='utf-8') as f:
                events_to_deduplicate = json.load(f)
            
            # Ensure all events have the new location fields before deduplication
            print(f"{geolocation.Colors.INFO}Ensuring all events have required location fields...{geolocation.Colors.END}")
            events_to_deduplicate = ensure_location_fields(events_to_deduplicate)
            
            # Step 3: Run intelligent deduplication using startTimestamp + location
            final_events = intelligent_deduplication(events_to_deduplicate)
            
            # Step 4: Save the final, clean list in correct order
            final_events_ordered = convert_events_to_correct_order(final_events)
            with open(final_filename, 'w', encoding='utf-8') as f:
                json.dump(final_events_ordered, f, indent=2, ensure_ascii=False)
            
            print(f"\n{geolocation.Colors.SUCCESS}✅ Final, deduplicated events saved to: {final_filename}{geolocation.Colors.END}")

            # Show a sample of final events
            if final_events:
                print(f"\n{geolocation.Colors.HEADER}🗺️  Sample final events (with timestamps):{geolocation.Colors.END}")
                for i, event in enumerate(final_events[:3]):
                    print(f"{geolocation.Colors.BLUE}{i+1}. {event.get('name', 'N/A')}{geolocation.Colors.END}")
                    print(f"   📍 Location: {event.get('locationName', 'N/A')}")
                    print(f"   🗺️  Coordinates: {event.get('locationLat', 'N/A')}, {event.get('locationLng', 'N/A')}")
                    print(f"   🕐 Start: {event.get('startTimestamp', 'N/A')} ({datetime.fromtimestamp(event.get('startTimestamp', 0)).strftime('%Y-%m-%d %H:%M') if event.get('startTimestamp') else 'N/A'})")
                    print(f"   🕐 End: {event.get('endTimestamp', 'N/A')} ({datetime.fromtimestamp(event.get('endTimestamp', 0)).strftime('%Y-%m-%d %H:%M') if event.get('endTimestamp') else 'N/A'})")
                    print()

        except FileNotFoundError:
            print(f"{geolocation.Colors.ERROR}Could not find intermediate file {intermediate_filename} to deduplicate.{geolocation.Colors.END}")
        except Exception as e:
            print(f"{geolocation.Colors.ERROR}An error occurred during deduplication: {e}{geolocation.Colors.END}")
    else:
        print(f"{geolocation.Colors.WARNING}Filtering produced no events. Skipping deduplication.{geolocation.Colors.END}")

    _dur = int(time.time() - _filter_run_start)
    print(f"{geolocation.Colors.INFO}⏱️ Filtering & Deduplication duration: {_dur//60}:{_dur%60:02d}{geolocation.Colors.END}")
    print(f"\n{geolocation.Colors.HEADER}{geolocation.Colors.BOLD}--- Event filtering & deduplication finished ---{geolocation.Colors.END}")
