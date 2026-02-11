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
