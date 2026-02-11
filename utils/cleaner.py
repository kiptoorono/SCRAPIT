"""
Content Cleaner: Standardized data pipeline for cleaning and normalizing extracted content
"""

import re
from typing import List, Dict, Optional, Any, Tuple
import logging
import html
import unicodedata

logger = logging.getLogger(__name__)


class ContentCleaner:
    """
    Cleans and normalizes extracted content according to standardized pipeline
    """
    
    def __init__(self, config: Dict):
        """
        Initialize cleaner with configuration
        
        Args:
            config: Configuration dict with normalization settings
        """
        self.config = config
        self.data_norm_config = config.get('data_normalization', {})
        self.output_schema = config.get('output_schema', {})
    
    def clean_title(self, title: str) -> str:
        """Clean article title"""
        if not title:
            return ""
        
        # Decode HTML entities
        title = html.unescape(title)
        
        # Strip whitespace
        title = title.strip()
        
        # Remove double spaces
        title = re.sub(r'\s+', ' ', title)
        
        # Remove trailing punctuation if duplicate
        title = re.sub(r'([.!?])\1+', r'\1', title)
        
        # Normalize unicode
        title = unicodedata.normalize('NFC', title)
        
        return title
    
    def clean_content(self, content: str) -> str:
        """Clean article body content"""
        if not content:
            return ""
        
        # Decode HTML entities
        content = html.unescape(content)
        
        # Remove HTML tags (but preserve content)
        content = re.sub(r'<[^>]+>', '', content)
        
        # Remove excess whitespace
        content = re.sub(r'\n\s*\n+', '\n\n', content)  # Multiple newlines -> double newline
        lines = content.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        content = '\n'.join(lines)
        
        # Normalize unicode
        content = unicodedata.normalize('NFC', content)
        
        # Remove common boilerplate text
        content = self._remove_boilerplate(content)
        
        return content.strip()
    
    def _remove_boilerplate(self, content: str) -> str:
        """Remove known boilerplate phrases"""
        # Get site config boilerplate phrases if available
        boilerplate_phrases = []
        
        # This would be populated from sites_config if processing per-site
        # For now, use common patterns
        common_boilerplate = [
            r'subscribe\s+to\s+our\s+newsletter',
            r'follow\s+us\s+on',
            r'share\s+this\s+article',
            r'related\s+articles',
            r'click\s+here\s+for',
            r'©\s+\d{4}',  # Copyright
            r'all\s+rights\s+reserved',
            r'powered\s+by',
        ]
        
        for pattern in common_boilerplate:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        return content
    
    def clean_author(self, author: str) -> str:
        """Normalize author name"""
        if not author:
            return ""
        
        # Decode HTML entities
        author = html.unescape(author)
        
        # Remove "By" prefix
        author = re.sub(r'^(by|written by|author:?)\s+', '', author, flags=re.IGNORECASE)
        
        # Remove organizational suffixes commonly tagged as author
        author = re.sub(r'\s+(Staff|Reuters|AP|AFP)$', '', author, flags=re.IGNORECASE)
        
        # Remove titles (Dr., Prof., etc.)
        author = re.sub(r'^(Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.|Sir|Dame)\s+', '', author)
        
        # Remove suffixes (Jr., PhD, etc.)
        author = re.sub(r'\s+(Jr\.|Sr\.|PhD|Esq\.?)$', '', author)
        
        # Normalize caps and spacing
        author = author.strip()
        author = re.sub(r'\s+', ' ', author)
        
        # Normalize unicode
        author = unicodedata.normalize('NFC', author)
        
        return author
    
    def normalize_date(self, date_str: str) -> str:
        """
        Normalize date string (should already be normalized by DateNormalizer)
        This is a final cleanup pass
        """
        if not date_str:
            return ""
        
        # Remove timezone info for consistency (we work in UTC)
        date_str = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str)
        date_str = re.sub(r'\s*[A-Z]{3}$', '', date_str)
        date_str = re.sub(r'\s*Z$', '', date_str)
        
        return date_str.strip()
    
    def normalize_category(self, category: str, site_name: str) -> str:
        """
        Map site-specific categories to standard taxonomy
        
        Args:
            category: Original category from site
            site_name: Site identifier
        
        Returns:
            Normalized category
        """
        if not category:
            return "Uncategorized"
        
        category = category.strip().lower()
        
        # Load category mappings from config
        category_mappings = self.data_norm_config.get('category_mapping', {})
        site_mappings = category_mappings.get(site_name, {})
        
        # Try exact match
        if category in site_mappings:
            return site_mappings[category]
        
        # Try partial match
        for original, normalized in site_mappings.items():
            if original in category or category in original:
                return normalized
        
        # Return original if no mapping found
        return category.title()
    
    def normalize_tags(self, tags: List[str]) -> List[str]:
        """
        Normalize and deduplicate tags
        
        Args:
            tags: List of tags
        
        Returns:
            Cleaned and deduplicated tags
        """
        if not tags:
            return []
        
        normalized = []
        seen = set()
        
        for tag in tags:
            if not tag:
                continue
            
            # Clean tag
            tag = tag.strip().lower()
            
            # Remove special characters (keep only alphanumeric, hyphens, underscores)
            tag = re.sub(r'[^a-z0-9\-_]', '', tag)
            
            # Remove overly broad tags
            if tag in ['news', 'article', 'story', 'post', 'page']:
                continue
            
            # Deduplicate
            if tag not in seen:
                normalized.append(tag)
                seen.add(tag)
        
        # Limit to top N tags
        max_tags = 10
        return normalized[:max_tags]
    
    def extract_image_url(self, image_url: str, base_url: str = None) -> Optional[str]:
        """
        Clean and validate image URL
        
        Args:
            image_url: Image URL from extraction
            base_url: Base URL for resolving relative URLs
        
        Returns:
            Absolute image URL or None
        """
        if not image_url:
            return None
        
        image_url = image_url.strip()
        
        # Remove common placeholder URLs
        if 'placeholder' in image_url.lower():
            return None
        
        # Resolve relative URLs
        if image_url.startswith('/'):
            if base_url:
                if base_url.startswith('http'):
                    domain = base_url.split('/', 3)[2]  # Extract domain
                    image_url = f"https://{domain}{image_url}"
        elif image_url.startswith('./'):
            if base_url:
                base = base_url.rsplit('/', 1)[0]
                image_url = base + image_url[1:]
        
        # Validate that it's a real URL
        if not image_url.startswith('http'):
            return None
        
        return image_url
    
    def normalize_output(self, raw_data: Dict) -> Dict:
        """
        Normalize all extracted data into standardized schema
        
        Args:
            raw_data: Raw extracted data
        
        Returns:
            Normalized data dict
        """
        normalized = {
            # Required fields
            'url': raw_data.get('url', ''),
            'title': self.clean_title(raw_data.get('title', '')),
            'content': self.clean_content(raw_data.get('content', '')),
            'scraped_at': raw_data.get('scraped_at', ''),
            
            # Optional fields
            'author': self.clean_author(raw_data.get('author', '')) or None,
            'published_date': self.normalize_date(raw_data.get('date', '')) or None,
            'modified_date': raw_data.get('modified_date') or None,
            'category': self.normalize_category(raw_data.get('category', ''), 
                                               raw_data.get('source_site', '')),
            'tags': self.normalize_tags(raw_data.get('tags', [])) or [],
            'language': raw_data.get('language', 'en'),
            'image_url': self.extract_image_url(raw_data.get('image_url', '')) or None,
            
            # Metadata
            'source_site': raw_data.get('source_site', ''),
            'extraction_method': raw_data.get('extraction_method', 'unknown'),
            'extraction_confidence': raw_data.get('extraction_confidence', 0),
            'confidence_scores': raw_data.get('confidence_scores', {}),
            'extraction_duration_ms': raw_data.get('extraction_duration_ms', 0),
        }
        
        # Validate required fields
        required = self.output_schema.get('required_fields', ['url', 'title', 'content', 'scraped_at'])
        for field in required:
            if not normalized.get(field):
                logger.warning(f"Missing required field: {field}")
        
        return normalized
    
    def validate_article(self, article: Dict) -> Tuple[bool, List[str]]:
        """
        Validate extracted article
        
        Args:
            article: Article dict to validate
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check URL
        if not article.get('url') or not article['url'].startswith('http'):
            errors.append("Invalid or missing URL")
        
        # Check title
        title = article.get('title', '')
        if not title or len(title) < 5:
            errors.append(f"Title too short: {len(title)} chars")
        elif len(title) > 500:
            errors.append(f"Title too long: {len(title)} chars")
        
        # Check content
        content = article.get('content', '')
        if not content or len(content) < 100:
            errors.append(f"Content too short: {len(content)} chars")
        
        # Check date if present
        date = article.get('published_date')
        if date and not self._is_valid_date(date):
            errors.append(f"Invalid date format: {date}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string matches expected format"""
        # Expected format: YYYY-MM-DD HH:MM:SS
        pattern = r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$'
        return bool(re.match(pattern, date_str))
