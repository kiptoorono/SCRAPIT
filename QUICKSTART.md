# SCRAP!T Quick Start Guide

## 5-Minute Setup

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

If you get errors with curl_cffi, it's optional:
```bash
# Try without curl_cffi (falls back to aiohttp)
pip install beautifulsoup4 pyyaml aiohttp
```

### Step 2: Verify Structure
```bash
# Check all files are in place
ls -la
# Should see: 
# - main.py
# - sites_config.yaml
# - proxies.json
# - requirements.txt
# - /engine, /utils, /data folders
```

### Step 3: Test Discovery (Scout)

Discover article URLs from The Star:
```bash
python main.py scout --site the-star --max-pages 2
```

Check results:
```bash
# View discovered URLs
head -20 data/url_queue.json

# Should see URLs like:
# "url": "https://www.the-star.co.ke/article/...",
# "site": "the-star",
# "status": "new"
```

### Step 4: Test Extraction (Harvester)

Extract articles from discovered URLs:
```bash
python main.py harvest --site the-star --batch-size 5 --max-concurrent 3
```

Check results:
```bash
# View extracted articles
head -100 data/articles.json

# Should see complete articles with:
# - title
# - content
# - author
# - published_date
# - extraction_method (tier1/tier2/tier3)
# - confidence_scores
```

### Step 5: Run Full Pipeline

One command to discover + extract:
```bash
python main.py full --site the-standard --max-pages 3
```

## Command Reference

### Scout (Discovery)
```bash
# All sites, default pages
python main.py scout

# Specific site, custom depth
python main.py scout --site the-star --max-pages 10

# With debug logging
python main.py scout --site the-star 2>&1 | tee scout.log
```

### Harvest (Extraction)
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
python main.py full

python main.py full --site the-star

python main.py full --site the-standard --max-pages 5 --max-concurrent 10
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
print(scout.get_queue_stats())

# Output:
# {
#   'total_urls': 450,
#   'by_status': {'new': 200, 'in_progress': 50, 'completed': 200},
#   'by_site': {'the-star': 300, 'the-standard': 150},
#   'by_section': {'politics': 100, 'sports': 80, ...}
# }
```

### Extract Statistics
```python
from engine.harvester import Harvester

harvester = Harvester(config, scout)
stats = harvester.get_stats()
print(stats)

# Shows:
# {
#   'processed': 150,
#   'successful': 142,
#   'failed': 8,
#   'total_articles': 1200
# }
```

## Troubleshooting

### Issue: 403 Forbidden

The site is blocking you. Options:

1. **Slow down** (add delays between requests):
```yaml
# In sites_config.yaml
rate_limit:
  requests_per_minute: 10  # Reduced from 30
```

2. **Use proxies** (add to proxies.json):
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

3. **Rotate user-agents** (already happening automatically)

### Issue: Extraction Confidence Low

Selectors might be wrong. Check logs:

```bash
# Check failed extractions
ls -l data/failed_extractions/the-star/

# View failure details
cat data/failed_extractions/the-star/abc123_metadata.json

# Examine the HTML
cat data/failed_extractions/the-star/abc123_page.html | grep -o '<h1[^>]*>.*</h1>'
```

Then update `sites_config.yaml` with correct selectors.

### Issue: Memory Usage High

Too many concurrent tasks. Reduce concurrency:

```bash
python main.py harvest --max-concurrent 2
```

### Issue: Process interrupted, how to resume?

All state is saved:
- Previously discovered URLs in `data/url_queue.json`
- Extracted articles in `data/articles.json`
- Just run again with same commands

System will skip already-processed URLs.

## Performance Tuning

### For Speed (maximum throughput)
```bash
python main.py full \
  --max-pages 20 \
  --max-concurrent 15 \
  --batch-size 100
```

**Trade-offs**: Higher CPU/memory, may trigger rate limits

### For Stealth (avoid detection)
```bash
python main.py full \
  --max-pages 2 \
  --max-concurrent 2 \
  --batch-size 5
```

**Trade-offs**: Much slower, but less likely to be blocked

### Balanced (recommended)
```bash
python main.py full \
  --max-pages 5 \
  --max-concurrent 5 \
  --batch-size 20
```

## Next Steps

1. **Check Output Quality**
   - Review extracted articles in `data/articles.json`
   - Verify fields are populated correctly
   - Check confidence scores

2. **Add More Sites**
   - Edit `sites_config.yaml`
   - Follow [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md)
   - Test with `python main.py scout --site new-site`

3. **Production Deployment**
   - Move to production server
   - Set up proxies
   - Configure concurrency limits
   - Run in background with nohup/screen/supervisor
   - Monitor logs

4. **Continuous Updates**
   - Sites redesign frequently
   - Monitor `failed_extractions` folder
   - Update selectors when failures appear
   - Version control `sites_config.yaml`

## File Reference

| File | Purpose |
|------|---------|
| `main.py` | Entry point, CLI commands |
| `sites_config.yaml` | All site-specific configuration |
| `engine/scout.py` | URL discovery module |
| `engine/harvester.py` | Article extraction module |
| `engine/extraction_logic.py` | 4-tier extraction system |
| `utils/proxy_manager.py` | Proxy pool & sessions |
| `utils/date_normalizer.py` | Date parsing & normalization |
| `utils/cleaner.py` | Content cleaning pipeline |
| `data/url_queue.json` | Discovered URLs (generated) |
| `data/articles.json` | Extracted articles (generated) |
| `data/failed_extractions/` | Failed extraction logs |

## Output Format

Extract articles are saved as JSON with full metadata:

```json
{
  "url": "https://www.the-star.co.ke/article/2025/02/11/news",
  "title": "Article Headline",
  "content": "Full article text here...",
  "author": "Reporter Name",
  "published_date": "2025-02-11 14:30:00",
  "modified_date": null,
  "category": "Politics",
  "tags": ["corruption", "parliament"],
  "language": "en",
  "image_url": "https://..../image.jpg",
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

## Import in Python

```python
import json

# Load articles
with open('data/articles.json') as f:
    articles = json.load(f)

# Search
political_articles = [
    a for a in articles 
    if a['category'] == 'Politics'
]

# Analyze
high_confidence = [
    a for a in articles
    if a['extraction_confidence'] > 0.90
]

print(f"Total: {len(articles)}")
print(f"Political: {len(political_articles)}")
print(f"High confidence: {len(high_confidence)}")
```

## Getting Help

1. **Check logs**: `tail -f scraper.log`
2. **Review failed extractions**: `ls data/failed_extractions/`
3. **Read docs**:
   - [README.md](README.md) - Overview
   - [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) - Adding sites
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Technical details
4. **Debug extraction**: Review extraction_logic.py tiers
5. **Test selectors**: Use browser DevTools console

---

**You're ready!** Start with:
```bash
python main.py full --site the-star --max-pages 2
```

Then check `data/articles.json` for results. 🚀

