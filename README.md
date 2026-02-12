# SCRAP!T - Universal News Scraper

![SCRAP!T Logo](src/Scrapit.png)

A production-grade, fully configuration-driven news scraper built with advanced architecture patterns. No site-specific logic in code—all configuration lives in `sites_config.yaml`.

## Architecture Overview

### Four-Tier Fallback Extraction System

1. **Tier 1 (Precision)**: CSS selectors from `sites_config.yaml` - fastest, most reliable
2. **Tier 2 (Semantic)**: Metadata extraction (JSON-LD, OpenGraph, Twitter Card)
3. **Tier 3 (Heuristic)**: Text density analysis to find article content
4. **Tier 4 (Human Loop)**: Logs failures for manual config updates

### Decoupled Scout/Harvester Architecture

- **Scout**: Fast URL discovery module - navigates sites and populates queue
- **Harvester**: Deep extraction module - processes queue asynchronously with concurrency control

### Stealth & Proxy Layer

- **Sticky Sessions**: Maintains same IP + User-Agent for coherent browsing behavior
- **TLS Mimicry**: Uses `curl_cffi` to mimic real browser TLS handshakes
- **Adaptive Throttling**: Adjusts request rates based on server response times
- **Proxy Health Monitoring**: Tracks success/failure rates, applies intelligent cooldowns

### Standardized Pipeline

- Date normalization (ISO 8601)
- Content cleaning (boilerplate removal, whitespace normalization)
- Author standardization
- Category mapping
- Output validation

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

##  Quick Start

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

### 3. Run Scout to Discover URLs

```bash
# Scout all configured sites
python main.py scout

# Scout specific site
python main.py scout --site the-star --max-pages 10
```

This populates `data/url_queue.json` with discovered article URLs.

### 4. Run Harvester to Extract Articles

```bash
# Harvest all queued articles
python main.py harvest

# Harvest with custom concurrency
python main.py harvest --max-concurrent 10 --batch-size 50
```

Articles saved to `data/articles.json`.

### 5. Run Full Pipeline

```bash
# One command: discover + extract
python main.py full --site the-star
```

##  Configuration (`sites_config.yaml`)

### Adding a New Site

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

## 🔄 Extraction Flow

```
HTML → Tier 1 (CSS Selectors)
    ↓ (fails)
    → Tier 2 (JSON-LD, OpenGraph)
    ↓ (fails)
    → Tier 3 (Text Density Heuristics)
    ↓ (fails)
    → Tier 4 (Failure Logged)
```

Each tier has confidence scores assigned to extracted fields.

## 📊 Output Format

Articles saved in `data/articles.json`:

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

## 🛡️ Stealth Features

### Sticky Sessions
- Each "browsing session" maintains:
  - Same proxy/IP throughout lifecycle
  - Consistent User-Agent and browser fingerprint
  - Accumulated cookies
  - Logical referrer chain
- Session rotates after N articles or timeout

### Browser Fingerprints
Multiple realistic fingerprints (Chrome Windows, Chrome Mac, Firefox, etc.) with:
- Matching User-Agent
- Browser-specific headers (Sec-Fetch-*, Accept-*)
- Proper header ordering
- TLS fingerprint matching (with curl_cffi)

### Adaptive Throttling
- Base rate from config
- Adjusts up if server responds quickly
- Adjusts down if server slow or timeouts
- Respects robots.txt crawl-delay
- Adds randomness (±10%) to avoid patterns

### Proxy Health Monitoring
- Tracks success/failure per proxy
- Weights selection by success rate
- Applies cooldowns on 429 (rate limit), 403 (forbidden)
- Auto-detects and deprioritizes failing proxies

##  Monitoring & Statistics

### Scout Statistics

```python
scraper.scout.get_queue_stats()
# {
#   'total_urls': 1250,
#   'by_status': {'new': 800, 'in_progress': 150, 'completed': 300},
#   'by_site': {'the-star': 700, 'the-standard': 550},
#   'by_section': {'politics': 400, 'sports': 300, ...}
# }
```

### Harvester Statistics

```python
scraper.harvester.get_stats()
# {
#   'processed': 300,
#   'successful': 285,
#   'failed': 15,
#   'total_articles': 2150,
#   'start_time': '2025-02-11T14:30:00',
#   'proxy_stats': {...}
# }
```

## 🔍 Failure Analysis (Tier 4)

When all extraction methods fail, the system logs:
- Raw HTML (`failed_extractions/{site}/{id}_page.html`)
- Metadata (`failed_extractions/{site}/{id}_metadata.json`)
- What we attempted to extract
- Specific reason for failure

Use these logs to iteratively improve `sites_config.yaml`.

## 🎯 Performance Tuning

### Concurrent Extraction
```bash
# Faster but heavier on memory/CPU
python main.py harvest --max-concurrent 20

# Slower but lighter
python main.py harvest --max-concurrent 2
```

### Batch Size
```bash
# Larger batches = fewer saves to disk, faster throughput
python main.py harvest --batch-size 100

# Smaller batches = more frequent saves, checkpoint more often
python main.py harvest --batch-size 10
```

### Scout Pages Per Section
```bash
# Deep discovery = more URLs found
python main.py scout --max-pages 20

# Quick discovery = fewer URLs
python main.py scout --max-pages 2
```

##  Testing & Debugging

### Enable Debug Logging
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Test Single URL Extraction
```python
from engine.extraction_logic import ExtractionEngine
import yaml

with open('sites_config.yaml') as f:
    config = yaml.safe_load(f)

engine = ExtractionEngine(config)
result = engine.extract(html, url='http://example.com', site_name='the-star')
print(result.to_dict())
```

### Inspect Failed Extractions
```bash
ls data/failed_extractions/the-star/
cat data/failed_extractions/the-star/abc123_metadata.json
```

##  Customization

### Adding Custom Extractors
Subclass `ExtractionEngine` and override tier methods:

```python
class MyExtractor(ExtractionEngine):
    def _tier3_heuristic_analysis(self, soup, result, site_name):
        # Custom heuristics
        return result
```

### Custom Date Formats
Add to `sites_config.yaml`:

```yaml
sites:
  my-site:
    date_patterns:
      - "%custom %date %format"
```

### Custom Boilerplate Filtering
```yaml
sites:
  my-site:
    boilerplate_phrases:
      - "Custom phrase to remove"
      - "Another phrase"
```

##  Ethical Guidelines

- Always check site's `robots.txt` before scraping
- Respect `crawl-delay` and `request-rate` directives
- Don't overload servers (use appropriate rate limits)
- Check site's Terms of Service
- Consider reaching out to site owners for permission
- Use scraped data responsibly

##  Troubleshooting

### Site Returns 403 Forbidden
- Update User-Agent in config
- Rotate proxies more frequently
- Reduce request rate
- Check if site requires cookies/JavaScript

### Extraction Confidence Low
- Update CSS selectors in config
- Add fallback selectors
- Review failed extraction logs
- Check if site uses JavaScript rendering

### Memory Usage High
- Reduce max concurrency
- Smaller batch sizes
- Clear `data/failed_extractions` periodically

##  Advanced Topics

### URL Deduplication
System uses URL hash to prevent re-scraping:
```python
seen_urls = set(article['url'] for article in self.articles)
```

### Resumable Crawling
Scout and Harvester persist state:
- `data/url_queue.json` - resumable discovery state
- `data/articles.json` - already extracted articles
- Can stop and resume without losing progress

### Multi-Site Coordination
Scout and Harvester can be run for specific sites:
```bash
python main.py full --site the-star
python main.py full --site the-standard
```

##  Reference Implementation

Configuration for The Star and The Standard already included in `sites_config.yaml`.

##  Contributing

To improve scrapers:
1. Inspect failed extractions in `data/failed_extractions/`
2. Update CSS selectors in `sites_config.yaml`
3. Test with: `python main.py full --site site-name`
4. Commit improved config

##  License

This project is provided as-is for educational purposes.

---

**Built with  for robust, maintainable web scraping**
