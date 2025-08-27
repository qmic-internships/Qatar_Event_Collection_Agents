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

def _normalize_tokens(text: str) -> Set[str]:
    """
    Normalize text into a set of tokens for comparison.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Set of normalized tokens
    """
    text = text.lower()
    # Replace non-alphanumeric with space (ASCII-focused for robustness)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t]
    return set(tokens)

def _select_primary_event_by_slug_tokens(events: List[dict], slug_tokens: List[str]) -> Optional[dict]:
    """
    From a list of event dicts, select the one whose name best matches the slug tokens.
    Requires at least 2-token overlap; if none meets threshold, return first event.
    
    Args:
        events: List of event dictionaries
        slug_tokens: List of slug tokens to match against
        
    Returns:
        The best matching event or the first event if no good match found
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
    """
    Convert filename-based slug to path 'category/slug' by replacing first '_' with '/'.
    
    Args:
        filename: The filename to process
        ilq_event_prefix: The prefix to remove from the filename
        
    Returns:
        Reconstructed path string
    """
    raw = filename[len(ilq_event_prefix):-len('_scraped_content.md')].rstrip('_')
    return raw.replace('_', '/', 1)

def _is_u17_world_cup_individual_match(event_name: str) -> bool:
    """
    Return True if the event name looks like an individual FIFA U-17 World Cup match 
    (e.g., contains 'vs', 'Group X:', rounds), and False for overarching events like 
    'FIFA U-17 World Cup Qatar 2025'.
    
    Args:
        event_name: The event name to check
        
    Returns:
        True if it's an individual match, False otherwise
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
