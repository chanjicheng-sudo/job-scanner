import os

# Telegram settings
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# File paths
COMPANIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "companies.json")
SEEN_JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_jobs.json")

# Scraping
REQUEST_TIMEOUT = 20
DELAY_BETWEEN_COMPANIES = 1.0
MAX_DESCRIPTION_LENGTH = 200

# ─── Marketing keywords (matched against title + description) ────────────────
MARKETING_KEYWORDS = [
    # Core marketing
    "marketing", "growth", "brand", "branding",
    # Content & creative
    "content", "copywriter", "copywriting", "creative strategy",
    "editorial", "storytelling", "content strategy",
    # Social & community
    "social media", "community", "community manager",
    "organic social", "social strategy",
    # Paid / performance
    "paid social", "paid media", "paid search",
    "ppc", "sem", "performance marketing",
    "media buyer", "media buying", "media planner", "media planning",
    "programmatic", "display advertising",
    # SEO
    "seo",
    # CRM / email / lifecycle
    "crm", "email marketing", "lifecycle",
    "retention", "engagement", "loyalty",
    "marketing automation", "customer engagement",
    # Acquisition / demand gen
    "acquisition", "demand gen", "demand generation",
    "lead gen", "lead generation", "funnel",
    # Digital marketing
    "digital marketing",
    # Campaign
    "campaign", "campaign manager", "campaign management",
    # PR / comms
    "pr ", "public relations", "communications", "comms",
    "press", "media relations",
    # Partnerships / affiliate / influencer
    "partnerships", "affiliate", "influencer",
    "brand ambassador", "sponsorship",
    # Analytics / insights (marketing-specific)
    "marketing analyst", "marketing analytics",
    "marketing insight", "marketing data",
    "marketing operations", "marketing ops",
    # Product marketing
    "product marketing", "go-to-market", "gtm",
    # Events
    "event marketing", "events manager", "experiential",
    # Employer / internal
    "employer brand",
    # Conversion / optimisation
    "conversion", "cro", "optimisation", "optimization",
    # Advertising
    "advertising",
    # Ecommerce
    "ecommerce marketing", "e-commerce marketing",
    # Video / visual
    "video content", "video producer", "video production",
    "creative producer", "creative director",
]

# ─── Department/category keywords (matched against ATS department field) ─────
MARKETING_DEPARTMENTS = [
    "marketing", "growth", "brand", "content",
    "communications", "comms", "creative",
    "demand gen", "digital", "acquisition",
    "partnerships", "pr", "public relations",
    "social", "media", "campaign",
    "advertising", "performance",
]

# ─── Seniority exclusions (skip roles requiring too much experience) ──────────
EXCLUDE_KEYWORDS = [
    "director", "head of", "vp ", "vp,", "vice president",
    "chief", "cmo", "cto", "cfo", "coo",
    "principal", "staff ",
    "senior director", "group director",
    "managing director",
]

# Location keywords
LONDON_KEYWORDS = [
    "london", "uk", "united kingdom", "remote", "hybrid",
    "england", "greater london", "emea",
]

TELEGRAM_MAX_LENGTH = 4000
