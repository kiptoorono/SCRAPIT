# SCRAP!T - Universal News Scraper

![SCRAP!T Logo](src/Scrapit.png)

**A production-grade, fully configuration-driven news scraper** with advanced anti-detection and modular extraction. No site-specific logic in code—all configuration lives in `sites_config.yaml`.

## Table of Contents

- [Features](#features)
- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Configuration Guide](#configuration-guide)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Features

- **Configuration-Driven**: Zero hardcoded site logic. All configuration in YAML.
- **Four-Tier Extraction**: Progressive fallback from CSS selectors to heuristics to metadata.
- **Anti-Detection**: Browser fingerprinting, TLS mimicry, sticky sessions, adaptive throttling.
- **Proxy Support**: Intelligent proxy rotation with health monitoring and cooldowns.
- **Resumable**: Scout and Harvester persist state. Stop and resume without data loss.
- **Scalable**: Configurable concurrency, batch processing, and per-site rate limiting.
- **Failure Tracking**: Detailed logs of failed extractions for iterative config improvement.

## System Requirements

- Python 3.8 or higher
- Windows, macOS, or Linux
- 500MB+ disk space for article storage
- Internet connection with optional proxy support

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Proxies (Optional)

Edit `proxies.json` with your proxy credentials:

```json
[
  {
    "address": "proxy.example.com",
    "port": "8080",
    "username": "user",
    "password": "pass"
  }
]
```

If no proxies provided, system will make direct requests.

### 3. Run Full Pipeline (Scout + Extract)

```bash
# Discover and extract all configured sites
python main.py full

# Specific site
python main.py full --site the-star --max-pages 6
```

Articles saved to `data/articles.json`.

### 4. Or Use Separated Scout/Harvester

```bash
# Discover URLs
python main.py scout --site the-star --max-pages 10

# Extract articles
python main.py harvest --max-concurrent 10
```

## How It Works

### Architecture Overview

#### Four-Tier Fallback Extraction System

| Tier | Method | Speed | Reliability | Coverage |
|------|--------|-------|-------------|----------|
| 1 | CSS Selectors (from config) | Very Fast | Very High | 85-95% |
| 2 | Metadata (JSON-LD, OG, Twitter) | Fast | High | 5-10% |
| 3 | Text Density Heuristics | Medium | Medium | 2-5% |
| 4 | Human Loop (failure logs) | Manual | N/A | <1% |

Extract HTML → Tier 1 (CSS) → Tier 2 (Metadata) → Tier 3 (Heuristics) → Tier 4 (Log & Manual Review)

#### Module Architecture

```
┌─────────────────────────────────────────────┐
│         SCRAP!T Pipeline                    │
├─────────────────────────────────────────────┤
│                                             │
│  SCOUT (URL Discovery)                      │
│  ├─ Navigate configured sites               │
│  ├─ Follow pagination                       │
│  └─ Persist URLs to data/url_queue.json     │
│                  ↓                          │
│  HARVESTER (Article Extraction)             │
│  ├─ Read from url_queue.json                │
│  ├─ Concurrent requests (configurable)      │
│  └─ Apply four-tier extraction              │
│                  ↓                          │
│  EXTRACTION ENGINE (Four Tiers)             │
│  ├─ Tier 1: CSS Selectors                   │
│  ├─ Tier 2: Metadata (JSON-LD, OG)          │
│  ├─ Tier 3: Text Density Heuristics         │
│  └─ Tier 4: Log Failures                    │
│                  ↓                          │
│  CLEANING PIPELINE                          │
│  ├─ Boilerplate removal                     │
│  ├─ Date normalization (ISO 8601)           │
│  ├─ Whitespace normalization                │
│  └─ Author/category standardization         │
│                  ↓                          │
│  OUTPUT: data/articles.json                 │
│                                             │
└─────────────────────────────────────────────┘
```

**Scout**: Discovers article URLs across multiple pages and sections. Fast, breadth-first, populates the queue.

**Harvester**: Extracts full article data from the queue. Intensive processing, uses multiple extraction strategies, respects rate limits.

**Proxy Layer**: Maintains sticky sessions (same IP + User-Agent), uses TLS mimicry, adapts throttling, monitors proxy health.

## Folder Structure

```
News scrappers/
├── engine/
│   ├── extraction_logic.py      # Four-tier extraction engine
│   ├── scout.py                 # URL discovery module
│   ├── harvester.py             # Article extraction module
│   └── __init__.py
├── utils/
│   ├── proxy_manager.py         # Proxy pool, sessions, TLS fingerprints
│   ├── date_normalizer.py       # Date parsing and normalization
│   ├── cleaner.py               # Content cleaning pipeline
│   └── __init__.py
├── data/                        # Generated files
│   ├── url_queue.json           # Articles discovered by Scout
│   ├── articles.json            # Extracted articles
│   └── failed_extractions/      # Failed extractions (Tier 4 logs)
├── main.py                      # Entry point
├── sites_config.yaml            # All site-specific configuration
├── proxies.json                 # Proxy credentials
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Configuration Guide

### Configuration Syntax

Edit `sites_config.yaml` to add or modify sites. Here's a complete example:

```yaml
sites:
  my-news-site:
    name: "My News Site"
    domain: "mynewssite.com"
    base_url: "https://www.mynewssite.com"
    
    entry_points:
      - path: "/"
        name: "homepage"
      - path: "/news"
        name: "news_section"
    
    selectors:
      title:
        primary: "h1.headline"
        fallback:
          - "h1"
          - "span.title"
      
      content:
        primary: "div.article-body"
        fallback:
          - "article"
          - "div.story"
      
      author:
        primary: "span.author"
        fallback:
          - "a.byline"
      
      date:
        primary: "time[datetime]"
        fallback:
          - "span.publish-date"
    
    date_patterns:
      - "%B %d, %Y"
      - "%d/%m/%Y %H:%M"
    
    pagination:
      type: "url_param"  # or "button_load_more"
      url_param_name: "page"
      param_increment: 1
    
    rate_limit:
      requests_per_minute: 30
      crawl_delay_override: 2.0
```


## Output Format

Articles are saved in `data/articles.json` with this structure:

```json
{
  "url": "https://example.com/article",
  "title": "Article headline",
  "content": "Full article text with normalized formatting...",
  "author": "Author Name",
  "published_date": "2025-02-11 14:30:00",
  "category": "Politics",
  "tags": ["tag1", "tag2"],
  "image_url": "https://example.com/image.jpg",
  "language": "en",
  "source_site": "the-star",
  "extraction_method": "tier1",
  "confidence_scores": {
    "title": 0.98,
    "content": 0.95,
    "author": 0.85
  }
}
```

## Stealth & Anti-Detection Features

Your scraper maintains legitimate browsing behavior through multiple layers:

### Sticky Sessions

Each browsing session maintains:
- Same proxy/IP throughout lifecycle
- Consistent User-Agent and browser fingerprint
- Accumulated cookies
- Logical referrer chain
- Automatic rotation after N articles or timeout

### Browser Fingerprinting

Multiple realistic fingerprints (Chrome Windows, Chrome Mac, Firefox, Safari) with:
- Matching User-Agent headers
- Browser-specific headers (Sec-Fetch-*, Accept-*)
- Proper header ordering
- TLS fingerprint matching via `curl_cffi`

### Adaptive Request Throttling

- Base rate defined in config (default: 30 requests/minute)
- Automatically reduces if server responds slowly or returns timeouts
- Raises rate if server responds quickly
- Respects robots.txt `crawl-delay` directives
- Adds randomness (±10%) to avoid predictable patterns

### Proxy Health Monitoring

- Tracks success/failure rates per proxy
- Weights selection by success rate (better proxies used more)
- Applies automatic cooldowns on 429 (rate limit) and 403 (forbidden)
- Auto-detects and deprioritizes failing proxies
- Fallback to direct requests if all proxies fail

## Monitoring & Statistics

### Scout Statistics

Get discovered URL stats during or after scouting:

```python
scraper.scout.get_queue_stats()
# Returns:
# {
#   'total_urls': 1250,
#   'by_status': {'new': 800, 'in_progress': 150, 'completed': 300},
#   'by_site': {'the-star': 700, 'the-standard': 550},
#   'by_section': {'politics': 400, 'sports': 300, ...}
# }
```

### Harvester Statistics

Monitor extraction progress:

```python
scraper.harvester.get_stats()
# Returns:
# {
#   'processed': 300,
#   'successful': 285,
#   'failed': 15,
#   'total_articles': 2150,
#   'start_time': '2025-02-11T14:30:00',
#   'proxy_stats': {...}
# }
```

## Failure Tracking (Tier 4)

When all four extraction tiers fail, the system logs detailed failure information:
- Raw HTML: `failed_extractions/{site}/{id}_page.html`
- Extraction metadata: `failed_extractions/{site}/{id}_metadata.json`
- Specific reason for failure and what methods were attempted

Use these logs to iteratively improve `sites_config.yaml`:

```bash
ls data/failed_extractions/the-star/
cat data/failed_extractions/the-star/abc123_metadata.json
```

## Advanced Usage

### Concurrent Extraction

Optimize based on your system resources:

```bash
# Faster but heavier on memory/CPU
python main.py harvest --max-concurrent 20

# Slower but lighter resource usage
python main.py harvest --max-concurrent 2
```

### Batch Size Configuration

```bash
# Larger batches = fewer saves to disk, faster throughput
python main.py harvest --batch-size 100

# Smaller batches = more frequent saves, better checkpoint recovery
python main.py harvest --batch-size 10
```

### Scout Pages Per Section

```bash
# Deep discovery = more URLs found
python main.py scout --max-pages 20

# Quick discovery = fewer URLs
python main.py scout --max-pages 2
```

### Programmatic Usage

Use SCRAP!T as a module in your own Python code:

```python
from engine.extraction_logic import ExtractionEngine
import yaml

# Load configuration
with open('sites_config.yaml') as f:
    config = yaml.safe_load(f)

# Create extraction engine
engine = ExtractionEngine(config)

# Extract from single URL
result = engine.extract(
    html_content,
    url='http://example.com/article',
    site_name='the-star'
)

print(result.to_dict())
```

### Custom Extractors

Extend the extraction system for specialized cases:

```python
from engine.extraction_logic import ExtractionEngine

class CustomExtractor(ExtractionEngine):
    def _tier3_heuristic_analysis(self, soup, result, site_name):
        # Add your custom heuristics here
        return result
```

### Custom Date Formats

Add site-specific date patterns to `sites_config.yaml`:

```yaml
sites:
  my-site:
    date_patterns:
      - "%custom %date %format"
      - "%d-%m-%Y %H:%M"
```

## Testing & Debugging

Enable debug logging to see detailed extraction steps:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

Test single URL extraction:

```python
from engine.extraction_logic import ExtractionEngine
import yaml

with open('sites_config.yaml') as f:
    config = yaml.safe_load(f)

engine = ExtractionEngine(config)
result = engine.extract(html, url='http://example.com', site_name='the-star')
print(result.to_dict())
```

Inspect specific failed extraction:

```bash
ls data/failed_extractions/the-star/
cat data/failed_extractions/the-star/abc123_metadata.json
```

## Ethical & Legal Guidelines

Before deploying SCRAP!T on any site:

- Always check the site's `robots.txt` file
- Respect `crawl-delay` and `request-rate` directives
- Don't overload servers (use appropriate rate limits)
- Review the site's Terms of Service for scraping restrictions
- Consider contacting website owners for permission
- Use scraped data responsibly and legally
- Check local laws regarding web scraping

## Troubleshooting

### Site Returns 403 Forbidden

Multiple extraction requests are being blocked. Try:
- Update User-Agent in config or rotate more frequently
- Rotate proxies more frequently or use different proxies
- Reduce request rate (decrease `requests_per_minute`)
- Check if site requires cookies/JavaScript rendering
- Add custom headers to match legitimate browser requests

### Extraction Confidence Scores Low

Content isn't being reliably extracted from the site:
- Inspect failed extractions in `data/failed_extractions/{site}/`
- Update CSS selectors in `sites_config.yaml` with correct ones
- Add more fallback selectors for robustness
- Check if the site uses JavaScript to render content (may need Playwright)
- Ensure date patterns match the site's date format

### Memory Usage Is High

System is consuming too much RAM:
- Reduce `max-concurrent` parameter (fewer parallel requests)
- Decrease `batch-size` (flush to disk more frequently)
- Clear `data/failed_extractions/` periodically
- Monitor article count in `data/articles.json` and archive old data

### URLs Not Being Discovered

Scout isn't finding articles:
- Check `data/url_queue.json` to see what was found
- Verify entry points in `sites_config.yaml` correctly point to list pages
- Check if pagination configuration matches the site's structure
- Inspect logs for rate limiting or proxy issues
- Manually test URLs with a browser to confirm accessibility

### Proxies Failing Repeatedly

Proxy health monitoring shows consistent failures:
- Verify proxy credentials in `proxies.json` are correct
- Check proxy IP allowlisting (site may require IP registration)
- Test proxies manually: `python test_proxies.py`
- Reduce `requests_per_minute` to avoid triggering rate limits
- Try different proxy provider or disable proxies for testing

## Advanced Topics

### URL Deduplication

System prevents re-scraping the same article:

```python
seen_urls = set(article['url'] for article in self.articles)
```

### Resumable Crawling

Both Scout and Harvester persist state for interruption-safe operation:
- `data/url_queue.json` - resumable discovery state (urls found so far)
- `data/articles.json` - already extracted articles
- Stop and resume without losing progress
- Combine multiple site passes incrementally

### Multi-Site Coordination

Scout and Harvest can be run for specific sites or all sites:

```bash
# Run full pipeline for one site
python main.py full --site the-star

# Run full pipeline for another site
python main.py full --site the-standard

# Both sites share the same article database (data/articles.json)
```

### Confidence Scoring

Each extracted field has a confidence score (0.0 to 1.0):

```json
{
  "title": "Article headline",
  "confidence_scores": {
    "title": 0.98,
    "content": 0.95,
    "author": 0.85
  }
}
```

Scores indicate which extraction tier was used:
- 0.95-1.0: Tier 1 (CSS selectors - most reliable)
- 0.75-0.95: Tier 2 (Metadata extraction)
- 0.50-0.75: Tier 3 (Heuristic analysis)
- Below 0.50: Tier 4 (logged failure, not included)

## Contributing

To improve extraction quality for a site:

1. Run full pipeline: `python main.py full --site site-name`
2. Inspect failed extractions: `ls data/failed_extractions/site-name/`
3. Review failure metadata: `cat data/failed_extractions/site-name/*_metadata.json`
4. Manually inspect source HTML to find correct selectors
5. Update CSS selectors in `sites_config.yaml`
6. Re-test with: `python main.py full --site site-name`
7. When success rate is high, commit improved config

## License

This project is provided as-is for educational purposes.

---

**Built for robust, maintainable, configuration-driven web scraping**
