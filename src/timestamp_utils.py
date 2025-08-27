#!/usr/bin/env python3
"""
Timestamp utility functions for the Event Collection Agent.
Handles conversion of various date/time formats to Unix timestamps.
"""

from datetime import datetime, timedelta, timezone
import re

# Qatar timezone is UTC+3
QATAR_TIMEZONE = timezone(timedelta(hours=3))

def get_qatar_datetime(date_obj, hour=0, minute=0, second=0):
    """
    Create a timezone-aware datetime object in Qatar time (UTC+3).
    This ensures all timestamps are generated in Qatar time, not local system time.
    """
    # Create naive datetime object
    naive_dt = date_obj.replace(hour=hour, minute=minute, second=second, microsecond=0)
    
    # Make it timezone-aware in Qatar time
    qatar_dt = naive_dt.replace(tzinfo=QATAR_TIMEZONE)
    
    return qatar_dt

def convert_to_qatar_timestamp(date_obj, hour=0, minute=0, second=0):
    """
    Convert a date and time to Unix timestamp in Qatar time (UTC+3).
    This ensures consistency regardless of the system's local timezone.
    """
    qatar_dt = get_qatar_datetime(date_obj, hour, minute, second)
    return int(qatar_dt.timestamp())


def parse_time_to_minutes(time_str):
    """Convert time string (e.g., '2:30 PM') to minutes since midnight."""
    if not time_str or not isinstance(time_str, str):
        return 0
    
    # Handle special cases
    time_str = time_str.strip().upper()
    if time_str in ['TBA', 'TBD', 'TO BE ANNOUNCED', 'TO BE DETERMINED', 'N/A']:
        return 0
    
    try:
        # Handle various time formats
        if 'AM' in time_str or 'PM' in time_str:
            # 12-hour format - try multiple patterns
            for fmt in ['%I:%M %p', '%I %p', '%I:%M%p', '%I%p']:
                try:
                    time_obj = datetime.strptime(time_str, fmt)
                    return time_obj.hour * 60 + time_obj.minute
                except ValueError:
                    continue
        else:
            # 24-hour format - try multiple patterns
            for fmt in ['%H:%M', '%H:%M:%S', '%H']:
                try:
                    time_obj = datetime.strptime(time_str, fmt)
                    return time_obj.hour * 60 + time_obj.minute
                except ValueError:
                    continue
        
        # Try alternative formats (e.g., "8:00 am")
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 2:
                try:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    return hour * 60 + minute
                except ValueError:
                    pass
    except Exception:
        pass
    
    return 0


def extract_date_range(date_str):
    """Extract start and end dates from date string."""
    if not date_str or not isinstance(date_str, str):
        return None, None
    
    date_str = date_str.strip()
    
    # Handle single date
    if ' to ' not in date_str and ' - ' not in date_str:
        try:
            # Try various date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y']:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj, date_obj
                except ValueError:
                    continue
        except:
            pass
        return None, None
    
    # Handle date range
    separators = [' to ', ' - ', ' until ', ' through ']
    start_date = None
    end_date = None
    
    for sep in separators:
        if sep in date_str:
            parts = date_str.split(sep)
            if len(parts) == 2:
                start_str = parts[0].strip()
                end_str = parts[1].strip()
                
                # Parse start date
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y']:
                    try:
                        start_date = datetime.strptime(start_str, fmt)
                        break
                    except ValueError:
                        continue
                
                # Parse end date
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y']:
                    try:
                        end_date = datetime.strptime(end_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if start_date and end_date:
                    return start_date, end_date
    
    return None, None


def extract_time_range_from_complex_string(time_str):
    """
    Extract a valid time range from complex time strings.
    Handles formats like:
    - "4:30 pm - 5:30 pm / 6:30 pm - 7:30 pm (Friday), 4:30 pm - 6 pm (Saturday), 4:30 pm - 6 pm (Sunday)"
    - "2:30 pm & 7:30 pm shows"
    - "From 6 pm onwards"
    - "Set menus available throughout the week; launch reception on 21 August, 2 pm – 5 pm"
    """
    if not time_str or not isinstance(time_str, str):
        return None, None
    
    time_str = time_str.strip()
    
    # Try to find the first valid time range pattern
    
    # Pattern 1: "HH:MM am/pm - HH:MM am/pm" (most common)
    pattern1 = r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))'
    match1 = re.search(pattern1, time_str, re.IGNORECASE)
    if match1:
        start_time = match1.group(1).strip()
        end_time = match1.group(2).strip()
        return start_time, end_time
    
    # Pattern 2: "HH:MM - HH:MM" (24-hour format)
    pattern2 = r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})'
    match2 = re.search(pattern2, time_str)
    if match2:
        start_time = match2.group(1).strip()
        end_time = match2.group(2).strip()
        return start_time, end_time
    
    # Pattern 3: Single time with "onwards" or similar
    if 'onwards' in time_str.lower() or 'from' in time_str.lower():
        # Extract the time part
        time_pattern = r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))|(\d{1,2}\s*(?:am|pm|AM|PM))'
        time_match = re.search(time_pattern, time_str, re.IGNORECASE)
        if time_match:
            start_time = time_match.group(0).strip()
            return start_time, None
    
    # Pattern 4: Multiple times separated by "&" or "/"
    if '&' in time_str or '/' in time_str:
        # Try to extract the first valid time
        time_pattern = r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))|(\d{1,2}\s*(?:am|pm|AM|PM))'
        time_match = re.search(time_pattern, time_str, re.IGNORECASE)
        if time_match:
            start_time = time_match.group(0).strip()
            return start_time, None
    
    # Pattern 5: Look for any valid time format in the string
    time_pattern = r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))|(\d{1,2}\s*(?:am|pm|AM|PM))'
    time_match = re.search(time_pattern, time_str, re.IGNORECASE)
    if time_match:
        start_time = time_match.group(0).strip()
        return start_time, None
    
    return None, None


def convert_datetime_to_timestamps(event):
    """
    Convert date and time fields to Unix timestamps.
    Returns a new event dict with startTimestamp and endTimestamp fields.
    """
    if not event or not isinstance(event, dict):
        return event
    
    # Create a copy to avoid modifying the original
    new_event = event.copy()
    
    # Extract date and time information
    date_str = event.get('date', '')
    time_str = event.get('time', '')
    
    # Initialize timestamp fields
    start_timestamp = None
    end_timestamp = None
    
    # Check for TBA/unknown cases first
    if (date_str and date_str.upper() in ['TBA', 'TBD', 'TO BE ANNOUNCED', 'TO BE DETERMINED', 'N/A']) or \
       (time_str and time_str.upper() in ['TBA', 'TBD', 'TO BE ANNOUNCED', 'TO BE DETERMINED', 'N/A']):
        # Set both timestamps to null for TBA cases
        start_timestamp = None
        end_timestamp = None
    elif date_str and time_str:
        # Parse date range
        start_date, end_date = extract_date_range(date_str)
        
        if start_date:
            # Try enhanced time parsing first for complex strings
            start_time_str, end_time_str = extract_time_range_from_complex_string(time_str)
            
            if start_time_str:
                # Enhanced parsing found a valid time range
                start_minutes = parse_time_to_minutes(start_time_str)
                end_minutes = parse_time_to_minutes(end_time_str) if end_time_str else 0
                
                if start_minutes > 0:
                    # Create start datetime
                    start_timestamp = convert_to_qatar_timestamp(
                        start_date,
                        hour=start_minutes // 60,
                        minute=start_minutes % 60
                    )
                
                if end_time_str and end_minutes > 0:
                    # Create end datetime
                    end_timestamp = convert_to_qatar_timestamp(
                        end_date,
                        hour=end_minutes // 60,
                        minute=end_minutes % 60
                    )
                else:
                    # No valid end time, set to null
                    end_timestamp = None
                
                # Handle recurring schedules (e.g., different times for different days)
                if 'description' in event:
                    desc = event['description'].lower()
                    if any(term in desc for term in ['weekdays', 'weekends', 'sunday to thursday', 'friday & saturday']):
                        # For recurring events, use earliest start and latest end
                        if start_minutes > 0:
                            start_timestamp = int(start_date.replace(
                                hour=start_minutes // 60,
                                minute=start_minutes % 60,
                                second=0,
                                microsecond=0
                            ).timestamp())
                        
                        if end_minutes > 0:
                            end_timestamp = convert_to_qatar_timestamp(
                                end_date,
                                hour=end_minutes // 60,
                                minute=end_minutes % 60
                            )
            
            else:
                # Fall back to simple parsing for standard formats
                time_parts = time_str.split(' - ')
                
                if len(time_parts) == 2:
                    # Event has both start and end times
                    start_time_str = time_parts[0].strip()
                    end_time_str = time_parts[1].strip()
                    
                    # Convert times to minutes
                    start_minutes = parse_time_to_minutes(start_time_str)
                    end_minutes = parse_time_to_minutes(end_time_str)
                    
                    if start_minutes > 0:
                        # Create start datetime
                        start_timestamp = convert_to_qatar_timestamp(
                            start_date,
                            hour=start_minutes // 60,
                            minute=start_minutes % 60
                        )
                    
                    if end_minutes > 0:
                        # Create end datetime
                        end_datetime = end_date.replace(
                            hour=end_minutes // 60,
                            minute=end_minutes % 60,
                            second=0,
                            microsecond=0
                        )
                        end_timestamp = int(end_datetime.timestamp())
                    
                    # Handle recurring schedules (e.g., different times for different days)
                    if 'description' in event:
                        desc = event['description'].lower()
                        if any(term in desc for term in ['weekdays', 'weekends', 'sunday to thursday', 'friday & saturday']):
                            # For recurring events, use earliest start and latest end
                            if start_minutes > 0:
                                start_timestamp = int(start_date.replace(
                                    hour=start_minutes // 60,
                                    minute=start_minutes % 60,
                                    second=0,
                                    microsecond=0
                                ).timestamp())
                            
                            if end_minutes > 0:
                                end_timestamp = int(end_date.replace(
                                    hour=end_minutes // 60,
                                    minute=end_minutes % 60,
                                    second=0,
                                    microsecond=0
                                ).timestamp())
                
                elif len(time_parts) == 1:
                    # Event has only start time (single time)
                    start_time_str = time_parts[0].strip()
                    start_minutes = parse_time_to_minutes(start_time_str)
                    
                    if start_minutes > 0:
                        # Create start datetime
                        start_timestamp = convert_to_qatar_timestamp(
                            start_date,
                            hour=start_minutes // 60,
                            minute=start_minutes % 60
                        )
                    
                    # Set endTimestamp to null for single-time events
                    end_timestamp = None
    
    # Add timestamp fields
    new_event['startTimestamp'] = start_timestamp
    new_event['endTimestamp'] = end_timestamp
    

    
    return new_event


def convert_events_to_timestamps(events):
    """Convert a list of events to include Unix timestamps."""
    if not events:
        return events
    
    converted_events = []
    for event in events:
        converted_event = convert_datetime_to_timestamps(event)
        converted_events.append(converted_event)
    
    return converted_events


def convert_datetime_to_timestamps_clean(event):
    """
    Convert date and time fields to Unix timestamps WITHOUT modifying description.
    This is used for filtered events to keep them clean.
    Returns a new event dict with startTimestamp and endTimestamp fields.
    """
    if not event or not isinstance(event, dict):
        return event
    
    # Create a copy to avoid modifying the original
    new_event = event.copy()
    
    # Extract date and time information
    date_str = event.get('date', '')
    time_str = event.get('time', '')
    
    # Initialize timestamp fields
    start_timestamp = None
    end_timestamp = None
    
    # Check for TBA/unknown cases first
    if (date_str and date_str.upper() in ['TBA', 'TBD', 'TO BE ANNOUNCED', 'TO BE DETERMINED', 'N/A']) or \
       (time_str and time_str.upper() in ['TBA', 'TBD', 'TO BE ANNOUNCED', 'TO BE DETERMINED', 'N/A']):
        # Set both timestamps to null for TBA cases
        start_timestamp = None
        end_timestamp = None
    elif date_str and time_str:
        # Parse date range
        start_date, end_date = extract_date_range(date_str)
        
        if start_date:
            # Try enhanced time parsing first for complex strings
            start_time_str, end_time_str = extract_time_range_from_complex_string(time_str)
            
            if start_time_str:
                # Enhanced parsing found a valid time range
                start_minutes = parse_time_to_minutes(start_time_str)
                end_minutes = parse_time_to_minutes(end_time_str) if end_time_str else 0
                
                if start_minutes > 0:
                    # Create start datetime
                    start_timestamp = convert_to_qatar_timestamp(
                        start_date,
                        hour=start_minutes // 60,
                        minute=start_minutes % 60
                    )
                
                if end_time_str and end_minutes > 0:
                    # Create end datetime
                    end_timestamp = convert_to_qatar_timestamp(
                        end_date,
                        hour=end_minutes // 60,
                        minute=end_minutes % 60
                    )
                else:
                    # No valid end time, set to null
                    end_timestamp = None
                
                # Handle recurring schedules (e.g., different times for different days)
                if 'description' in event:
                    desc = event['description'].lower()
                    if any(term in desc for term in ['weekdays', 'weekends', 'sunday to thursday', 'friday & saturday']):
                        # For recurring events, use earliest start and latest end
                        if start_minutes > 0:
                            start_timestamp = int(start_date.replace(
                                hour=start_minutes // 60,
                                minute=start_minutes % 60,
                                second=0,
                                microsecond=0
                            ).timestamp())
                        
                        if end_minutes > 0:
                            end_timestamp = convert_to_qatar_timestamp(
                                end_date,
                                hour=end_minutes // 60,
                                minute=end_minutes % 60
                            )
            
            else:
                # Fall back to simple parsing for standard formats
                time_parts = time_str.split(' - ')
                
                if len(time_parts) == 2:
                    # Event has both start and end times
                    start_time_str = time_parts[0].strip()
                    end_time_str = time_parts[1].strip()
                    
                    # Convert times to minutes
                    start_minutes = parse_time_to_minutes(start_time_str)
                    end_minutes = parse_time_to_minutes(end_time_str)
                    
                    if start_minutes > 0:
                        # Create start datetime
                        start_timestamp = convert_to_qatar_timestamp(
                            start_date,
                            hour=start_minutes // 60,
                            minute=start_minutes % 60
                        )
                    
                    if end_minutes > 0:
                        # Create end datetime
                        end_datetime = end_date.replace(
                            hour=end_minutes // 60,
                            minute=end_minutes % 60,
                            second=0,
                            microsecond=0
                        )
                        end_timestamp = int(end_datetime.timestamp())
                    
                    # Handle recurring schedules (e.g., different times for different days)
                    if 'description' in event:
                        desc = event['description'].lower()
                        if any(term in desc for term in ['weekdays', 'weekends', 'sunday to thursday', 'friday & saturday']):
                            # For recurring events, use earliest start and latest end
                            if start_minutes > 0:
                                start_timestamp = int(start_date.replace(
                                    hour=start_minutes // 60,
                                    minute=start_minutes % 60,
                                    second=0,
                                    microsecond=0
                                ).timestamp())
                            
                            if end_minutes > 0:
                                end_timestamp = int(end_date.replace(
                                    hour=end_minutes // 60,
                                    minute=end_minutes % 60,
                                    second=0,
                                    microsecond=0
                                ).timestamp())
                
                elif len(time_parts) == 1:
                    # Event has only start time (single time)
                    start_time_str = time_parts[0].strip()
                    start_minutes = parse_time_to_minutes(start_time_str)
                    
                    if start_minutes > 0:
                        # Create start datetime
                        start_timestamp = convert_to_qatar_timestamp(
                            start_date,
                            hour=start_minutes // 60,
                            minute=start_minutes % 60
                        )
                    
                    # Set endTimestamp to null for single-time events
                    end_timestamp = None
    
    # Add timestamp fields
    new_event['startTimestamp'] = start_timestamp
    new_event['endTimestamp'] = end_timestamp
    
    # Clean the description by removing any existing schedule information
    if 'description' in new_event:
        desc = new_event['description']
        # Remove schedule information if it exists
        if 'Schedule:' in desc:
            # Find the position of "Schedule:" and remove everything from there
            schedule_pos = desc.find('Schedule:')
            if schedule_pos > 0:
                # Remove the schedule part and clean up extra newlines
                clean_desc = desc[:schedule_pos].rstrip()
                new_event['description'] = clean_desc
    
    # Remove the original date and time fields from filtered events
    # Only keep startTimestamp and endTimestamp
    if 'date' in new_event:
        del new_event['date']
    if 'time' in new_event:
        del new_event['time']
    
    return new_event


def convert_events_to_timestamps_clean(events):
    """Convert a list of events to include Unix timestamps WITHOUT modifying descriptions."""
    if not events:
        return events
    
    converted_events = []
    for event in events:
        converted_event = convert_datetime_to_timestamps_clean(event)
        converted_events.append(converted_event)
    
    return converted_events


def save_raw_events_with_timestamps(events, raw_filename=None, filtered_filename=None):
    """
    Two-step processing:
    1. Save raw events with original date/time text intact
    2. Convert to timestamps and save filtered version
    """
    if not events:
        print("No events to save.")
        return
    
    # Set default filenames with 'Collected Events' folder path
    import os
    project_root = os.path.dirname(os.path.dirname(__file__))
    collected_events_dir = os.path.join(project_root, 'Collected Events')
    os.makedirs(collected_events_dir, exist_ok=True)
    if raw_filename is None:
        raw_filename = os.path.join(collected_events_dir, 'events_01_raw.json')
    if filtered_filename is None:
        filtered_filename = os.path.join(collected_events_dir, 'events_02_processed.json')
    
    # Step 1: Save raw events with original date/time intact
    print(f"Saving {len(events)} raw events to {raw_filename}...")
    import json
    
    # For raw events, we want to preserve the original date/time fields
    # but also add a note in the description for clarity
    raw_events = []
    for event in events:
        raw_event = event.copy()
        date_str = event.get('date', '')
        time_str = event.get('time', '')
        
        # Add a note about the original schedule in the description for raw events only
        if 'description' in raw_event and date_str and time_str:
            original_schedule = f"Schedule: {date_str} {time_str}"
            if original_schedule not in raw_event['description']:
                raw_event['description'] = f"{raw_event['description']}\n\n{original_schedule}"
        
        raw_events.append(raw_event)
    
    with open(raw_filename, 'w', encoding='utf-8') as f:
        json.dump(raw_events, f, indent=2, ensure_ascii=False)
    
    # Step 2: Convert to timestamps and save filtered version
    print("Converting events to Unix timestamps...")
    # Use the ORIGINAL events with CLEAN conversion (no description modification)
    events_with_timestamps = convert_events_to_timestamps_clean(events)
    
    # Remove events without valid timestamps
    valid_events = []
    invalid_events = 0
    tba_events = 0
    no_date_events = 0
    no_time_events = 0
    parsing_failed_events = 0
    
    for event in events_with_timestamps:
        start_timestamp = event.get('startTimestamp')
        end_timestamp = event.get('endTimestamp')
        
        if start_timestamp is not None:
            # Event has a valid start timestamp (endTimestamp can be null)
            # Convert to correct order for filtered events
            ordered_event = generate_event_in_correct_order(event)
            valid_events.append(ordered_event)
        else:
            invalid_events += 1
            # Log the reason for failure
            date_str = event.get('date', '')
            time_str = event.get('time', '')
            
            if not date_str and not time_str:
                no_date_events += 1
            elif not date_str:
                no_date_events += 1
            elif not time_str:
                no_time_events += 1
            elif (date_str.upper() in ['TBA', 'TBD', 'TO BE ANNOUNCED', 'TO BE DETERMINED', 'N/A'] or 
                  time_str.upper() in ['TBA', 'TBD', 'TO BE ANNOUNCED', 'TO BE DETERMINED', 'N/A']):
                tba_events += 1
            else:
                parsing_failed_events += 1
    
    if invalid_events > 0:
        print(f"⚠️  {invalid_events} events could not be converted to timestamps and were excluded.")
        if tba_events > 0:
            print(f"  - {tba_events} events marked as TBA/To Be Announced")
        if no_date_events > 0:
            print(f"  - {no_date_events} events missing date information")
        if no_time_events > 0:
            print(f"  - {no_time_events} events missing time information")
        if parsing_failed_events > 0:
            print(f"  - {parsing_failed_events} events failed date/time parsing")
    
    print(f"Saving {len(valid_events)} filtered events with timestamps to {filtered_filename}...")
    with open(filtered_filename, 'w', encoding='utf-8') as f:
        json.dump(valid_events, f, indent=2, ensure_ascii=False)
    
    print("✅ Successfully saved both raw and filtered event files.")
    return len(valid_events)


def generate_event_in_correct_order(event):
    """
    Generate an event with fields in the exact order specified:
    1. name: event name
    2. description: event description 
    3. categoryId: event category name
    4. startTimestamp: event start time in seconds
    5. endTimestamp: event end time in seconds 
    6. locationLat: event location latitude
    7. locationLng: event location longitude
    8. locationDescription: event location description (optional)
    9. locationName: event location name 
    10. locationPhone: event location phone number
    11. website: event website
    12. image: event image URL
    """
    if not event or not isinstance(event, dict):
        return event
    
    # Create new event with correct field order
    ordered_event = {}
    
    # 1. name: event name
    ordered_event['name'] = event.get('name', '')
    
    # 2. description: event description 
    ordered_event['description'] = event.get('description', '')
    
    # 3. categoryId: event category name
    # Try to get from categoryId first, then fallback to category
    category_id = event.get('categoryId') or event.get('category', '')
    ordered_event['categoryId'] = category_id
    
    # 4. startTimestamp: event start time in seconds
    ordered_event['startTimestamp'] = event.get('startTimestamp')
    
    # 5. endTimestamp: event end time in seconds 
    ordered_event['endTimestamp'] = event.get('endTimestamp')
    
    # 6. locationLat: event location latitude
    ordered_event['locationLat'] = event.get('locationLat')
    
    # 7. locationLng: event location longitude
    ordered_event['locationLng'] = event.get('locationLng')
    
    # 8. locationDescription: event location description (optional)
    # Try to extract location description from various sources
    location_description = None
    if 'locationDescription' in event and event['locationDescription']:
        location_description = event['locationDescription']
    elif 'description' in event and event['description']:
        # Try to extract location info from the main description
        desc = event['description']
        # Look for location-related information in the description
        if 'Location:' in desc or 'Venue:' in desc or 'Address:' in desc:
            # Extract location details from description
            import re
            location_match = re.search(r'(?:Location|Venue|Address):\s*([^\n]+)', desc)
            if location_match:
                location_description = location_match.group(1).strip()
    ordered_event['locationDescription'] = location_description
    
    # 9. locationName: event location name 
    ordered_event['locationName'] = event.get('locationName', '')
    
    # 10. locationPhone: event location phone number
    # Try to extract phone number from various sources
    location_phone = None
    if 'locationPhone' in event and event['locationPhone']:
        location_phone = event['locationPhone']
    elif 'description' in event and event['description']:
        # Try to extract phone number from description
        desc = event['description']
        import re
        phone_match = re.search(r'(?:Phone|Tel|Contact):\s*([+\d\s\-\(\)]+)', desc)
        if phone_match:
            location_phone = phone_match.group(1).strip()
        # Also look for WhatsApp numbers
        whatsapp_match = re.search(r'WhatsApp:\s*([+\d\s\-\(\)]+)', desc)
        if whatsapp_match:
            location_phone = f"WhatsApp: {whatsapp_match.group(1).strip()}"
    ordered_event['locationPhone'] = location_phone
    
    # 11. website: event website
    ordered_event['website'] = event.get('website', '')
    
    # 12. image: event image URL
    ordered_event['image'] = event.get('image')
    
    # IMPORTANT: Preserve original date and time fields for doha_events.json
    # These will NOT be converted to timestamps in this file
    if 'date' in event:
        ordered_event['date'] = event.get('date')
    if 'time' in event:
        ordered_event['time'] = event.get('time')
    
    return ordered_event


def convert_events_to_correct_order(events):
    """Convert a list of events to have fields in the correct order."""
    if not events:
        return events
    
    converted_events = []
    for event in events:
        converted_event = generate_event_in_correct_order(event)
        converted_events.append(converted_event)
    
    return converted_events


def save_events_in_correct_order(events, filename=None):
    """
    Save events with fields in the correct order to a JSON file.
    This preserves the original date/time format for timestamps.
    """
    if not events:
        print("No events to save.")
        return
    
    # Set default filename with 'Collected Events' folder path
    if filename is None:
        import os
        project_root = os.path.dirname(os.path.dirname(__file__))
        collected_events_dir = os.path.join(project_root, 'Collected Events')
        os.makedirs(collected_events_dir, exist_ok=True)
        filename = os.path.join(collected_events_dir, 'events_01_raw.json')
    
    # Convert events to correct order
    ordered_events = convert_events_to_correct_order(events)
    
    print(f"Saving {len(ordered_events)} events in correct order to {filename}...")
    
    import json
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(ordered_events, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully saved {len(ordered_events)} events to {filename}")
    return len(ordered_events)