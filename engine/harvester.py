"""
Harvester Module: Async extraction of articles from discovered URLs
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import time

try:
    from curl_cffi.requests import AsyncSession, Session
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    import aiohttp

from engine.extraction_logic import ExtractionEngine
from utils.proxy_manager import ProxyManager, AdaptiveThrottler, Session as ProxySession
from utils.date_normalizer import DateNormalizer
from utils.cleaner import ContentCleaner

logger = logging.getLogger(__name__)


class Harvester:
    """
    Async harvester for extracting article content from URLs
    """
    
    def __init__(self, config: Dict, scout, max_concurrent: int = 5,
                 output_file: str = "data/articles.json",
                 use_curl_cffi: bool = True):
        """
        Initialize Harvester
        
        Args:
            config: Site configuration
            scout: Scout module instance for URL queue
            max_concurrent: Maximum concurrent extraction tasks
            output_file: Path to save extracted articles
            use_curl_cffi: Whether to use curl_cffi for TLS mimicry
        """
        self.config = config
        self.scout = scout
        self.max_concurrent = max_concurrent
        self.output_file = Path(output_file)
        self.use_curl_cffi = use_curl_cffi and HAS_CURL_CFFI
        
        # Initialize components
        self.extraction_engine = ExtractionEngine(config)
        self.proxy_manager = ProxyManager()
        self.throttler = AdaptiveThrottler(config)
        self.date_normalizer = DateNormalizer()
        self.cleaner = ContentCleaner(config)
        
        # Storage
        self.articles = self._load_articles()
        self.processed_urls = set(a['url'] for a in self.articles)
        
        # Metrics
        self.stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'start_time': datetime.utcnow(),
        }
    
    def _load_articles(self) -> List[Dict]:
        """Load existing articles"""
        if self.output_file.exists():
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load articles: {e}")
        return []
    
    def _save_articles(self):
        """Save articles to file"""
        try:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.articles, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.articles)} articles to {self.output_file}")
        except Exception as e:
            logger.error(f"Failed to save articles: {e}")
    
    async def harvest(self, site_name: str = None, batch_size: int = 20):
        """
        Start harvesting articles
        
        Args:
            site_name: Specific site to harvest, or None for all
            batch_size: Number of URLs to process per batch
        """
        logger.info("Harvester starting...")
        
        while True:
            # Get next batch of URLs
            urls = self.scout.get_next_urls(count=batch_size, site=site_name)
            
            if not urls:
                logger.info("No more URLs to process")
                break
            
            logger.info(f"Processing batch of {len(urls)} URLs")
            
            # Process batch concurrently
            await self._process_batch(urls)
            
            # Save progress
            self._save_articles()
            self._print_stats()
        
        logger.info("Harvesting complete")
        self._print_stats()
    
    async def _process_batch(self, url_items: List[Dict]):
        """Process a batch of URLs concurrently"""
        
        # Create tasks with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        tasks = [
            self._harvest_single_with_limit(semaphore, item)
            for item in url_items
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _harvest_single_with_limit(self, semaphore: asyncio.Semaphore, url_item: Dict):
        """Process single URL with concurrency limit"""
        async with semaphore:
            await self._harvest_single(url_item)
    
    async def _harvest_single(self, url_item: Dict):
        """
        Harvest single article
        
        Args:
            url_item: Item from scout queue with 'url', 'site', 'section' keys
        """
        url = url_item['url']
        site_name = url_item['site']
        section_name = url_item['section']
        
        # Skip if already processed
        if url in self.processed_urls:
            logger.debug(f"Skipping already processed: {url}")
            return
        
        self.stats['processed'] += 1
        start_time = time.time()
        
        try:
            # Create or get session
            session = self.proxy_manager.create_session()
            
            # Fetch article
            html = await self._fetch_with_session(session, url, site_name)
            if not html:
                raise Exception("Failed to fetch HTML")
            
            # Extract article
            result = self.extraction_engine.extract(
                html=html,
                url=url,
                site_name=site_name,
                category=section_name
            )
            
            # Normalize dates
            if result.date:
                normalized_date, _ = self.date_normalizer.normalize(result.date)
                result.date = normalized_date
            
            # Normalize data
            article_dict = result.to_dict()
            normalized = self.cleaner.normalize_output(article_dict)
            
            # Validate
            is_valid, errors = self.cleaner.validate_article(normalized)
            
            if not is_valid:
                logger.warning(f"Validation failed for {url}: {errors}")
                self.scout.mark_url_processed(url, success=False, error=str(errors))
                self.stats['failed'] += 1
                self.proxy_manager.mark_request_failure(session.session_id)
                return
            
            # Store article
            self.articles.append(normalized)
            self.processed_urls.add(url)
            self.stats['successful'] += 1
            
            duration = time.time() - start_time
            logger.info(f"✓ Harvested {url} ({duration:.1f}s)")
            
            # Mark as processed
            self.scout.mark_url_processed(url, success=True)
            self.proxy_manager.mark_request_success(session.session_id)
            
            # Throttle
            site_config = self.config['sites'].get(site_name, {})
            self.throttler.wait_if_needed(
                urlparse(url).netloc,
                site_config,
                last_response_time=duration
            )
            
        except Exception as e:
            logger.error(f"Error harvesting {url}: {e}")
            self.scout.mark_url_processed(url, success=False, error=str(e))
            self.stats['failed'] += 1
            if 'session' in locals():
                self.proxy_manager.mark_request_failure(session.session_id)
    
    async def _fetch_with_session(self, session: ProxySession, url: str,
                                  site_name: str) -> Optional[str]:
        """
        Fetch URL using session with proxy and TLS mimicry
        
        Args:
            session: Proxy session with fingerprint
            url: URL to fetch
            site_name: Site identifier
        
        Returns:
            HTML content or None
        """
        site_config = self.config['sites'].get(site_name, {})
        timeout = site_config.get('default_timeout', 15)
        
        try:
            if self.use_curl_cffi:
                return await self._fetch_curl_cffi(session, url, timeout)
            else:
                return await self._fetch_aiohttp(session, url, timeout)
        except Exception as e:
            logger.error(f"Fetch failed for {url}: {e}")
            return None
    
    async def _fetch_curl_cffi(self, session: ProxySession, url: str,
                              timeout: int) -> Optional[str]:
        """Fetch with curl_cffi (better TLS mimicry)"""
        proxy_url = session.proxy.to_http_proxy()
        headers = session.fingerprint.to_headers()
        
        try:
            # curl_cffi expects proxies as dict: {'http': url, 'https': url}
            proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None
            async with AsyncSession(proxies=proxies, timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.text
                else:
                    logger.warning(f"HTTP {resp.status_code} from {url}")
                    return None
        except Exception as e:
            logger.error(f"curl_cffi fetch failed: {e}")
            return None
    
    async def _fetch_aiohttp(self, session: ProxySession, url: str,
                            timeout: int) -> Optional[str]:
        """Fallback fetch with aiohttp"""
        proxy_url = session.proxy.to_http_proxy()
        headers = session.fingerprint.to_headers()
        
        try:
            import aiohttp
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=client_timeout) as client:
                async with client.get(url, proxy=proxy_url, headers=headers, ssl=False) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    else:
                        logger.warning(f"HTTP {resp.status} from {url}")
                        return None
        except Exception as e:
            logger.error(f"aiohttp fetch failed: {e}")
            return None
    
    def _print_stats(self):
        """Print harvester statistics"""
        elapsed = (datetime.utcnow() - self.stats['start_time']).total_seconds()
        rate = self.stats['processed'] / elapsed if elapsed > 0 else 0
        
        logger.info(
            f"\n=== HARVESTER STATS ===\n"
            f"Processed: {self.stats['processed']}\n"
            f"Successful: {self.stats['successful']}\n"
            f"Failed: {self.stats['failed']}\n"
            f"Rate: {rate:.1f} articles/sec\n"
            f"Elapsed: {elapsed:.0f}s\n"
            f"Total articles: {len(self.articles)}\n"
            f"=======================\n"
        )
    
    def get_stats(self) -> Dict:
        """Get harvester statistics"""
        return {
            **self.stats,
            'total_articles': len(self.articles),
            'proxy_stats': self.proxy_manager.get_proxy_stats(),
            'queue_stats': self.scout.get_queue_stats(),
        }


from urllib.parse import urlparse
