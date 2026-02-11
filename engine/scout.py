"""
Scout Module: Discovers article URLs from news sites
Pure navigation - finds URLs rapidly without deep extraction
"""

import asyncio
import logging
from typing import Set, List, Dict, Optional
from pathlib import Path
from urllib.parse import urljoin, urlparse
import json
from datetime import datetime
import hashlib

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class Scout:
    """
    URL discovery module - finds article links across site sections
    """
    
    def __init__(self, config: Dict, queue_file: str = "data/url_queue.json"):
        """
        Initialize Scout
        
        Args:
            config: Site configuration from sites_config.yaml
            queue_file: Path to persistent URL queue
        """
        self.config = config
        self.queue_file = Path(queue_file)
        self.url_queue = self._load_queue()
        self.seen_urls: Set[str] = set(item['url'] for item in self.url_queue)
    
    def _load_queue(self) -> List[Dict]:
        """Load existing URL queue from file"""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load queue: {e}")
        return []
    
    def _save_queue(self):
        """Persist URL queue to file"""
        try:
            self.queue_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.queue_file, 'w') as f:
                json.dump(self.url_queue, f, indent=2, default=str)
            logger.debug(f"Saved {len(self.url_queue)} URLs to queue")
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")
    
    async def discover_urls(self, site_name: str, max_pages_per_section: int = 5):
        """
        Discover article URLs from a site
        
        Args:
            site_name: Site identifier (e.g., 'the-star')
            max_pages_per_section: Max pages to scan per section
        """
        site_config = self.config['sites'].get(site_name)
        if not site_config:
            logger.error(f"Site config not found: {site_name}")
            return
        
        # Clear queue for fresh discovery of this specific site
        self.url_queue = []
        self.seen_urls = set()
        logger.info(f"Starting Scout for {site_name} (cleared previous queue)")
        
        entry_points = site_config.get('entry_points', [])
        base_url = site_config.get('base_url', '')
        
        async with aiohttp.ClientSession() as session:
            for entry in entry_points:
                section_url = urljoin(base_url, entry['path'])
                section_name = entry.get('name', entry['path'])
                
                logger.info(f"Scouting {section_name}: {section_url}")
                await self._scout_section(
                    session,
                    section_url,
                    site_name,
                    section_name,
                    max_pages_per_section,
                    site_config
                )
        
        self._save_queue()
        logger.info(f"Scout complete. Queue size: {len(self.url_queue)}")
    
    async def _scout_section(self, session: aiohttp.ClientSession, url: str,
                            site_name: str, section_name: str,
                            max_pages: int, site_config: Dict):
        """
        Scout a single section/category
        """
        visited = set()
        current_url = url
        page_count = 0
        
        while current_url and current_url not in visited and page_count < max_pages:
            visited.add(current_url)
            page_count += 1
            
            logger.info(f"Scouting page {page_count}: {current_url}")
            
            try:
                html = await self._fetch_url(session, current_url, site_config)
                if not html:
                    break
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract article links from this page
                article_urls = self._extract_article_links(soup, current_url, site_name, section_name)
                logger.info(f"Found {len(article_urls)} articles on page {page_count}")
                
                # Get next page URL
                current_url = self._find_next_page(soup, current_url, site_config)
                
            except Exception as e:
                logger.error(f"Scout error on {current_url}: {e}")
                break
            
            await asyncio.sleep(1)  # Rate limiting
    
    async def _fetch_url(self, session: aiohttp.ClientSession, url: str,
                        site_config: Dict) -> Optional[str]:
        """Fetch URL with error handling"""
        try:
            timeout = aiohttp.ClientTimeout(total=site_config.get('global', {}).get('default_timeout', 15))
            async with session.get(url, timeout=timeout, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    logger.warning(f"Failed to fetch {url}: {resp.status}")
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _extract_article_links(self, soup: BeautifulSoup, page_url: str,
                              site_name: str, section_name: str) -> List[str]:
        """
        Extract article URLs from page
        """
        article_urls = []
        
        # Find all links on page
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert to absolute URL
            if not href.startswith('http'):
                href = urljoin(page_url, href)
            
            # Filter out non-articles
            if self._is_article_url(href, site_name):
                # Avoid duplicates
                if href not in self.seen_urls:
                    self.url_queue.append({
                        'url': href,
                        'site': site_name,
                        'section': section_name,
                        'discovered_at': datetime.utcnow().isoformat(),
                        'status': 'new',
                        'priority': self._calculate_priority(section_name),
                        'retry_count': 0,
                        'last_error': None,
                    })
                    self.seen_urls.add(href)
                    article_urls.append(href)
        
        return article_urls
    
    def _is_article_url(self, url: str, site_name: str) -> bool:
        """
        Determine if URL is likely an article
        """
        path = urlparse(url).path.lower()
        
        # Filter out obvious non-articles
        exclude_patterns = [
            '/search', '/contact', '/about', '/subscribe', '/login', '/register',
            '/page/', '/category/', '/tag/', '/author/', '/sitemap', '.pdf', '.jpg', '.png',
            '/ads', '/help', '/privacy', '/terms', '/feed', '/rss'
        ]
        
        for pattern in exclude_patterns:
            if pattern in path:
                return False
        
        # Look for article indicators
        include_patterns = [
            '/article/', '/story/', '/news/', '/post/', '/blog/',
            '/[0-9]{4}/[0-9]{2}',  # Date in path
        ]
        
        for pattern in include_patterns:
            import re
            if re.search(pattern, path):
                return True
        
        # If hostname is article-like subdomain
        domain = urlparse(url).netloc
        if any(x in domain for x in ['article', 'news', 'story']):
            return True
        
        # Heuristic: if path is deep enough and not just category
        path_segments = [s for s in path.split('/') if s]
        if len(path_segments) >= 3:
            return True
        
        return False
    
    def _find_next_page(self, soup: BeautifulSoup, current_url: str,
                       site_config: Dict) -> Optional[str]:
        """
        Find next page URL based on pagination config
        """
        pagination = site_config.get('pagination', {})
        pagination_type = pagination.get('type', 'button_load_more')
        
        if pagination_type == 'button_load_more':
            return self._find_load_more_next_page(soup, current_url, pagination)
        elif pagination_type == 'url_param':
            return self._find_url_param_next_page(soup, current_url, pagination)
        else:
            return None
    
    def _find_load_more_next_page(self, soup: BeautifulSoup, current_url: str,
                                 pagination_config: Dict) -> Optional[str]:
        """Find next page from 'Load More' button pagination"""
        selector = pagination_config.get('selector', "button:contains('load more articles')")
        
        # Simple button detection (CSS selector with contains is limited in BeautifulSoup)
        button = soup.find('button', string=lambda s: s and 'load more' in s.lower())
        
        if button and button.parent:
            if button.parent.name == 'a':
                href = button.parent.get('href')
                if href:
                    return urljoin(current_url, href)
        
        return None
    
    def _find_url_param_next_page(self, soup: BeautifulSoup, current_url: str,
                                 pagination_config: Dict) -> Optional[str]:
        """Find next page from URL parameter pagination"""
        param_name = pagination_config.get('url_param_name', 'start')
        increment = pagination_config.get('param_increment', 24)
        
        # Extract current parameter value
        from urllib.parse import parse_qs, urlencode, urlparse as parse_url, urlunparse
        
        parsed = parse_url(current_url)
        query_params = parse_qs(parsed.query)
        
        # Get current start value
        current_start = int(query_params.get(param_name, ['0'])[0])
        next_start = current_start + increment
        
        # Update parameter
        query_params[param_name] = [str(next_start)]
        
        # Reconstruct URL
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        
        return new_url
    
    def _calculate_priority(self, section_name: str) -> float:
        """Calculate priority score for URL (higher = more urgent)"""
        # Prioritize news/breaking over archives
        priority_keywords = {
            'homepage': 1.0,
            'breaking': 0.95,
            'latest': 0.90,
            'today': 0.85,
            'recent': 0.80,
            'archive': 0.30,
        }
        
        for keyword, score in priority_keywords.items():
            if keyword in section_name.lower():
                return score
        
        return 0.5  # Default priority
    
    def get_queue_stats(self) -> Dict:
        """Get statistics about URL queue"""
        by_status = {}
        by_site = {}
        by_section = {}
        
        for item in self.url_queue:
            status = item.get('status', 'unknown')
            site = item.get('site', 'unknown')
            section = item.get('section', 'unknown')
            
            by_status[status] = by_status.get(status, 0) + 1
            by_site[site] = by_site.get(site, 0) + 1
            by_section[section] = by_section.get(section, 0) + 1
        
        return {
            'total_urls': len(self.url_queue),
            'by_status': by_status,
            'by_site': by_site,
            'by_section': by_section,
        }
    
    def get_next_urls(self, count: int = 10, site: Optional[str] = None) -> List[Dict]:
        """Get next URLs to process from queue"""
        # Filter by status and site
        candidates = [
            item for item in self.url_queue
            if item.get('status') == 'new'
            and (site is None or item.get('site') == site)
        ]
        
        logger.debug(f"Queue has {len(self.url_queue)} total items. Filtering by status='new' and site='{site}': found {len(candidates)} candidates")
        
        # Sort by priority (higher first)
        candidates.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        # Return top N
        selected = candidates[:count]
        
        # Mark as in_progress
        for item in selected:
            item['status'] = 'in_progress'
        
        self._save_queue()
        return selected
    
    def mark_url_processed(self, url: str, success: bool, error: Optional[str] = None):
        """Mark URL as processed"""
        for item in self.url_queue:
            if item['url'] == url:
                item['status'] = 'completed' if success else 'failed'
                item['last_error'] = error
                self._save_queue()
                return
