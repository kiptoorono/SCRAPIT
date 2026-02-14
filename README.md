# SCRAP!T - Universal News Scraper

![SCRAP!T Logo](src/Scrapit.png)

A production-grade, configuration-driven news scraper for any news website. No hardcoded site logic—all configuration lives in `sites_config.yaml`.

## Features

- **Configuration-Driven**: All site logic in YAML, no code changes
- **4-Tier Extraction**: CSS selectors → metadata → heuristics → failure logging
- **Anti-Detection**: Browser fingerprints, TLS mimicry, sticky sessions, adaptive throttling
- **Proxy Support**: Health monitoring, automatic cooldowns, rate limiting
- **Resumable**: Persistent state—stop and resume without data loss
- **Data Quality**: Date normalization, content cleaning, author standardization

## Quick Start

**Requirements**: Python 3.8+

```bash
# 1. Install
pip install -r requirements.txt

# 2. Test Scout (URL discovery)
python main.py scout --site the-star --max-pages 2

# 3. Test Harvest (extraction)
python main.py harvest --batch-size 5

# 4. Check results
cat data/articles.json
```

Full walkthrough: [QUICKSTART.md](QUICKSTART.md)

## Documentation

| Guide | Purpose |
|-------|---------|
| [QUICKSTART.md](QUICKSTART.md) | 5-minute setup, commands, monitoring, troubleshooting |
| [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) | Adding new sites, CSS selectors, testing |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, how components work, performance tuning |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Complete deliverables and capabilities |

## Basic Commands

```bash
# Discover URLs
python main.py scout --site the-star --max-pages 5

# Extract articles
python main.py harvest --max-concurrent 10

# Full pipeline (scout + harvest)
python main.py full --site the-star --max-pages 3
```

## Output

Articles saved to `data/articles.json`:

```json
{
  "url": "https://example.com/article",
  "title": "Article headline",
  "content": "Full article text...",
  "author": "Author Name",
  "published_date": "2025-02-11 14:30:00",
  "extraction_method": "tier1",
  "confidence_scores": {
    "title": 0.98,
    "content": 0.95
  }
}
```

Full schema: [QUICKSTART.md](QUICKSTART.md#output-format)

## Project Structure

```
engine/              # Extraction logic (4-tier system)
utils/               # Proxy management, date parsing, content cleaning
data/                # Generated files (articles, queue, failures)
main.py              # CLI entry point
sites_config.yaml    # All site configurations
proxies.json         # Proxy credentials (optional)
requirements.txt     # Python dependencies
```

## Ethical Usage

Before scraping any site:
- Check `robots.txt` and respect crawl-delay
- Review Terms of Service
- Use appropriate rate limits
- Contact site owners for permission
- See [QUICKSTART.md](QUICKSTART.md#ethical--legal-guidelines) for full guidelines

## Contributing

To improve extraction for a site:

1. Run: `python main.py full --site site-name`
2. Check: `data/failed_extractions/site-name/`
3. Update CSS selectors in `sites_config.yaml`
4. Re-run and verify improvements

See [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md#contributing) for detailed steps.

## License

Educational purposes only.

---

**Built for robust, maintainable web scraping**
