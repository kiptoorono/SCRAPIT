"""
Extraction Logic: Four-Tier Fallback System

Tier 1: Config-based CSS selectors (Precision)
Tier 2: Metadata extraction (JSON-LD, OpenGraph, Twitter)
Tier 3: Heuristic text density analysis
Tier 4: Failure logging for manual review
"""

import json
import re
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import hashlib

from bs4 import BeautifulSoup, NavigableString
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of article extraction with confidence scores"""
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None  # Add URL field
    
    # Metadata
    extraction_method: str = None  # 'tier1', 'tier2', 'tier3', 'tier4'
    confidence_scores: Dict[str, float] = None
    extraction_duration_ms: float = None
    scraped_at: str = None
    source_site: str = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'url': self.url,  # Include URL in output
            'title': self.title,
            'content': self.content,
            'author': self.author,
            'date': self.date,
            'image_url': self.image_url,
            'category': self.category,
            'extraction_method': self.extraction_method,
            'confidence_scores': self.confidence_scores or {},
            'extraction_duration_ms': self.extraction_duration_ms,
            'scraped_at': self.scraped_at or datetime.utcnow().isoformat(),
            'source_site': self.source_site,
        }
    
    def is_complete(self, required_fields=None) -> bool:
        """Check if result has minimum required fields"""
        if required_fields is None:
            required_fields = ['title', 'content']
        
        for field in required_fields:
            if not getattr(self, field):
                return False
        return True


class ExtractionEngine:
    """
    Four-tier extraction engine for universal article extraction
    """
    
    def __init__(self, config: Dict, failed_extractions_dir: str = "failed_extractions"):
        """
        Initialize extraction engine
        
        Args:
            config: Site configuration from sites_config.yaml
            failed_extractions_dir: Directory to log failed extractions
        """
        self.config = config
        self.failed_extractions_dir = Path(failed_extractions_dir)
        self.failed_extractions_dir.mkdir(exist_ok=True)
    
    def extract(self, html: str, url: str, site_name: str, category: str = None) -> ExtractionResult:
        """
        Main extraction method with four-tier fallback
        
        Args:
            html: Raw HTML content
            url: Article URL (for logging/deduplication)
            site_name: Name of site (e.g., 'the-star', 'the-standard')
            category: Article category/section
        
        Returns:
            ExtractionResult with extracted data
        """
        start_time = datetime.utcnow()
        soup = BeautifulSoup(html, 'html.parser')
        result = ExtractionResult(source_site=site_name, category=category, url=url)
        
        # Tier 1: Config-based extraction
        logger.info(f"[Tier 1] Attempting config-based extraction from {url}")
        result = self._tier1_config_selectors(soup, result, site_name)
        
        if result.is_complete():
            result.extraction_method = 'tier1'
            result.extraction_duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"✓ Tier 1 succeeded for {url}")
            return result
        
        # Tier 2: Metadata extraction
        logger.info(f"[Tier 2] Attempting metadata extraction from {url}")
        result = self._tier2_metadata_extraction(soup, result, site_name)
        
        if result.is_complete():
            result.extraction_method = 'tier2'
            result.extraction_duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"✓ Tier 2 succeeded for {url}")
            return result
        
        # Tier 3: Heuristic analysis
        logger.info(f"[Tier 3] Attempting heuristic extraction from {url}")
        result = self._tier3_heuristic_analysis(soup, result, site_name)
        
        if result.is_complete():
            result.extraction_method = 'tier3'
            result.extraction_duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"✓ Tier 3 succeeded for {url}")
            return result
        
        # Tier 4: Log failure for manual review
        logger.warning(f"[Tier 4] All extraction methods failed for {url}")
        self._tier4_log_failure(html, url, site_name, result)
        
        result.extraction_method = 'tier4_failed'
        result.extraction_duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return result
    
    def _tier1_config_selectors(self, soup: BeautifulSoup, result: ExtractionResult, 
                               site_name: str) -> ExtractionResult:
        """
        Tier 1: Extract using site-specific CSS selectors from config
        """
        site_config = self.config.get('sites', {}).get(site_name, {})
        selectors = site_config.get('selectors', {})
        confidence_scores = {}
        
        # Extract title
        title, title_conf = self._extract_by_selectors(
            soup, selectors.get('title', {})
        )
        if title and len(title) >= 10:
            result.title = title
            confidence_scores['title'] = title_conf
        
        # Extract content
        content, content_conf = self._extract_content_by_selectors(
            soup, selectors.get('content', {})
        )
        if content and len(content) >= 100:
            result.content = content
            confidence_scores['content'] = content_conf
        
        # Extract author
        author, author_conf = self._extract_by_selectors(
            soup, selectors.get('author', {})
        )
        if author:
            result.author = author
            confidence_scores['author'] = author_conf
        
        # Extract date
        date_str, date_conf = self._extract_by_selectors(
            soup, selectors.get('date', {})
        )
        if date_str:
            result.date = date_str
            confidence_scores['date'] = date_conf
        
        # Extract image URL
        img_url, img_conf = self._extract_image_url(
            soup, selectors.get('image', {})
        )
        if img_url:
            result.image_url = img_url
            confidence_scores['image_url'] = img_conf
        
        result.confidence_scores = confidence_scores
        return result
    
    def _extract_by_selectors(self, soup: BeautifulSoup, selector_config: Dict) -> Tuple[Optional[str], float]:
        """
        Extract text using primary and fallback selectors
        
        Returns:
            Tuple of (extracted_text, confidence_score)
        """
        primary = selector_config.get('primary')
        fallbacks = selector_config.get('fallback', [])
        
        all_selectors = [primary] + fallbacks if primary else fallbacks
        
        for i, selector in enumerate(all_selectors):
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text:
                        # Confidence decreases with fallback levels
                        confidence = 1.0 - (i * 0.15)
                        return text, confidence
            except Exception as e:
                logger.debug(f"Selector failed: {selector} - {e}")
                continue
        
        return None, 0.0
    
    def _extract_content_by_selectors(self, soup: BeautifulSoup, selector_config: Dict) -> Tuple[Optional[str], float]:
        """
        Extract full content (paragraphs) using selectors
        """
        primary = selector_config.get('primary')
        fallbacks = selector_config.get('fallback', [])
        
        all_selectors = [primary] + fallbacks if primary else fallbacks
        
        for i, selector in enumerate(all_selectors):
            try:
                container = soup.select_one(selector)
                if container:
                    paragraphs = container.find_all('p')
                    if paragraphs:
                        content = '\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                        if len(content) >= 100:
                            confidence = 1.0 - (i * 0.15)
                            return content, confidence
            except Exception as e:
                logger.debug(f"Content selector failed: {selector} - {e}")
                continue
        
        return None, 0.0
    
    def _extract_image_url(self, soup: BeautifulSoup, selector_config: Dict) -> Tuple[Optional[str], float]:
        """
        Extract image URL from CSS selectors
        """
        primary = selector_config.get('primary')
        fallbacks = selector_config.get('fallback', [])
        
        all_selectors = [primary] + fallbacks if primary else fallbacks
        
        for i, selector in enumerate(all_selectors):
            try:
                img_element = soup.select_one(selector)
                if img_element:
                    img_url = img_element.get('src') or img_element.get('data-src')
                    if img_url:
                        confidence = 1.0 - (i * 0.15)
                        return img_url, confidence
            except Exception as e:
                logger.debug(f"Image selector failed: {selector} - {e}")
                continue
        
        return None, 0.0
    
    def _tier2_metadata_extraction(self, soup: BeautifulSoup, result: ExtractionResult,
                                  site_name: str) -> ExtractionResult:
        """
        Tier 2: Extract from JSON-LD, OpenGraph, Twitter Card metadata
        """
        confidence_scores = result.confidence_scores or {}
        
        # Try JSON-LD
        if not result.title or not result.content:
            ld_data = self._extract_json_ld(soup)
            if ld_data:
                if not result.title and ld_data.get('headline'):
                    result.title = ld_data['headline']
                    confidence_scores['title'] = 0.85
                if not result.content and ld_data.get('articleBody'):
                    result.content = ld_data['articleBody']
                    confidence_scores['content'] = 0.85
                if not result.author and ld_data.get('author'):
                    result.author = ld_data['author']
                    confidence_scores['author'] = 0.80
                if not result.date and ld_data.get('datePublished'):
                    result.date = ld_data['datePublished']
                    confidence_scores['date'] = 0.90
        
        # Try OpenGraph tags
        og_data = self._extract_og_tags(soup)
        if og_data:
            if not result.title and og_data.get('title'):
                result.title = og_data['title']
                confidence_scores['title'] = 0.75
            if not result.image_url and og_data.get('image'):
                result.image_url = og_data['image']
                confidence_scores['image_url'] = 0.80
        
        # Try Twitter Card
        twitter_data = self._extract_twitter_card(soup)
        if twitter_data and not result.title and twitter_data.get('title'):
            result.title = twitter_data['title']
            confidence_scores['title'] = 0.70
        
        result.confidence_scores = confidence_scores
        return result
    
    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract Article data from JSON-LD schema"""
        try:
            ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in ld_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle both single object and array
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') in ['NewsArticle', 'Article']:
                                return item
                    elif data.get('@type') in ['NewsArticle', 'Article']:
                        return data
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.debug(f"JSON-LD extraction failed: {e}")
        
        return None
    
    def _extract_og_tags(self, soup: BeautifulSoup) -> Dict:
        """Extract OpenGraph metadata"""
        og_data = {}
        try:
            og_tags = soup.find_all('meta', property=re.compile(r'^og:'))
            for tag in og_tags:
                prop = tag.get('property', '')
                content = tag.get('content', '')
                prop_name = prop.replace('og:', '')
                og_data[prop_name] = content
        except Exception as e:
            logger.debug(f"OpenGraph extraction failed: {e}")
        
        return og_data
    
    def _extract_twitter_card(self, soup: BeautifulSoup) -> Dict:
        """Extract Twitter Card metadata"""
        twitter_data = {}
        try:
            twitter_tags = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})
            for tag in twitter_tags:
                name = tag.get('name', '')
                content = tag.get('content', '')
                name_key = name.replace('twitter:', '')
                twitter_data[name_key] = content
        except Exception as e:
            logger.debug(f"Twitter Card extraction failed: {e}")
        
        return twitter_data
    
    def _tier3_heuristic_analysis(self, soup: BeautifulSoup, result: ExtractionResult,
                                 site_name: str) -> ExtractionResult:
        """
        Tier 3: Heuristic-based extraction using text density analysis
        """
        confidence_scores = result.confidence_scores or {}
        
        # Extract title via heuristics
        if not result.title:
            title = self._find_title_heuristic(soup)
            if title:
                result.title = title
                confidence_scores['title'] = 0.60
        
        # Extract content via text density
        if not result.content:
            content = self._find_content_by_density(soup)
            if content:
                result.content = content
                confidence_scores['content'] = 0.55
        
        # Extract author via heuristics
        if not result.author:
            author = self._find_author_heuristic(soup)
            if author:
                result.author = author
                confidence_scores['author'] = 0.50
        
        # Extract date via heuristics
        if not result.date:
            date_str = self._find_date_heuristic(soup)
            if date_str:
                result.date = date_str
                confidence_scores['date'] = 0.50
        
        result.confidence_scores = confidence_scores
        return result
    
    def _find_title_heuristic(self, soup: BeautifulSoup) -> Optional[str]:
        """Find title using heuristics"""
        # Prefer first H1
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
            if 10 <= len(title) <= 500:
                return title
        
        # Look for largest heading
        for heading_tag in ['h2', 'h3', 'h4']:
            heading = soup.find(heading_tag)
            if heading:
                title = heading.get_text(strip=True)
                if 10 <= len(title) <= 500:
                    return title
        
        # Use page title
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove site name suffix (e.g., "Article Title | Site Name")
            if '|' in title:
                title = title.split('|')[0].strip()
            if 10 <= len(title) <= 500:
                return title
        
        return None
    
    def _find_content_by_density(self, soup: BeautifulSoup) -> Optional[str]:
        """Find main content using text density heuristics"""
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'navigation', 'header', 'footer']):
            element.decompose()
        
        # Find potential content containers
        candidates = []
        
        for container in soup.find_all(['article', 'div', 'section']):
            # Skip very small containers
            text = container.get_text(strip=True)
            if len(text) < 100:
                continue
            
            # Calculate text density
            paragraphs = container.find_all('p')
            if not paragraphs:
                continue
            
            paragraph_count = len(paragraphs)
            total_text = sum(len(p.get_text(strip=True)) for p in paragraphs)
            
            # Count links
            links = container.find_all('a')
            link_text_length = sum(len(a.get_text(strip=True)) for a in links)
            
            # Calculate metrics
            word_count = len(text.split())
            paragraph_density = paragraph_count / max(1, len(container.find_all(['p', 'div'])))
            link_density = link_text_length / max(1, total_text)
            avg_paragraph_length = word_count / max(1, paragraph_count)
            
            # Score this container
            score = 0
            if paragraph_count >= 3:
                score += paragraph_count * 10
            if word_count >= 500:
                score += 50
            if link_density <= 0.30:
                score += 30
            if avg_paragraph_length >= 50:
                score += 20
            
            if score > 0:
                candidates.append((score, container, paragraphs))
        
        if candidates:
            # Get highest scoring container
            candidates.sort(reverse=True, key=lambda x: x[0])
            _, best_container, paragraphs = candidates[0]
            
            content = '\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            if len(content) >= 100:
                return content
        
        return None
    
    def _find_author_heuristic(self, soup: BeautifulSoup) -> Optional[str]:
        """Find author using heuristics"""
        # Look for common author patterns
        patterns = [
            r'^[Bb]y\s+(.+?)(?:\s+on\s+|$)',
            r'^[Ww]ritten\s+by\s+(.+?)(?:\s+on\s+|$)',
        ]
        
        # Search in visible text
        body_text = soup.get_text()
        for pattern in patterns:
            match = re.search(pattern, body_text[:500])  # Search first 500 chars
            if match:
                return match.group(1).strip()
        
        # Look for author elements
        author_elements = soup.find_all(['span', 'div'], class_=re.compile(r'author|byline|writer', re.I))
        if author_elements:
            author_text = author_elements[0].get_text(strip=True)
            if author_text:
                return author_text
        
        return None
    
    def _find_date_heuristic(self, soup: BeautifulSoup) -> Optional[str]:
        """Find date using heuristics"""
        # Look for time elements
        time_elem = soup.find('time')
        if time_elem and time_elem.get('datetime'):
            return time_elem.get('datetime')
        
        # Look for date patterns in text
        date_patterns = [
            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b',
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}/\d{1,2}/\d{4})\b',
        ]
        
        body_text = soup.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, body_text)
            if match:
                return match.group(1)
        
        return None
    
    def _tier4_log_failure(self, html: str, url: str, site_name: str, result: ExtractionResult):
        """
        Tier 4: Log failure for manual review
        """
        failure_id = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Create failure log directory for this site
        site_failures_dir = self.failed_extractions_dir / site_name
        site_failures_dir.mkdir(exist_ok=True)
        
        # Log HTML content
        html_file = site_failures_dir / f"{failure_id}_page.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        # Log metadata and what we tried to extract
        metadata = {
            'failure_id': failure_id,
            'url': url,
            'site': site_name,
            'timestamp': datetime.utcnow().isoformat(),
            'what_we_found': {
                'title': result.title,
                'content_length': len(result.content) if result.content else 0,
                'author': result.author,
                'date': result.date,
            },
            'html_file': str(html_file),
            'reason': 'All four extraction tiers failed'
        }
        
        metadata_file = site_failures_dir / f"{failure_id}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.warning(f"Logged failed extraction to {metadata_file}")
