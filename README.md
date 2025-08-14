# Qatar Events Scraper & Analyzer

A Python application that scrapes and analyzes events from various Qatar-based websites and APIs using Firecrawl and Google's Gemini AI model.

## Features

- **Multi-source Event Collection**: Scrapes events from multiple Qatar websites
- **Visit Qatar API Integration**: Direct API integration with Visit Qatar's events endpoint
- **AI-Powered Analysis**: Uses Google's Gemini AI model for intelligent event extraction and processing
- **Geocoding Support**: Automatically adds coordinates to event locations using Google Geocoding API
- **Flexible Output**: Generates structured JSON files with event data
- **Command-line Interface**: Easy-to-use CLI with different modes

## Installation

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

## Usage

### Visit Qatar API Mode
Fetch events directly from the Visit Qatar API:
```bash
python app.py --visit-qatar
```

### Website Scraping Mode (Default)
Scrape events from configured websites:
```bash
python app.py
```

## Output Files

- `visit_qatar_events.json`: Events fetched from Visit Qatar API
- `doha_events.json`: Events scraped from websites
- `qatar_events_combined_analysis.json`: Combined analysis of scraped websites
- `scraped_pages/`: Raw scraped content (excluded from git)

## Configuration

### Target Websites
Currently configured to scrape:
- https://marhaba.qa/event/
- https://www.iloveqatar.net/events

### API Endpoints
- Visit Qatar API: https://visitqatar.com/api/en/events.v2.json

## Event Data Structure

Each event contains:
- `name`: Event title
- `date`: Event date(s)
- `time`: Event time(s)
- `location`: Venue with coordinates (if available)
- `description`: Event description
- `category`: Event category
- `url`: Event URL
- `source`: Data source identifier

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