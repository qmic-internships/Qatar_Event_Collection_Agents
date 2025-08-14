# Docker Setup for Qatar Events Scraper with Firecrawl

This Docker Compose configuration sets up a complete environment for running the Qatar Events Scraper with a self-hosted Firecrawl instance.

## Prerequisites

- Docker and Docker Compose installed on your system
- Google AI API key (for Gemini model)
- Google Geocoding API key (for location coordinates)

## Quick Start

1. **Clone or navigate to your project directory**
   ```bash
   cd "path/to/your/project"
   ```

2. **Set up environment variables**
   ```bash
   # Copy the example environment file
   cp env.example .env
   
   # Edit .env file with your actual API keys
   nano .env
   ```

3. **Build and start the services**
   ```bash
   docker-compose up --build
   ```

4. **Run the scraper**
   ```bash
   # For regular scraping mode
   docker-compose exec app python app.py
   
   # For Visit Qatar API mode
   docker-compose exec app python app.py --visit-qatar
   ```

## Services

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

## Configuration

### Environment Variables

Create a `.env` file in your project root with the following variables:

```env
# Google AI API Key - Get from Google AI Studio
GOOGLE_API_KEY=your_google_ai_api_key_here

# Google Geocoding API Key - Get from Google Cloud Console
GEOCODING_API_KEY=your_google_geocoding_api_key_here
```

### Volumes

- `./scraped_pages`: Stores raw scraped content
- `./data`: Stores application data and results
- `firecrawl_data`: Persistent Firecrawl data

## Usage

### Starting Services
```bash
# Start all services in background
docker-compose up -d

# Start with logs
docker-compose up

# Rebuild and start
docker-compose up --build
```

### Running the Scraper
```bash
# Regular scraping mode (scrapes websites)
docker-compose exec app python app.py

# Visit Qatar API mode (fetches from API)
docker-compose exec app python app.py --visit-qatar
```

### Stopping Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Viewing Logs
```bash
# View all service logs
docker-compose logs

# View specific service logs
docker-compose logs firecrawl
docker-compose logs app

# Follow logs in real-time
docker-compose logs -f
```

## Output Files

The application generates several output files in the `./data` directory:

- `doha_events.json`: Extracted events from scraped websites
- `visit_qatar_events.json`: Events from Visit Qatar API
- `qatar_events_combined_analysis.json`: Combined analysis of scraped sites

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

### Network Issues
```bash
# Check if services can communicate
docker-compose exec app curl http://firecrawl:3002/health

# Restart services
docker-compose restart
```

## Development

### Making Changes
1. Modify your Python code
2. Rebuild the application container:
   ```bash
   docker-compose build app
   docker-compose up -d
   ```

### Adding Dependencies
1. Update `requirements.txt`
2. Rebuild the container:
   ```bash
   docker-compose build app
   ```

## Security Notes

- Never commit your `.env` file to version control
- The `.dockerignore` file excludes sensitive files from the build context
- Firecrawl runs in a containerized environment for isolation
- API keys are passed as environment variables

## Performance

- Firecrawl service includes health checks for reliability
- Services restart automatically unless manually stopped
- Data persistence through Docker volumes
- Optimized Python image for smaller footprint

## Support

For issues with:
- **Firecrawl**: Check the [Firecrawl documentation](https://github.com/firecrawl/firecrawl)
- **Docker**: Refer to [Docker Compose documentation](https://docs.docker.com/compose/)
- **Application**: Check the main README.md file 