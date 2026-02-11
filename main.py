"""
SCRAP!T - Universal News Scraper

Configuration-driven scraper with:
- Declarative site configuration (sites_config.yaml)
- Four-tier fallback extraction system
- Decoupled Scout/Harvester architecture
- Sticky sessions with TLS mimicry
- Standardized data pipeline
"""

import asyncio
import json
import logging
import argparse
from pathlib import Path
from typing import AsyncIterator

import yaml

from engine.scout import Scout
from engine.harvester import Harvester

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class UniversalScraper:
    """
    SCRAP!T - Main coordinating class for the universal news scraper
    """
    
    def __init__(self, config_file: str = "sites_config.yaml"):
        """
        Initialize scraper
        
        Args:
            config_file: Path to sites_config.yaml
        """
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
        # Create data directory
        Path("data").mkdir(exist_ok=True)
    
    def _load_config(self) -> dict:
        """Load configuration from YAML"""
        if not self.config_file.exists():
            logger.error(f"Config file not found: {self.config_file}")
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_file}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def _find_site_key(self, site_arg: str) -> str:
        """
        Map a user-provided site argument (URL or partial) to the config key (full URL).
        If not found, return None (for generic fallback mode).
        """
        if not site_arg:
            return None
        site_arg = site_arg.strip().lower().rstrip('/')
        for key in self.config['sites'].keys():
            key_norm = key.strip().lower().rstrip('/')
            if site_arg == key_norm:
                return key
            if site_arg in key_norm:
                return key
            # Allow matching by domain
            if site_arg in key_norm.replace('https://','').replace('http://',''):
                return key
        # Not found: return None for generic fallback
        logger.warning(f"Site '{site_arg}' not found in config. Proceeding in generic fallback mode.")
        return None

    async def run_scout(self, site_name: str = None, max_pages_per_section: int = 5):
        """
        Run Scout to discover article URLs
        
        Args:
            site_name: Specific site to scout, or None for all configured sites
            max_pages_per_section: Max pages to scan per section
        """
        scout = Scout(self.config)
        
        if site_name:
            site_key = self._find_site_key(site_name)
            if site_key:
                logger.info(f"Scouting site: {site_key}")
                await scout.discover_urls(site_key, max_pages_per_section)
            else:
                # Generic fallback: pass the raw URL as the site key
                logger.info(f"Scouting site (generic fallback): {site_name}")
                await scout.discover_urls(site_name, max_pages_per_section)
        else:
            # Scout all configured sites
            for site in self.config['sites'].keys():
                logger.info(f"Scouting site: {site}")
                await scout.discover_urls(site, max_pages_per_section)
        
        # Print queue stats
        stats = scout.get_queue_stats()
        logger.info(f"Scout complete. Queue stats: {json.dumps(stats, indent=2)}")
        
        return scout
    
    async def run_harvester(self, site_name: str = None, max_concurrent: int = 5,
                           batch_size: int = 20):
        """
        Run Harvester to extract articles
        
        Args:
            site_name: Specific site to harvest, or None for all
            max_concurrent: Maximum concurrent extraction tasks
            batch_size: URLs per batch
        """
        scout = Scout(self.config)
        harvester = Harvester(self.config, scout, max_concurrent=max_concurrent)
        
        if site_name:
            site_key = self._find_site_key(site_name)
            if site_key:
                logger.info(f"Starting harvester (max_concurrent={max_concurrent}) for {site_key}")
                await harvester.harvest(site_name=site_key, batch_size=batch_size)
            else:
                logger.info(f"Starting harvester (generic fallback) for {site_name}")
                await harvester.harvest(site_name=site_name, batch_size=batch_size)
        else:
            logger.info(f"Starting harvester (max_concurrent={max_concurrent}) for all configured sites")
            await harvester.harvest(site_name=None, batch_size=batch_size)
        
        # Print final stats
        final_stats = harvester.get_stats()
        logger.info(f"Harvester stats: {json.dumps(final_stats, indent=2, default=str)}")
        
        return harvester
    
    async def run_full_pipeline(self, site_name: str = None, max_pages_per_section: int = 5,
                              max_concurrent: int = 5, batch_size: int = 20):
        """
        Run full pipeline: Scout → Harvest
        
        Args:
            site_name: Specific site to process, or None for all
            max_pages_per_section: Pages to scan per section
            max_concurrent: Concurrent extraction tasks
            batch_size: URLs per harvester batch
        """
        logger.info("Starting full pipeline")
        
        # Scout phase
        logger.info("\n" + "="*60)
        logger.info("PHASE 1: DISCOVERY (Scout)")
        logger.info("="*60)
        scout = Scout(self.config)
        
        if site_name:
            site_key = self._find_site_key(site_name)
            if site_key:
                await scout.discover_urls(site_key, max_pages_per_section)
            else:
                await scout.discover_urls(site_name, max_pages_per_section)
        else:
            for site in self.config['sites'].keys():
                await scout.discover_urls(site, max_pages_per_section)
        
        queue_stats = scout.get_queue_stats()
        logger.info(f"Discovery complete: {queue_stats['total_urls']} URLs found")
        
        # Harvester phase
        logger.info("\n" + "="*60)
        logger.info("PHASE 2: EXTRACTION (Harvester)")
        logger.info("="*60)
        harvester = Harvester(self.config, scout, max_concurrent=max_concurrent)
        
        if site_name:
            if site_key:
                await harvester.harvest(site_name=site_key, batch_size=batch_size)
            else:
                await harvester.harvest(site_name=site_name, batch_size=batch_size)
        else:
            await harvester.harvest(site_name=None, batch_size=batch_size)
        
        final_stats = harvester.get_stats()
        logger.info(f"\n" + "="*60)
        logger.info("PIPELINE COMPLETE")
        logger.info("="*60)
        logger.info(f"Total articles: {final_stats['total_articles']}")
        logger.info(f"Successful: {final_stats['successful']}")
        logger.info(f"Failed: {final_stats['failed']}")
        logger.info("="*60)
        
        return scout, harvester


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='SCRAP!T - Configuration-driven web scraping'
    )
    
    parser.add_argument(
        'command',
        choices=['scout', 'harvest', 'full'],
        help='Scraper command: scout=discover URLs, harvest=extract articles, full=both'
    )
    
    parser.add_argument(
        '--config',
        default='sites_config.yaml',
        help='Path to sites_config.yaml (default: sites_config.yaml)'
    )
    
    parser.add_argument(
        '--site',
        help='Specific site to process (e.g., "https://www.the-star.co.ke")'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=5,
        help='Max pages to scan per section (default: 5)'
    )
    
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=5,
        help='Max concurrent extraction tasks (default: 5)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=20,
        help='URLs per harvester batch (default: 20)'
    )
    
    args = parser.parse_args()
    
    # Initialize scraper
    try:
        scraper = UniversalScraper(args.config)
    except Exception as e:
        logger.error(f"Failed to initialize scraper: {e}")
        return 1
    
    # Run requested command
    try:
        if args.command == 'scout':
            asyncio.run(
                scraper.run_scout(
                    site_name=args.site,
                    max_pages_per_section=args.max_pages
                )
            )
        elif args.command == 'harvest':
            asyncio.run(
                scraper.run_harvester(
                    site_name=args.site,
                    max_concurrent=args.max_concurrent,
                    batch_size=args.batch_size
                )
            )
        elif args.command == 'full':
            asyncio.run(
                scraper.run_full_pipeline(
                    site_name=args.site,
                    max_pages_per_section=args.max_pages,
                    max_concurrent=args.max_concurrent,
                    batch_size=args.batch_size
                )
            )
    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Scraper error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
