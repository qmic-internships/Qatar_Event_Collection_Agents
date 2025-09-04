# URL_Extraction.py
#
# URL extraction functionality for the Event Collection Agent
# This module contains all functions related to extracting URLs from scraped content

import re
from urllib.parse import urlparse
from typing import List, Optional, Set

def extract_marhaba_event_urls(markdown_content: str) -> List[str]:
    """
    Extract all unique Marhaba Qatar event detail URLs from the main page markdown content.
    
    Args:
        markdown_content: The markdown content scraped from Marhaba Qatar pages
        
    Returns:
        List of unique event detail URLs
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

def extract_ilq_event_urls(markdown_content: str) -> List[str]:
    """
    Extract only iLoveQatar EVENT DETAIL URLs from listing content.
    Rules:
      - Must be under /events/<category>/<slug>
      - Exclude: /events, /events/<category>, /events/filter, any with query-only filters
      
    Args:
        markdown_content: The markdown content scraped from iLoveQatar pages
        
    Returns:
        List of unique event detail URLs
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


def extract_event_source_url(markdown_content: str) -> Optional[str]:
    """
    Extract the first valid external website link from the event markdown content after a 'Website:' label.
    
    Args:
        markdown_content: The markdown content to search
        
    Returns:
        The URL as a string, or None if not found
    """
    # Look for a line starting with 'Website:'
    website_section = re.search(r'Website:\s*\n\[* ?(https?://[^)\]\s]+)', markdown_content)
    if website_section:
        return website_section.group(1)
    return None

def extract_ilq_visit_website_url(markdown_content: str) -> Optional[str]:
    """
    Extract the external link labeled 'Visit Website' from an iLoveQatar event page markdown.
    
    Args:
        markdown_content: The markdown content to search
        
    Returns:
        The URL string if found, else None
    """
    try:
        # Match markdown links like: [Visit Website](https://example.com ...) case-insensitively
        match = re.search(r"\[\s*Visit\s+Website\s*\]\((https?://[^)\s]+)", markdown_content, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    except Exception:
        return None
