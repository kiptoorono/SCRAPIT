# SCRAP!T - Architecture Documentation

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Layer                       │
│              (sites_config.yaml - declarative)              │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌───────────────────────────────────────┐
        │        Scout Module (Discovery)       │
        │  - Navigates site structure           │
        │  - Extracts article URLs              │
        │  - Populates URL queue                │
        │  - Respects pagination config         │
        └───────────────────────────────────────┘
                              ↓
        ┌───────────────────────────────────────┐
        │     URL Queue (Persistent State)      │
        │      (data/url_queue.json)            │
        └───────────────────────────────────────┘
                              ↓
        ┌───────────────────────────────────────┐
        │      Harvester Module (Extraction)    │
        │  - Fetches URLs from queue            │
        │  - Async concurrent processing        │
        │  - Manages proxy sessions             │
        │  - Applies extraction pipeline        │
        └───────────────────────────────────────┘
                              ↓
        ┌───────────────────────────────────────┐
        │     Extraction Engine (4-Tier)        │
        │  1. Config selectors (Precision)      │
        │  2. Metadata (JSON-LD, OG)            │
        │  3. Heuristics (Text density)         │
        │  4. Failure logging (Manual review)   │
        └───────────────────────────────────────┘
                              ↓
        ┌───────────────────────────────────────┐
        │   Standardization Pipeline            │
        │  - Date normalization (ISO 8601)     │
        │  - Content cleaning                   │
        │  - Author standardization             │
        │  - Category mapping                   │
        │  - Output validation                  │
        └───────────────────────────────────────┘
                              ↓
        ┌───────────────────────────────────────┐
        │      Output (data/articles.json)      │
        │   Normalized, validated articles      │
        └───────────────────────────────────────┘
```

## Detailed Component Architecture

### 1. Configuration Layer (`sites_config.yaml`)

**Purpose**: Single source of truth for all site-specific knowledge

**Structure**:
- Global settings (user-agents, timeouts, pools)
- Per-site configuration:
  - Entry points for navigation
  - CSS selectors (primary + fallbacks)
  - Pagination strategies
  - Rate limits
  - Date formats
  - Boilerplate patterns

**Key Design**:
- **No hardcoding** in Python code
- **Hierarchical** (global defaults + site overrides)
- **Granular** (can override per section)
- **Maintainable** (non-technical users can edit)

Example impact:
```yaml
# Change rate limit without restarting
rate_limit:
  requests_per_minute: 60  # Changed from 30
  
# Add new selector without touching code
selectors:
  content:
    fallback:
      - "div.new-content-class"  # New site design
```

### 2. Scout Module (`engine/scout.py`)

**Purpose**: Fast discovery of article URLs

**Responsibilities**:
1. Navigate site using entry points from config
2. Extract links from listing pages
3. Filter to identify article URLs (vs navigation/ads)
4. Handle pagination (URL params, Load More, etc.)
5. Persist discovered URLs to JSON queue

**Design Patterns**:
- **Async I/O**: Concurrent page fetching
- **Stateless Processing**: No article content extracted
- **Queue Persistence**: Resumable discovery
- **Priority Scoring**: Breaking news before archives

**URL Queue Schema**:
```python
{
    'url': 'https://site.com/article/123',
    'site': 'the-star',
    'section': 'politics',
    'discovered_at': '2025-02-11T14:30:00',
    'status': 'new',  # new → in_progress → completed/failed
    'priority': 0.85,
    'retry_count': 0,
    'last_error': None
}
```

**Key Features**:
- Intelligent link filtering (articles only)
- Pagination support (3 types)
- URL deduplication
- Section-based organization

### 3. Harvester Module (`engine/harvester.py`)

**Purpose**: Deep extraction of article content with concurrency

**Responsibilities**:
1. Pull URLs from Scout's queue
2. Fetch HTML using proxied sessions
3. Apply extraction pipeline (4-tier)
4. Normalize extracted data
5. Validate and store results
6. Provide metrics and progress

**Concurrency Architecture**:
```python
async def _process_batch(self, urls):
    semaphore = asyncio.Semaphore(self.max_concurrent)
    tasks = [
        self._harvest_single_with_limit(semaphore, url)
        for url in urls
    ]
    await asyncio.gather(*tasks)
```

- **Semaphore**: Limits concurrent requests
- **Async/await**: Non-blocking I/O
- **Batch processing**: Group updates for efficiency
- **Error isolation**: One URL's error doesn't block others

**Session Management**:
```python
session = proxy_manager.create_session()
# Maintains throughout article extraction:
# - Same IP (proxy)
# - Same fingerprint (User-Agent, headers)
# - Session ID for tracking
# - Cookies accumulated
# - Referrer chain

# Session rotates after:
# - N articles (default 30)
# - Time limit (default 30min)
# - Server rejection (403, etc.)
```

### 4. Extraction Engine (`engine/extraction_logic.py`)

**Purpose**: 4-tier fallback extraction system

#### Tier 1: Config Selectors (Precision)
```python
def _tier1_config_selectors(soup, result, site_name):
    selectors = self.config['sites'][site_name]['selectors']
    
    # Try primary selector
    element = soup.select_one(selectors['title']['primary'])
    if element:
        result.title = element.get_text(strip=True)
        confidence = 1.0
        return result
    
    # Try fallback selectors
    for fallback_selector in selectors['title']['fallback']:
        element = soup.select_one(fallback_selector)
        if element:
            result.title = element.get_text(strip=True)
            confidence = 0.85 - (fallback_index * 0.15)
            return result
```

**Characteristics**:
- Fastest execution
- High accuracy (tested patterns)
- Highest confidence scores
- Site-specific knowledge

#### Tier 2: Metadata Extraction (Semantic)
```python
def _tier2_metadata_extraction(soup, result, site_name):
    # Try JSON-LD
    ld_data = self._extract_json_ld(soup)  # NewsArticle schema
    if ld_data:
        result.title = ld_data['headline']
        result.content = ld_data['articleBody']
        confidence = 0.85
        return result
    
    # Try OpenGraph
    og_data = self._extract_og_tags(soup)  # og:title, og:description
    if og_data['title']:
        result.title = og_data['title']
        confidence = 0.75
        return result
    
    # Try Twitter Card
    twitter_data = self._extract_twitter_card(soup)  # twitter:title
    if twitter_data['title']:
        result.title = twitter_data['title']
        confidence = 0.70
        return result
```

**Advantages**:
- Standards-based (won't change if site redesigns)
- Site-agnostic (works for any site)
- Usually high quality (SEO optimized)

**Data Sources**:
- JSON-LD: `<script type="application/ld+json">`
- OpenGraph: `<meta property="og:*">`
- Twitter Card: `<meta name="twitter:*">`
- Microdata: `<span itemprop="*">`

#### Tier 3: Heuristic Analysis (Smart Guessing)
```python
def _tier3_heuristic_analysis(soup, result, site_name):
    # Title heuristics
    # - Largest heading (usually H1)
    # - Longest bold text
    # - Text in <title> tag (minus site name)
    
    # Content heuristics - Text Density Algorithm
    for container in soup.find_all(['article', 'div']):
        # Calculate score based on:
        # - Paragraph count (more paragraphs = article)
        # - Word count (more words = content)
        # - Link density (fewer links = content, more = nav)
        # - Average paragraph length (proper prose)
        
        score = (
            paragraph_count * 10 +
            (word_count >= 500) * 50 +
            (link_density <= 0.30) * 30 +
            (avg_para_length >= 50) * 20
        )
        
        candidates.add((score, container))
    
    best_container = max(candidates)
    result.content = extract_paragraphs(best_container)
    confidence = 0.55  # Lower confidence for heuristics
    return result
```

**Heuristic Methods**:
- Title: H1 tags, largest text, page title
- Author: "By" patterns, author element classes
- Date: Date patterns, time elements, relative dates
- Content: Text density, paragraph density, link density

**Why It Works**:
- Articles follow conventions
- Text content > navigation content  
- Dense paragraphs = article body
- Sparse content = sidebars/ads

#### Tier 4: Human Loop (Failure Logging)
```python
def _tier4_log_failure(html, url, site_name, result):
    # Generate unique ID for this extraction
    failure_id = hashlib.md5(url.encode()).hexdigest()[:8]
    
    # Save HTML for inspection
    with open(f'failed/{site_name}/{failure_id}_page.html', 'w') as f:
        f.write(html)
    
    # Save metadata
    metadata = {
        'url': url,
        'site': site_name,
        'timestamp': datetime.utcnow().isoformat(),
        'what_we_found': {
            'title': result.title,
            'content_length': len(result.content),
            'author': result.author,
        },
        'failure_reasons': [
            'Tier 1: No matching selectors',
            'Tier 2: No JSON-LD or OG tags',
            'Tier 3: Content density too low',
        ]
    }
    
    with open(f'failed/{site_name}/{failure_id}_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
```

**Purpose**: Enable learning from failures
- Inspectors can review failed HTML
- Identifies why extraction failed
- Basis for config improvements

**Workflow**:
1. Failed extraction logged
2. Engineer reviews HTML + metadata  
3. Identifies missing patterns
4. Updates CSS selectors in config
5. Re-runs scraper (better results)

### 5. Proxy & Session Management (`utils/proxy_manager.py`)

**Purpose**: Manage proxy pool and maintain behavioral realism

#### Proxy Credentials & Format
```python
# Input (from proxies.json)
{
    "address": "31.59.20.176",
    "port": "6754",
    "username": "nubyhsza",
    "password": "secret123"
}

# Converted to URL
ProxyCredentials.to_http_proxy()
# → "http://nubyhsza:secret123@31.59.20.176:6754"

# Used in requests
async with aiohttp.ClientSession(proxy=proxy_url) as session:
    async with session.get(url) as resp:
        ...
```

#### Sticky Sessions
```python
class Session:
    session_id = "session_1707591000000"
    proxy = ProxyCredentials(...)        # Same IP
    fingerprint = BrowserFingerprint(...)  # Same User-Agent
    created_at = datetime(...)
    requests_made = 0
    last_used = datetime(...)
    cookies = {}                        # Accumulated cookies
    referrer_chain = []                 # Navigation history
```

**Session Lifecycle**:
1. Scout needs to fetch Google homepage
2. Create session (IP + fingerprint)
3. Fetch with session → Sets cookies
4. Fetch related article with same session
5. Cookies sent automatically
6. Session rotation when:
   - Requests >= 30
   - Age >= 30 minutes
   - Server blocks (403)

**Browser Fingerprints**:
```python
BrowserFingerprint(
    browser='Chrome',
    user_agent='Mozilla/5.0 (...) Chrome/120.0...',
    headers={
        'Accept': 'text/html,...',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-site',
    }
)
```

Multiple realistic fingerprints:
- Chrome on Windows 10
- Chrome on macOS
- Firefox on Windows 10
- Firefox on Linux

#### Adaptive Throttling
```python
def calculate_delay(domain, site_config, last_response_time):
    # Base delay from config
    requests_per_minute = site_config['rate_limit']['requests_per_minute']
    base_delay = 60.0 / requests_per_minute  # e.g., 30 req/min → 2s delay
    
    # Adapt based on response time
    if last_response_time > 2.0:  # Server slow
        delay = base_delay * 2.0  # Double delay
    elif last_response_time > 0.5:  # Normal
        delay = base_delay
    else:  # Fast
        delay = base_delay * 0.8
    
    # Add randomness (makes it look human)
    variance = delay * 0.1
    return delay + random.uniform(-variance, variance)
```

**Throttling Examples**:
- Fast response (200ms) + 30 req/min config
  - Base delay: 2s
  - Actual: 1.6s (faster)

- Slow response (3s) + 30 req/min config
  - Base delay: 2s
  - Actual: 4s (slower)

- Error response (429 Rate Limit)
  - Immediately back off 2-5x slower

#### Proxy Health Monitoring
```python
proxy_health = {
    'http://user:pass@ip:port': {
        'success_count': 150,
        'failure_count': 5,
        'last_used': '2025-02-11T14:30:00',
        'cooldown_until': None
    }
}

# Selection algorithm
success_rate = 150 / 155 = 0.968
weight = max(0.1, success_rate) = 0.968
# Higher success rate = more likely to be selected

# After 403 Forbidden (blocked):
cooldown_until = now + 1 hour
# Proxy won't be selected for 1 hour
```

### 6. Data Normalization Pipeline

#### Date Normalization (`utils/date_normalizer.py`)
```python
# Input examples
"27 July 2025 - 20:13"
"February 11, 2025"
"2025-02-11T14:30:00Z"
"2 hours ago"
"1707591000"  # Unix timestamp

# Output (all normalized to)
"2025-02-11 20:13:00"  # ISO 8601 (YYYY-MM-DD HH:MM:SS)

# With confidence scores
("2025-02-11 20:13:00", 0.92)  # High confidence (specific time)
("2025-02-11 12:00:00", 0.40)  # Low confidence (relative date)
(None, 0.0)                     # Parsing failed
```

**Parsing Strategy**:
1. Try ISO 8601
2. Try Unix timestamp
3. Try HTML5 datetime
4. Try explicit formats (with month names, patterns)
5. Try relative dates ("2 hours ago")
6. Try heuristic patterns

**Validation**:
- Not in future (allow 1 day tolerance)
- Not too old (min year 2000)
- Not ancient (max 10000 days old)

#### Content Cleaning (`utils/cleaner.py`)
```python
def clean_content(raw_html):
    # 1. Decode HTML entities
    "&mdash;" → "—"
    "&nbsp;" → " "
    "&#39;" → "'"
    
    # 2. Remove HTML tags
    "<p>text</p>" → "text"
    
    # 3. Remove boilerplate
    "Subscribe to our newsletter" ✗
    "Share on Twitter" ✗
    "Related articles" ✗
    
    # 4. Normalize whitespace
    "text  with   spaces" → "text with spaces"
    "line1\n\n\nline2" → "line1\n\nline2"
    
    # 5. Remove extra newlines
    Collapse multiple blank lines to single newline
    
    # 6. Normalize unicode
    NFC normalization (composed forms)
    
    # Result
    "Cleaned, normalized article text"
```

**Boilerplate Detection**:
- Known phrase matching
- Structural patterns (footer text)
- Link density analysis
- Repeated content detection

#### Author Standardization
```python
# Input variations
"By John Smith"
"Written by Dr. John A. Smith, Jr."
"John Smith | Staff Writer"
"Reuters"

# Normalization
1. Remove "By", "Written by", titles (Dr.), suffixes (Jr.)
2. Handle multiple authors (split on "and", "&", commas)
3. Distinguish person vs organization
4. Apply canonical form: "FirstName LastName"

# Output
"John Smith"  # Multiple examples normalize to same name
```

#### Output Validation
```python
required_fields = ['url', 'title', 'content', 'scraped_at']
optional_fields = ['author', 'published_date', 'category', ...]

for article in articles:
    errors = []
    
    if not article['url'].startswith('http'):
        errors.append("Invalid URL")
    
    if len(article['title']) < 5:
        errors.append("Title too short")
    
    if len(article['content']) < 100:
        errors.append("Content too short")
    
    if errors:
        log_validation_error(article, errors)
        skip_article()
    else:
        save_article()
```

## Data Flow Example

```
DISCOVER PHASE:
1. Scout starts at "https://the-star.co.ke/"
2. Fetches homepage
3. Finds links to:
   - "/counties" → adds to queue (priority 0.8)
   - "/article/story-1" → adds to queue (priority 0.9)
   - "/article/story-2" → adds to queue (priority 0.9)
4. Follows pagination → finds 100+ URLs
5. Saves queue to data/url_queue.json

EXTRACTION PHASE:
1. Harvester pulls 10 URLs from queue (status: new → in_progress)
2. For each URL:
   a. Create session (IP + fingerprint)
   b. Fetch HTML
   c. Parse with extraction engine:
      - Tier 1: Use CSS selectors → found title, content, author, date
      - Return with confidence scores
   d. Normalize date → "2025-02-11 14:30:00"
   e. Clean content → Remove boilerplate, HTML entities
   f. Validate → All required fields present
   g. Store to data/articles.json
   h. Mark URL as completed
3. Throttle before next request
4. Repeat for all URLs

STORAGE:
- articles.json contains:
  {
    "url": "https://...",
    "title": "Article Title",
    "content": "Full article body...",
    "author": "John Doe",
    "published_date": "2025-02-11 14:30:00",
    "category": "Politics",
    "extraction_method": "tier1",
    "confidence_scores": {
      "title": 0.98,
      "content": 0.95,
      "author": 0.85,
      "date": 0.92
    }
  }
```

## Concurrency Model

```
Main asyncio loop
├─ Scout.discover_urls()
│  ├─ For each section:
│  │  ├─ aiohttp fetch page 1
│  │  ├─ aiohttp fetch page 2
│  │  ├─ aiohttp fetch page 3
│  │  └─ sleep 1 second
│  └─ Save queue
│
└─ Harvester.harvest()
   ├─ Get 20 URLs from queue
   ├─ Create 5 concurrent tasks (semaphore):
   │  ├─ Task 1: Harvest URL with proxy session
   │  ├─ Task 2: Harvest URL with proxy session
   │  ├─ Task 3: Harvest URL with proxy session
   │  ├─ Task 4: Harvest URL with proxy session
   │  └─ Task 5: Harvest URL with proxy session
   ├─ await all tasks
   ├─ Save articles
   └─ Repeat until queue empty
```

**Benefits**:
- Network I/O doesn't block
- CPU works on parsing while waiting for network
- Multiple requests in flight simultaneously
- Configurable concurrency (2-40+)

## Error Handling

```
Request Error
├─ Connection timeout → retry, backoff
├─ 403 Forbidden → cooldown proxy, mark failed
├─ 429 Rate Limited → increase delay 5x, cooldown
├─ 500 Server Error → retry with backoff
└─ Other HTTP → log and continue

Extraction Error
├─ All tiers fail → Tier 4: log for manual review
├─ Validation fails → Log error, skip article
└─ Storage fails → Alert, retry later

Recovery
├─ Failed URLs queued for retry
├─ Proxies in cooldown auto-recover
├─ Process can resume from saved queue state
└─ No data loss (persistent storage)
```

## Performance Considerations

### Bottleneck Analysis

```python
# Network-bound (most common)
- Scout: Limited by site response time + rate limit
- Harvester: Limited by I/O, not CPU
- Solution: Increase max_concurrent

# CPU-bound (html parsing)
- With 10+ concurrent requests and large articles
- BeautifulSoup CPU parsing slows overall
- Solution: Use lxml backend, profile code

# Memory-bound (rare)
- Storing entire HTML in memory
- 1000 concurrent requests × 1MB articles = 1GB
- Solution: Use streaming, reduce concurrency
```

### Optimization Strategies

1. **Scout Phase**:
   - Use async I/O (already doing)
   - Batch database inserts
   - Disk I/O is bottleneck

2. **Harvester Phase**:
   - Tune max_concurrent (test: 5-20)
   - Batch size affects save frequency (larger = faster)
   - Proxy quality matters (fast proxies = fewer timeouts)

3. **Extraction Phase**:
   - Tier 1 fastest (most should succeed)
   - Tier 2 requires no I/O (fast)
   - Tier 3 requires DOM analysis (moderate)
   - Tier 4 writes to disk (slowest)

## Future Enhancements

1. **JavaScript Rendering**:
   - Integrate Playwright for JS-heavy sites
   - Headless browser costs (CPU/memory)

2. **Distributed Processing**:
   - Multiple Scout processes
   - Multiple Harvester processes
   - Shared Queue (Redis)
   - Distributed storage

3. **Machine Learning**:
   - Learn selector confidence from success rates
   - Auto-improve failing selectors
   - Predict article quality

4. **Real-time Monitoring**:
   - WebSocket dashboard
   - Live metrics
   - Alert system

5. **API Export**:
   - GraphQL endpoint
   - REST pagination
   - Full-text search (Elasticsearch)

---

This architecture prioritizes:
- **Maintainability**: Config-driven, clear separation of concerns
- **Resilience**: Multiple fallback tiers, error recovery
- **Performance**: Async I/O, concurrent processing
- **Scalability**: Decoupled components, persistent state
- **Extensibility**: Easy to add new sites, customize logic

