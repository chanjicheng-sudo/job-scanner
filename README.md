# Marketing Job Scanner Bot

Telegram bot that scrapes career pages from 75+ UK companies and sends marketing-related job listings in London.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# Run the bot
python bot.py
```

## Commands

- `/scan` — Find **new** marketing jobs (only unseen listings)
- `/all` — Show **all** current marketing jobs
- `/status` — Bot status and stats

## Configuration

Edit `companies.json` to add/remove companies. Each entry needs:

- **`name`**: Display name
- **`type`**: One of `greenhouse`, `lever`, `ashby`, `workable`, `careers_page`
- **`slug`** (for API-based): Company identifier used in the API URL
- **`url`** (for `careers_page`): Direct URL to the careers page

### Fixing broken company slugs

Some Greenhouse/Lever slugs may need updating. To find the right slug:

1. Go to the company's careers page
2. Look at the URL — e.g. `https://boards.greenhouse.io/companyname` → slug is `companyname`
3. Or check the page source for API calls to greenhouse/lever/workable
4. Update the slug in `companies.json`

## How it works

- Uses public ATS APIs (Greenhouse, Lever, Ashby, Workable) — no browser automation needed
- Falls back to HTML scraping for companies with custom career pages
- Filters jobs by marketing keywords + London location
- Tracks seen job URLs in `seen_jobs.json` to avoid duplicates
