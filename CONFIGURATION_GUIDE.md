# SCRAP!T - Configuration Guide

This guide will walk you through adding a new news site to the scraper.

## Step 1: Understand Site Structure

Before writing configuration, manually explore the target site:

1. **Homepage**: `https://targetsite.com/`
   - Look for article listings
   - Note URL patterns
   
2. **Article Page**: Click on an article
   - Right-click → "Inspect" to open DevTools
   - Identify CSS classes/IDs for:
     - Title
     - Article body
     - Author name
     - Publication date
     - Featured image
   
3. **Pagination**: Look for:
   - "Next page" button/link
   - "Load More Articles" button
   - Query parameters (`?page=2`, `?start=20`)

## Step 2: Extract CSS Selectors

For each article element, find the selector:

### Example: Finding Title Selector

```
1. Open article page
2. Right-click title → Inspect
3. Find the HTML tag and classes
4. Test selector: copy-paste into browser console:
   
   // Test in console:
   document.querySelector('h1.headline')
   document.querySelectorAll('h1')
```

Record all selectors.

## Step 3: Create Site Configuration

Add to `sites_config.yaml`:

```yaml
sites:
  my-site:  # Site ID (use lowercase, hyphens)
    name: "My News Site"
    domain: "mynewssite.com"
    base_url: "https://www.mynewssite.com"
    
    # Entry points for Scout to start discovery
    entry_points:
      - path: "/"
        name: "homepage"
      - path: "/news"
        name: "news_main"
      - path: "/politics"
        name: "politics"
      - path: "/sports"
        name: "sports"
    
    # CSS selectors in order of reliability
    selectors:
      title:
        primary: "h1.headline"  # Most likely selector
        fallback:
          - "h1.post-title"
          - "span.article-title"
          - "h1"  # Generic fallback
      
      content:
        primary: "div.article-body"
        fallback:
          - "article"
          - "div.story-content"
          - "div.main"
      
      author:
        primary: "span.author-name"
        fallback:
          - "a.writer"
          - "span[data-author]"
      
      date:
        primary: "time[datetime]"
        fallback:
          - "span.publish-date"
          - "span.date-published"
      
      image:
        primary: "img.featured-image"
        fallback:
          - "img[alt*='article']"
          - "picture img"
    
    # Date formats this site uses (tried in order)
    date_patterns:
      - "%B %d, %Y"      # February 11, 2025
      - "%d/%m/%Y"       # 11/02/2025
      - "%Y-%m-%d"       # 2025-02-11
    
    # Pagination configuration
    pagination:
      type: "url_param"  # or "button_load_more"
      url_param_name: "page"
      param_increment: 1
    
    # Site-specific rate limiting
    rate_limit:
      requests_per_minute: 30
      respect_robots_txt: true
      crawl_delay_override: 1.5
```

## Step 4: Test Configuration

### 4.1 Test Scout (URL Discovery)

```bash
python main.py scout --site my-site --max-pages 2
```

Check `data/url_queue.json`:
- Should contain URLs from your site
- URLs should be distinct (not duplicates)
- Most should be article pages

If URLs are wrong:
- Review `entry_points` - are the paths correct?
- Check `_is_article_url()` logic in scout.py

### 4.2 Test Harvester (Article Extraction)

```bash
python main.py harvest --site my-site --batch-size 5
```

Check `data/articles.json`:
- Should have entries with:
  - Populated title, content, author, date
  - Extraction method (hopefully "tier1")
  - High confidence scores

If extraction fails:
- Check `data/failed_extractions/my-site/` for details
- Your selectors might be wrong (test in browser console)
- Site might use JavaScript rendering (need Selenium/Playwright)

### 4.3 Verify Individual Article

Manually inspect a failed extraction:

```bash
# Find failed extraction ID
ls data/failed_extractions/my-site/

# Check metadata
cat data/failed_extractions/my-site/abc12345_metadata.json

# View HTML
cat data/failed_extractions/my-site/abc12345_page.html
```

Use browser DevTools to verify selector paths.

## Step 5: Iterative Improvement

### Common Issues & Fixes

**Issue: Titles extracted but content is empty**
- Problem: Content selector is wrong
- Fix: Test selector in browser console
- Solution: Update `selectors.content.primary`

**Issue: Articles are just "Uncategorized"**
- This is normal if category isn't detected
- Optional field - can be manually mapped later

**Issue: Dates are None or wrong format**
- Problem: Date patterns don't match this site
- Fix: Add actual date examples
- Solution: Add new pattern to `date_patterns`

**Issue: Author shows "Staff" instead of names**
- Problem: Author selector picking up generic text
- Fix: Use more specific selector
- Solution: Update author selectors

**Issue: Getting 403 Forbidden after few requests**
- Problem: Site blocking automated access
- Fix: Reduce request rate, rotate proxies
- Solution: Decrease `requests_per_minute`, add proxies

### Example: Improving Star Config

Initial config extracted title but not content:

```yaml
# BEFORE (failing)
selectors:
  content:
    primary: "div.story-body"
    fallback: ["article"]

# AFTER (working)
selectors:
  content:
    primary: "div.story-content"  # Correct class found
    fallback:
      - "div.article-body"
      - "article"
      - "div.main"  # More fallbacks for robustness
```

## Step 6: Optimization

Once basic extraction works:

### Tier 2 Setup (Metadata Fallback)

Most modern sites have JSON-LD or OpenGraph. Test:

```javascript
// In browser console:
// Check for JSON-LD
JSON.parse(document.querySelector('script[type="application/ld+json"]').innerText)

// Check for OpenGraph
document.querySelectorAll('meta[property^="og:"]')
```

If present, Tier 2 will automatically supplement Tier 1.

### Pagination Fine-Tuning

Test pagination by visiting:
- First page: `https://site.com/news`
- Second page: Follow next link or add param
- Record actual URL of page 2

Use this to verify your pagination config:

```yaml
# If URL becomes: https://site.com/news?start=20
pagination:
  type: "url_param"
  url_param_name: "start"
  param_increment: 20  # 0→20→40→60

# If there's a "Load More" button:
pagination:
  type: "button_load_more"
```

### Rate Limiting Optimization

Monitor response times:

```bash
# If site responds quickly (< 500ms):
rate_limit:
  requests_per_minute: 60  # Can go faster

# If site responds slowly (> 2s):
rate_limit:
  requests_per_minute: 15  # Go slower
```

## Step 7: Document & Commit

Add comments to config explaining anything unusual:

```yaml
sites:
  my-site:
    name: "My News Site"
    # Note: This site uses JavaScript rendering for some content.
    # Basic articles work, but breaking news might need JavaScript engine.
    # Author names sometimes in <small> tag instead of declared author element.
    
    selectors:
      # ...
```

## Troubleshooting Decision Tree

```
Scraping failing?
├─ 403 Forbidden?
│  └─ Reduce rate, add proxies
├─ Extraction confidence low?
│  ├─ Wrong selectors?
│  │  └─ Update selectors from browser console
│  ├─ Content has boilerplate?
│  │  └─ Add phrases to boilerplate_phrases
│  └─ Site uses JavaScript?
│     └─ Might need Selenium/Playwright
├─ Dates not parsing?
│  ├─ Add date format to date_patterns
│  ├─ Check date_normalizer.py for new patterns
│  └─ Date too old/future?
│     └─ Fix validation in date_normalizer.py
└─ Performance slow?
   ├─ Increase max_concurrent
   ├─ Reduce rate_limit
   └─ Optimize batch_size
```

## Custom Extractors

Extend extraction logic by subclassing:

```python
from engine.extraction_logic import ExtractionEngine

class MyExtractor(ExtractionEngine):
    def _tier1_config_selectors(self, soup, result, site_name):
        # Add custom extraction logic
        # Custom parsing for unique markup
        result.title = soup.select_one('custom.selector').text
        return result
    
    def _tier3_heuristic_analysis(self, soup, result, site_name):
        # Custom heuristics for this site
        return result
```

Then use in main.py:

```python
from my_extractors import MyExtractor
engine = MyExtractor(config)
result = engine.extract(html, url, site_name)
```

## Custom Date Formats

Add to `sites_config.yaml` for non-standard dates:

```yaml
sites:
  my-site:
    date_patterns:
      - "%B %d, %Y"           # "February 11, 2025"
      - "%d/%m/%Y %H:%M"      # "11/02/2025 14:30"
      - "%d-%m-%Y"            # "11-02-2025"
      - "%Y-%m-%d"            # "2025-02-11"
      - "%d.%m.%Y"            # "11.02.2025"
      - "%A, %B %d, %Y"       # "Friday, February 11, 2025"
      - "%d %b %Y"            # "11 Feb 2025"
```

Date patterns are tried in order. Use Python `strftime` codes.

## Boilerplate Filtering

Remove common non-article text:

```yaml
sites:
  my-site:
    boilerplate_phrases:
      - "Subscribe to our newsletter"
      - "Read more: "
      - "Follow us on Twitter"
      - "Advertisement"
      - "About the author"
      - "Related articles"
      - "Sign up for alerts"
```

These phrases are removed from extracted content.

## Rate Limiting

Configure request throttling:

```yaml
sites:
  my-site:
    rate_limit:
      requests_per_minute: 30        # Base limit
      crawl_delay_override: 2.0      # Force minimum delay between requests
      exponential_backoff: true      # Increase delay on 429/503
      max_retries: 3                 # Retry failed requests
```

The system respects `robots.txt` crawl-delay if not overridden.

## Pagination Strategies

### URL Parameters

```yaml
pagination:
  type: "url_param"
  url_param_name: "page"             # Parameter name
  param_increment: 1                 # page=1, page=2, page=3...
  start_page: 1
  max_pages: 10
```

### Load More Button

```yaml
pagination:
  type: "button_load_more"
  selector: "button.load-more"        # Button CSS selector
  clicks_per_page: 3                  # How many clicks = one "page"
  wait_time_ms: 1000                  # Wait after each click
```

### Infinite Scroll

```yaml
pagination:
  type: "infinite_scroll"
  scroll_pause_time_ms: 500          # Time between scrolls
  scroll_distance_px: 1000           # Distance to scroll each time
  max_scrolls: 20                    # Total scroll events
```

## Authentication

For sites requiring login:

```yaml
sites:
  my-site:
    auth:
      type: "session"
      login_url: "https://site.com/login"
      username: "user@example.com"
      password: "password"
      session_timeout_hours: 24
```

Not yet implemented—requires custom session handler.

## Headers Customization

Override HTTP headers per site:

```yaml
sites:
  my-site:
    headers:
      "Referer": "https://google.com"
      "X-Requested-With": "XMLHttpRequest"
      "Accept-Language": "en-US,en;q=0.9"
```

These merge with default browser headers.

## Proxy Strategy

Configure proxy usage:

```yaml
sites:
  my-site:
    proxy:
      enabled: true
      rotate_every_n_requests: 30     # Change proxy after N requests
      force_protocol: "http"          # http or socks5
      timeout_seconds: 10
      backoff_multiplier: 2.0         # Increase wait time on failure
```

## Testing Selectors

Quick testing without running full scraper:

```python
from engine.extraction_logic import ExtractionEngine
from bs4 import BeautifulSoup
import requests

# Fetch test page
resp = requests.get('https://site.com/article')
html = resp.text

# Load config
import yaml
with open('sites_config.yaml') as f:
    config = yaml.safe_load(f)

# Create extractor
engine = ExtractionEngine(config)

# Test extraction
result = engine.extract(html, url='https://site.com/article', site_name='my-site')

# View results
print(f"Title: {result.title}")
print(f"Author: {result.author}")
print(f"Date: {result.published_date}")
print(f"Content length: {len(result.content)}")
print(f"Confidence: {result.confidence_scores}")
```

## Selector Validation

Before committing config, validate with:

```python
from bs4 import BeautifulSoup
import yaml

# Load config
with open('sites_config.yaml') as f:
    config = yaml.safe_load(f)

# Load test HTML
with open('test.html') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
selectors = config['sites']['my-site']['selectors']

# Test each selector
for field, selector_config in selectors.items():
    primary = selector_config['primary']
    element = soup.select_one(primary)
    print(f"{field}: {primary} -> {'FOUND' if element else 'MISSING'}")
    
    if not element:
        for fallback in selector_config['fallback']:
            element = soup.select_one(fallback)
            if element:
                print(f"  Fallback works: {fallback}")
                break
```

## Contributing

To improve extraction for a site:

1. Run full pipeline: `python main.py full --site site-name`
2. Check failed extractions: `ls data/failed_extractions/site-name/`
3. Review failure metadata: `cat data/failed_extractions/site-name/*_metadata.json`
4. Manually inspect source HTML to find correct selectors
5. Update CSS selectors in `sites_config.yaml`
6. Re-test with: `python main.py full --site site-name`
7. When success rate is high, commit improved config

## Advanced: JavaScript-Heavy Sites

For sites that render content with JavaScript:

Current system can't handle this. Options:

1. **Use Selenium** (slower but handles JS):
   ```python
   from selenium import webdriver
   driver = webdriver.Chrome()
   driver.get(url)
   html = driver.page_source
   # Then pass html to extraction engine
   ```

2. **Use Playwright** (modern browser automation):
   ```python
   async with async_playwright() as p:
       browser = await p.chromium.launch()
       page = await browser.new_page()
       await page.goto(url)
       html = await page.content()
   ```

3. **API-based**: Check if site has JSON API
   ```
   Look at Network tab in DevTools
   See if article data comes from API endpoint
   Hit API directly instead of parsing HTML
   ```

## Next Steps

1. Configure one site completely
2. Test scout + harvest on 10-20 articles
3. Review failed extractions
4. Iterate on selectors
5. Once working well, add more sites
6. Monitor quality metrics
7. Update config as sites redesign

---

For questions about specific sites, check the `sites_config.yaml` 
for working examples (The Star, The Standard).
