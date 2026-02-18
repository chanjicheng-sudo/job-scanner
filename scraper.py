"""
Scraper module — fetches job listings from various ATS platforms and career pages.
Now checks both title/description AND department/category for marketing relevance.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from config import (
    COMPANIES_FILE,
    DELAY_BETWEEN_COMPANIES,
    EXCLUDE_KEYWORDS,
    LONDON_KEYWORDS,
    MARKETING_DEPARTMENTS,
    MARKETING_KEYWORDS,
    MAX_DESCRIPTION_LENGTH,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)


@dataclass
class Job:
    title: str
    url: str
    description: str
    location: str
    company: str
    department: str = ""  # ATS department/category if available


def is_marketing_job(job):
    """Check title + description + department for marketing relevance."""
    text = f"{job.title} {job.description}".lower()
    dept = job.department.lower()

    # Check title/description against keywords
    keyword_match = any(kw in text for kw in MARKETING_KEYWORDS)

    # Check department/category against department keywords
    dept_match = any(kw in dept for kw in MARKETING_DEPARTMENTS)

    return keyword_match or dept_match


def is_london_job(job):
    loc = job.location.lower()
    title_desc = f"{job.title} {job.description}".lower()
    combined = f"{loc} {title_desc}"
    return any(kw in combined for kw in LONDON_KEYWORDS)


def is_too_senior(job):
    """Exclude roles that require senior-level experience."""
    title = job.title.lower()
    return any(kw in title for kw in EXCLUDE_KEYWORDS)


def truncate_desc(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = ""
    for s in sentences[:2]:
        if len(result) + len(s) > MAX_DESCRIPTION_LENGTH:
            break
        result = f"{result} {s}".strip() if result else s
    if not result:
        result = text[:MAX_DESCRIPTION_LENGTH]
        if len(text) > MAX_DESCRIPTION_LENGTH:
            result = result.rsplit(" ", 1)[0] + "..."
    return result


def load_companies():
    with open(COMPANIES_FILE, "r") as f:
        data = json.load(f)
    return data["companies"]


# ─── ATS-specific scrapers ──────────────────────────────────────────────────


async def scrape_greenhouse(client, name, slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    resp = await client.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", {}).get("name", "") if j.get("location") else ""
        desc_html = j.get("content", "")
        desc = BeautifulSoup(desc_html, "html.parser").get_text(" ") if desc_html else ""

        # Extract departments from Greenhouse API
        departments = j.get("departments", [])
        dept_names = [d.get("name", "") for d in departments if d.get("name")]
        dept_str = ", ".join(dept_names)

        jobs.append(Job(
            title=j.get("title", ""),
            url=j.get("absolute_url", ""),
            description=truncate_desc(desc),
            location=loc,
            company=name,
            department=dept_str,
        ))
    return jobs


async def scrape_lever(client, name, slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    resp = await client.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for j in data:
        cats = j.get("categories", {})
        loc = cats.get("location", "") or ""
        dept = cats.get("department", "") or cats.get("team", "") or ""
        desc = j.get("descriptionPlain", "") or ""
        jobs.append(Job(
            title=j.get("text", ""),
            url=j.get("hostedUrl", ""),
            description=truncate_desc(desc),
            location=loc,
            company=name,
            department=dept,
        ))
    return jobs


async def scrape_ashby(client, name, slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    resp = await client.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", "") or ""
        desc = j.get("descriptionPlain", "") or ""
        dept = j.get("department", "") or ""
        job_url = j.get("jobUrl", "") or f"https://jobs.ashbyhq.com/{slug}/{j.get('id', '')}"
        jobs.append(Job(
            title=j.get("title", ""),
            url=job_url,
            description=truncate_desc(desc),
            location=loc,
            company=name,
            department=dept,
        ))
    return jobs


async def scrape_workable(client, name, slug):
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    resp = await client.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", "") or j.get("city", "")
        desc = j.get("description", "") or ""
        dept = j.get("department", "") or ""
        shortcode = j.get("shortcode", "")
        job_url = f"https://apply.workable.com/{slug}/j/{shortcode}/" if shortcode else ""
        jobs.append(Job(
            title=j.get("title", ""),
            url=job_url,
            description=truncate_desc(desc),
            location=loc,
            company=name,
            department=dept,
        ))
    return jobs


async def scrape_careers_page(client, name, url):
    """Generic HTML scraper for company career pages."""
    resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = []
    job_links = soup.find_all("a", href=True)
    seen_urls = set()

    for link in job_links:
        href = link.get("href", "")
        text = link.get_text(strip=True)

        if not text or len(text) < 5 or len(text) > 200:
            continue

        href_lower = href.lower()
        job_indicators = ["/job/", "/jobs/", "/position/", "/opening/",
                          "/role/", "/vacancy/", "lever.co", "greenhouse.io",
                          "workable.com", "ashby", "apply"]
        is_job_link = any(ind in href_lower for ind in job_indicators)

        parent = link.find_parent(["div", "li", "article", "section"])
        parent_text = parent.get_text(" ", strip=True) if parent else ""

        if not is_job_link:
            text_lower = text.lower()
            title_indicators = ["manager", "lead", "head of", "director",
                                "specialist", "coordinator", "analyst",
                                "executive", "associate", "intern", "officer"]
            is_job_link = any(ind in text_lower for ind in title_indicators)

        if is_job_link:
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(url, href)
            elif not href.startswith("http"):
                continue

            if href in seen_urls:
                continue
            seen_urls.add(href)

            location = ""
            if parent:
                loc_el = parent.find(string=re.compile(r"london|uk|remote|hybrid", re.I))
                if loc_el:
                    location = loc_el.strip()[:100]

            desc = ""
            dept = ""
            if parent:
                desc_parts = parent.find_all(["p", "span", "div"])
                for dp in desc_parts:
                    dp_text = dp.get_text(strip=True)
                    if dp_text and dp_text != text and len(dp_text) > 10:
                        desc = dp_text
                        break
                # Try to find department from nearby elements
                dept_el = parent.find(string=re.compile(
                    r"marketing|growth|brand|content|digital|creative|communications",
                    re.I
                ))
                if dept_el:
                    dept = dept_el.strip()[:100]

            jobs.append(Job(
                title=text,
                url=href,
                description=truncate_desc(desc),
                location=location or "See listing",
                company=name,
                department=dept,
            ))

    return jobs


# ─── Dispatcher ──────────────────────────────────────────────────────────────

SCRAPERS = {
    "greenhouse": scrape_greenhouse,
    "lever": scrape_lever,
    "ashby": scrape_ashby,
    "workable": scrape_workable,
    "careers_page": scrape_careers_page,
}


async def scrape_company(client, company):
    name = company["name"]
    ats_type = company["type"]
    scraper = SCRAPERS.get(ats_type)

    if not scraper:
        logger.warning(f"[{name}] Unknown ATS type: {ats_type}")
        return []

    try:
        if ats_type == "careers_page":
            jobs = await scraper(client, name, company["url"])
        else:
            jobs = await scraper(client, name, company["slug"])

        all_count = len(jobs)
        # Filter for marketing + London + not too senior
        jobs = [j for j in jobs if is_marketing_job(j) and is_london_job(j) and not is_too_senior(j)]
        logger.info(f"[{name}] {all_count} total -> {len(jobs)} marketing+London "
                     f"(dept-tagged jobs included)")
        return jobs

    except httpx.HTTPStatusError as e:
        logger.warning(f"[{name}] HTTP {e.response.status_code}: {e}")
        return []
    except httpx.TimeoutException:
        logger.warning(f"[{name}] Request timed out")
        return []
    except Exception as e:
        logger.error(f"[{name}] Error: {e}")
        return []


async def scrape_all_companies():
    """Scrape all companies. Returns (jobs, stats)."""
    companies = load_companies()
    all_jobs = []
    successful = 0
    failed_names = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for i, company in enumerate(companies):
            if i > 0:
                await asyncio.sleep(DELAY_BETWEEN_COMPANIES)
            jobs = await scrape_company(client, company)
            if jobs is not None:
                all_jobs.extend(jobs)
                successful += 1
            else:
                failed_names.append(company["name"])

    stats = {
        "total_companies": len(companies),
        "successful": successful,
        "failed": len(failed_names),
        "failed_names": failed_names,
        "total_marketing_jobs": len(all_jobs),
    }

    logger.info(f"Scan complete: {stats['total_marketing_jobs']} marketing jobs from "
                f"{stats['successful']}/{stats['total_companies']} companies")

    return all_jobs, stats
