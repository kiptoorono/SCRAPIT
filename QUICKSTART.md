# SCRAP!T Quick Start Guide

## 5-Minute Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Test Scout (URL Discovery)

Discover article URLs from The Star:

```bash
python main.py scout --site the-star --max-pages 2
```

Check results:

```bash
cat data/url_queue.json
```

Should see URLs with status "new".

### Step 3: Test Harvest (Extraction)

Extract articles from discovered URLs:

```bash
python main.py harvest --site the-star --batch-size 5
```

Check results:

```bash
cat data/articles.json
```

Should see complete articles with title, content, author, dates.

### Step 4: Full Pipeline

One command to discover and extract:

```bash
python main.py full --site the-star --max-pages 3
```

## Command Reference

### Scout (URL Discovery)

```bash
# All sites, default pages
python main.py scout

# Specific site
python main.py scout --site the-star --max-pages 10

# Save logs
python main.py scout --site the-star 2>&1 | tee scout.log
```

### Harvest (Article Extraction)

```bash
# All queued articles
python main.py harvest

# Specific site
python main.py harvest --site the-star

# Tuned for speed
python main.py harvest --max-concurrent 20 --batch-size 100

# Tuned for stability
python main.py harvest --max-concurrent 2 --batch-size 5
```

### Full Pipeline

```bash
# All sites
python main.py full

# One site
python main.py full --site the-star

# Custom parameters
python main.py full --site the-standard --max-pages 5 --max-concurrent 10
```

## Output Format

Articles saved to `data/articles.json`:

```json
{
  "url": "https://example.com/article",
  "title": "Article headline",
  "content": "Full article text...",
  "author": "Author Name",
  "published_date": "2025-02-11 14:30:00",
  "modified_date": null,
  "category": "Politics",
  "tags": ["tag1", "tag2"],
  "language": "en",
  "image_url": "https://example.com/image.jpg",
  "source_site": "the-star",
  "extraction_method": "tier1",
  "extraction_confidence": 0.96,
  "confidence_scores": {
    "title": 0.98,
    "content": 0.95,
    "author": 0.85,
    "date": 0.92
  },
  "extraction_duration_ms": 245,
  "scraped_at": "2025-02-11T14:32:00"
}
```

## Monitoring Progress

### Real-time Logs

```bash
tail -f scraper.log
```

### Queue Statistics

```python
from engine.scout import Scout
import yaml

with open('sites_config.yaml') as f:
    config = yaml.safe_load(f)

scout = Scout(config)
stats = scout.get_queue_stats()
print(stats)
```

Returns:
```
{
  'total_urls': 450,
  'by_status': {'new': 200, 'in_progress': 50, 'completed': 200},
  'by_site': {'the-star': 300, 'the-standard': 150},
  'by_section': {'politics': 100, 'sports': 80, ...}
}
```

### Extraction Statistics

```python
from engine.harvester import Harvester

harvester = Harvester(config, scout)
stats = harvester.get_stats()
print(stats)
```

Returns:
```
{
  'processed': 150,
  'successful': 142,
  'failed': 8,
  'total_articles': 1200
}
```

## Programmatic Usage

Use SCRAP!T as a library in your code:

```python
from engine.extraction_logic import ExtractionEngine
import yaml

# Load configuration
with open('sites_config.yaml') as f:
    config = yaml.safe_load(f)

# Create extractor
engine = ExtractionEngine(config)

# Extract from HTML
result = engine.extract(
    html_content,
    url='http://example.com/article',
    site_name='the-star'
)

print(result.to_dict())
```

## Performance Tuning

### For Speed (Maximum Throughput)

```bash
python main.py full \
  --max-pages 20 \
  --max-concurrent 15 \
  --batch-size 100
```

Trade-off: Higher CPU/memory, may trigger rate limits

### For Stealth (Avoid Detection)

```bash
python main.py full \
  --max-pages 2 \
  --max-concurrent 2 \
  --batch-size 5
```

Trade-off: Much slower, lower detection risk

### Balanced (Recommended)

```bash
python main.py full \
  --max-pages 5 \
  --max-concurrent 5 \
  --batch-size 20
```

## Troubleshooting

### Site Returns 403 Forbidden

Site is blocking requests. Try:

1. Reduce rate limit in `sites_config.yaml`:
   ```yaml
   rate_limit:
     requests_per_minute: 10
   ```

2. Add proxies to `proxies.json`:
   ```json
   [
     {
       "address": "proxy1.example.com",
       "port": "8080",
       "username": "user",
       "password": "pass"
     }
   ]
   ```

3. Rotate User-Agent (happens automatically)

### Extraction Confidence Low

Content not being extracted properly:

1. Check failed extractions:
   ```bash
   ls data/failed_extractions/the-star/
   cat data/failed_extractions/the-star/abc123_metadata.json
   ```

2. Examine HTML:
   ```bash
   cat data/failed_extractions/the-star/abc123_page.html | grep -o '<h1[^>]*>.*</h1>'
   ```

3. Update CSS selectors in `sites_config.yaml`

### Memory Usage High

Too many concurrent tasks. Reduce concurrency:

```bash
python main.py harvest --max-concurrent 2
```

Or reduce batch size:

```bash
python main.py harvest --batch-size 10
```

### Process Interrupted

All state is saved automatically:
- Discovered URLs in `data/url_queue.json`
- Extracted articles in `data/articles.json`

Just run again—it skips already-processed URLs.

### URLs Not Being Discovered

Scout isn't finding articles:

1. Check what was found:
   ```bash
   cat data/url_queue.json
   ```

2. Verify entry points in `sites_config.yaml` point to list pages

3. Check pagination configuration matches site structure

4. Inspect logs for rate limiting or proxy issues

### Proxies Failing

Persistent proxy failures:

1. Verify credentials in `proxies.json` are correct

2. Test manually:
   ```bash
   python test_proxies.py
   ```

3. Check IP allowlisting (some sites require it)

4. Reduce request rate to avoid triggering limits

5. Try different proxy provider

## Ethical & Legal Guidelines

Before scraping any site:

- Check `robots.txt` and respect `crawl-delay`
- Review Terms of Service
- Don't overload servers (use appropriate rate limits)
- Contact site owners for permission
- Use data responsibly and legally
- Check local laws regarding web scraping

## Import in Python

```python
import json

# Load articles
with open('data/articles.json') as f:
    articles = json.load(f)

# Filter by category
political = [a for a in articles if a['category'] == 'Politics']

# Filter by confidence
high_confidence = [a for a in articles if a['extraction_confidence'] > 0.90]

print(f"Total: {len(articles)}")
print(f"Political: {len(political)}")
print(f"High confidence: {len(high_confidence)}")
```

## File Reference

| File | Purpose |
|------|---------|
| main.py | CLI entry point |
| sites_config.yaml | Site configurations |
| engine/scout.py | URL discovery |
| engine/harvester.py | Article extraction |
| engine/extraction_logic.py | 4-tier extraction |
| utils/proxy_manager.py | Proxy management |
| utils/date_normalizer.py | Date parsing |
| utils/cleaner.py | Content cleaning |
| data/url_queue.json | Discovered URLs |
| data/articles.json | Extracted articles |
| data/failed_extractions/ | Failure logs |

## Getting Help

1. Check logs: `tail -f scraper.log`
2. Review failed extractions: `ls data/failed_extractions/`
3. Read documentation:
   - [README.md](README.md) - Overview
   - [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) - Adding sites
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Technical details
4. Test selectors with browser DevTools

---

Ready to start? Run:

```bash
python main.py full --site the-star --max-pages 2
```

Then check `data/articles.json` for results.

