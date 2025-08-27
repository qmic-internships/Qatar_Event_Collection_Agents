# Qatar Events Scraper & Analyzer

A Python application that scrapes and analyzes events from various Qatar-based websites and APIs using Firecrawl and Google's Gemini AI model.

## Features

- **Multi-source Event Collection**: Scrapes events from multiple Qatar websites
- **Visit Qatar API Integration**: Direct API integration with Visit Qatar's events endpoint
- **AI-Powered Analysis**: Uses Google's Gemini AI model for intelligent event extraction and processing
- **Geocoding Support**: Automatically adds coordinates to event locations using Google Geocoding API
- **Unix Timestamp Support**: Advanced timestamp conversion for better data consistency and deduplication
- **Flexible Output**: Generates structured JSON files with event data
- **Command-line Interface**: Easy-to-use CLI with different modes
- **Docker Support**: Complete containerized environment with Firecrawl

## Project Structure

```
Event Collection Agent/
├── src/                           # All Python source code
│   ├── __init__.py               # Package initialization
│   ├── app.py                    # Main application logic
│   ├── config.py                 # Configuration settings
│   ├── geolocation.py            # Geolocation functionality
│   └── timestamp_utils.py        # Date/time processing utilities
├── Collected Events/             # Directory for all generated JSON event files
│   ├── events_01_raw.json       # Raw scraped events
│   ├── events_02_processed.json # Events with Unix timestamps
│   ├── events_03_curated.json   # Culturally filtered events
│   └── events_04_final.json     # Final deduplicated events
├── cache/                        # Directory for cache files
│   └── geolocation_cache.json   # Geolocation API cache
├── scraped_pages/               # Directory for scraped content (created at runtime)
├── main.py                      # Main entry point script
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker configuration
├── docker-compose.yml          # Docker Compose setup
└── README.md                    # Main project documentation
```

## Installation

### Option 1: Local Installation

1. Clone the repository:
```bash
git clone https://github.com/khaledawsd/Testing-repo.git
cd Testing-repo
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up required services:
   - **Firecrawl**: Run a local Firecrawl instance (default: http://localhost:3002)
   - **Google AI API**: Get an API key from [Google AI Studio](https://aistudio.google.com/)
   - **Google Geocoding API**: Get an API key from [Google Cloud Console](https://console.cloud.google.com/)

5. Update API keys in `app.py`:
   - Replace `GOOGLE_API_KEY` with your Google AI API key
   - Replace `GEOCODING_API_KEY` with your Google Geocoding API key

### Option 2: Docker Installation

1. **Set up environment variables**:
   ```bash
   # Copy the example environment file
   cp env.example .env
   
   # Edit .env file with your actual API keys
   nano .env
   ```

2. **Build and start the services**:
   ```bash
   docker-compose up --build
   ```

## Usage

### Running the Application

#### Option 1: Using the main entry point (Recommended)
```bash
python main.py [options]
```

#### Option 2: Running directly from src
```bash
cd src
python app.py [options]
```

#### Option 3: Docker (if using Docker setup)
```bash
# Regular scraping mode (scrapes websites)
docker-compose exec app python app.py
```

### Command Line Options

#### Website Scraping Mode (Default)
Scrape events from configured websites:
```bash
python app.py
```

#### Filtering and Deduplication Only
Process existing events for filtering and deduplication:
```bash
python app.py --filter-events
```

## Event Data Structure

### New Location Field Format
Each event now includes three separate location fields:
- `locationLat`: Latitude coordinate
- `locationLng`: Longitude coordinate  
- `locationName`: Location/venue name
- `website`: Event organizer's original website URL

### Unix Timestamp Fields
- `startTimestamp`: Unix timestamp (seconds since epoch) when the event first begins
- `endTimestamp`: Unix timestamp (seconds since epoch) when the event finally ends
- `date`: Original date text (preserved for user readability)
- `time`: Original time text (preserved for user readability)

### Complete Event Structure
```json
{
  "name": "Qatar National Day Celebration",
  "date": "2024-12-18",
  "time": "4:00 PM - 10:00 PM",
  "startTimestamp": 1734537600,
  "endTimestamp": 1734566400,
  "locationName": "Corniche",
  "locationLat": 25.2854,
  "locationLng": 51.5310,
  "description": "Annual celebration with fireworks and cultural performances.\n\nSchedule: 2024-12-18 4:00 PM - 10:00 PM",
  "category": "cultural",
  "website": "https://example.com/event"
}
```

## Two-Step Processing Workflow

### Step 1: Raw Event Collection
- Events are scraped and saved to `events_01_raw.json`
- Original date/time text is preserved exactly as found
- No timestamp conversion occurs at this stage

### Step 2: Timestamp Conversion
- Raw events are converted to include Unix timestamps
- Filtered events are saved to `events_02_processed.json`
- Only events with valid timestamps are included in the filtered file

## Output Files

The application generates several output files in the `Collected Events/` directory:

- `events_01_raw.json`: Raw scraped events with original date/time
- `events_02_processed.json`: Events with Unix timestamps
- `events_03_curated.json`: Culturally appropriate events
- `events_04_final.json`: Final deduplicated events
- `scraped_pages/`: Raw scraped content (excluded from git)

## Configuration

### Target Websites
Currently configured to scrape:
- https://marhaba.qa/event/
- https://www.iloveqatar.net/events

### Environment Variables (Docker)
Create a `.env` file in your project root:
```env
# Google AI API Key - Get from Google AI Studio
GOOGLE_API_KEY=your_google_ai_api_key_here

# Google Geocoding API Key - Get from Google Cloud Console
GEOCODING_API_KEY=your_google_geocoding_api_key_here
```

## Timestamp Conversion Logic

### Date Parsing
Supports multiple date formats:
- `YYYY-MM-DD`
- `DD/MM/YYYY`
- `MM/DD/YYYY`
- `DD-MM-YYYY`
- `MM-DD-YYYY`

### Time Parsing
Supports multiple time formats:
- `HH:MM AM/PM` (12-hour)
- `HH:MM` (24-hour)
- `H:MM AM/PM` (single digit hour)
- `H AM/PM` (hour only)

### Event Types Handled

#### 1. Full Time Range Events
- **Format**: `"9:00 AM - 5:00 PM"`
- **startTimestamp**: Converted to Unix timestamp
- **endTimestamp**: Converted to Unix timestamp

#### 2. Single Time Events
- **Format**: `"8:00 am"` or `"7:00 PM"`
- **startTimestamp**: Converted to Unix timestamp
- **endTimestamp**: Set to `null` (no end time specified)

#### 3. TBA/Unknown Events
- **Format**: `"TBA"`, `"TBD"`, `"To be announced"`, `"N/A"`
- **startTimestamp**: Set to `null`
- **endTimestamp**: Set to `null`
- **Note**: These events are excluded from filtered output

#### 4. Multi-day Events
- **Format**: `"2024-12-25 to 2024-12-31"`
- **startTimestamp**: Uses earliest date + earliest time
- **endTimestamp**: Uses latest date + latest time

#### 5. Recurring Schedules
For events with different times on different days:
- **startTimestamp**: Uses earliest start time
- **endTimestamp**: Uses latest end time
- Original schedule text is preserved in description

## Deduplication Logic

### Before (Old System)
- Used `date + location` for grouping
- Could miss events with same date but different times

### After (New System)
- Uses `startTimestamp + location` for grouping
- More accurate deduplication
- Handles events with same date but different times correctly

## Docker Services

### Firecrawl Service
- **Image**: `firecrawl/firecrawl:latest`
- **Port**: `3002` (accessible at `http://localhost:3002`)
- **Purpose**: Self-hosted web scraping API
- **Health Check**: Monitors service availability

### Python Application Service
- **Base**: Python 3.11 slim image
- **Port**: `8000` (if needed for web interface)
- **Purpose**: Runs the Qatar Events Scraper
- **Dependencies**: Waits for Firecrawl to be healthy before starting

### Docker Commands
```bash
# Start all services in background
docker-compose up -d

# Start with logs
docker-compose up

# Rebuild and start
docker-compose up --build

# Stop all services
docker-compose down

# View logs
docker-compose logs -f
```

## Dependencies

- `firecrawl-py`: Web scraping
- `google-generativeai`: Google Gemini AI integration
- `requests`: HTTP requests
- `argparse`: Command-line argument parsing

## Development

The project uses:
- **Firecrawl**: For web scraping (self-hosted instance)
- **Google Gemini**: For AI-powered content analysis
- **Google Geocoding**: For location coordinate lookup

### Making Changes
1. Modify your Python code
2. If using Docker, rebuild the application container:
   ```bash
   docker-compose build app
   docker-compose up -d
   ```

### Adding Dependencies
1. Update `requirements.txt`
2. If using Docker, rebuild the container:
   ```bash
   docker-compose build app
   ```

## Benefits of New Format

1. **Consistent Data Format**: Unix timestamps provide a standardized time representation
2. **Better Sorting**: Events can be easily sorted chronologically
3. **Improved Deduplication**: More accurate grouping using precise timestamps
4. **Preserved Readability**: Original date/time text remains for user display
5. **Recurring Schedule Support**: Handles complex multi-day schedules
6. **API Compatibility**: Timestamps are easily consumed by other systems
7. **Structured Location Data**: Separate fields make it easier to access specific location information
8. **Clean Output**: No redundant fields in the final JSON

## Error Handling

- Events that cannot be converted to timestamps are excluded from filtered output
- **Detailed failure logging** shows specific reasons for conversion failures
- The system continues processing even if some events fail conversion
- **Improved success rate**: Now handles single-time events and TBA cases properly
- Events with only `startTimestamp` (and `endTimestamp` as `null`) are considered valid

## Testing

Run the test suite to verify timestamp conversion:
```bash
python test_timestamps.py
```

## Troubleshooting

### Firecrawl Not Starting
```bash
# Check Firecrawl logs
docker-compose logs firecrawl

# Check if port 3002 is available
netstat -tulpn | grep 3002
```

### Application Errors
```bash
# Check application logs
docker-compose logs app

# Access container shell for debugging
docker-compose exec app bash
```

### API Key Issues
- Ensure your `.env` file contains valid API keys
- Verify API keys have proper permissions
- Check Google AI Studio and Google Cloud Console for quota limits

## Security Notes

- Never commit your `.env` file to version control
- The `.dockerignore` file excludes sensitive files from the build context
- Firecrawl runs in a containerized environment for isolation
- API keys are passed as environment variables

## License

This project is for educational and research purposes.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Notes

- The `scraped_pages/` directory contains raw scraped content and is excluded from version control
- JSON output files are excluded from version control to avoid large file commits
- API keys should be kept secure and not committed to version control
- The system automatically migrates old cache formats to new formats
- All original date/time information is preserved during processing 