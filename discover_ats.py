"""
ATS Discovery Script — probes Greenhouse, Lever, Ashby, and Workable APIs
to find which ATS each company uses.
"""

import asyncio
import json
import re
import sys

import httpx
import openpyxl


def slugify(name):
    """Generate likely slug variations from a company name."""
    # Base: lowercase, remove special chars, join with hyphens or nothing
    clean = re.sub(r"[''`]", "", name)  # Remove apostrophes
    clean = re.sub(r"[^a-zA-Z0-9\s&.-]", "", clean)

    # Variations
    slugs = set()

    # Standard slug: lowercase, spaces to hyphens
    s1 = re.sub(r"[\s&.]+", "-", clean.lower()).strip("-")
    s1 = re.sub(r"-+", "-", s1)
    slugs.add(s1)

    # No separators
    s2 = re.sub(r"[\s&.\-]+", "", clean.lower())
    slugs.add(s2)

    # Underscores
    s3 = re.sub(r"[\s&.\-]+", "_", clean.lower()).strip("_")
    slugs.add(s3)

    # First word only (e.g., "Adyen" from "Adyen N.V.")
    first = clean.split()[0].lower() if clean.split() else ""
    if first and len(first) > 2:
        slugs.add(first)

    # Two words joined (e.g., "capitalontap" from "Capital on Tap")
    words = [w.lower() for w in clean.split() if w.lower() not in ("the", "a", "an", "of", "on", "in", "and", "&")]
    if len(words) >= 2:
        slugs.add("".join(words))
        slugs.add("-".join(words))
        slugs.add("".join(words[:2]))
        slugs.add("-".join(words[:2]))

    # Handle parenthetical names like "CB Payments (Coinbase)" -> also try "coinbase"
    paren = re.search(r"\(([^)]+)\)", name)
    if paren:
        inner = paren.group(1).strip().lower()
        inner_slug = re.sub(r"[^a-z0-9]+", "", inner)
        slugs.add(inner_slug)
        slugs.add(re.sub(r"[^a-z0-9]+", "-", inner.lower()).strip("-"))

    # Remove empty strings
    slugs.discard("")

    return list(slugs)


async def check_greenhouse(client, slug):
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        resp = await client.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if "jobs" in data:
                return True
    except Exception:
        pass
    return False


async def check_lever(client, slug):
    try:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        resp = await client.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return True
    except Exception:
        pass
    return False


async def check_ashby(client, slug):
    try:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        resp = await client.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if "jobs" in data:
                return True
    except Exception:
        pass
    return False


async def check_workable(client, slug):
    try:
        url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
        resp = await client.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if "jobs" in data:
                return True
    except Exception:
        pass
    return False


async def discover_company(client, name, semaphore):
    """Try all slug variations against all ATS APIs."""
    slugs = slugify(name)

    async with semaphore:
        for slug in slugs:
            # Check all 4 ATS types in parallel for this slug
            gh, lv, ab, wk = await asyncio.gather(
                check_greenhouse(client, slug),
                check_lever(client, slug),
                check_ashby(client, slug),
                check_workable(client, slug),
            )

            if gh:
                return {"name": name, "type": "greenhouse", "slug": slug}
            if lv:
                return {"name": name, "type": "lever", "slug": slug}
            if ab:
                return {"name": name, "type": "ashby", "slug": slug}
            if wk:
                return {"name": name, "type": "workable", "slug": slug}

    return None


def read_excel(path):
    """Read company names from Excel file."""
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    companies = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        num, name, sector, sponsor_name, status, notes = row
        if name and isinstance(num, (int, float)):
            companies.append(name.strip())
    return companies


def read_existing(path):
    """Read existing companies.json."""
    with open(path) as f:
        data = json.load(f)
    return data


async def main():
    excel_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/chan/Downloads/London_Marketing_Companies_Visa_Sponsors (1).xlsx"
    companies_json_path = "companies.json"

    # Read Excel
    excel_companies = read_excel(excel_path)
    print(f"Found {len(excel_companies)} companies in Excel")

    # Read existing
    existing_data = read_existing(companies_json_path)
    existing_names = {c["name"].lower() for c in existing_data["companies"]}
    existing_by_slug = {}
    for c in existing_data["companies"]:
        slug = c.get("slug") or c.get("url", "")
        existing_by_slug[slug.lower()] = c["name"]

    # Find new companies not already in companies.json
    new_companies = [c for c in excel_companies if c.lower() not in existing_names]
    print(f"{len(new_companies)} companies not yet in companies.json")

    # Discover ATS for new companies
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    semaphore = asyncio.Semaphore(10)  # Limit concurrent requests

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        tasks = [discover_company(client, name, semaphore) for name in new_companies]

        discovered = []
        not_found = []
        total = len(tasks)

        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            done = i + 1
            if result:
                discovered.append(result)
                print(f"  [{done}/{total}] ✓ {result['name']} -> {result['type']}:{result['slug']}")
            else:
                # We need to figure out which company this was
                pass

        # Re-run to collect not_found names properly
        # (as_completed loses order, let's just gather)
        print(f"\nDiscovery complete. Running final pass...")

        results = await asyncio.gather(*[discover_company(client, name, semaphore) for name in new_companies])

    discovered = []
    not_found = []
    for name, result in zip(new_companies, results):
        if result:
            discovered.append(result)
        else:
            not_found.append(name)

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Discovered: {len(discovered)}")
    print(f"  Not found:  {len(not_found)}")
    print(f"{'='*60}")

    # Merge into existing companies.json
    # Avoid duplicate slugs
    for d in discovered:
        slug_key = d["slug"].lower()
        if slug_key not in existing_by_slug:
            existing_data["companies"].append(d)

    # Save updated companies.json
    with open(companies_json_path, "w") as f:
        json.dump(existing_data, f, indent=2)
    print(f"\nUpdated {companies_json_path} — now has {len(existing_data['companies'])} companies")

    # Save not-found list for reference
    if not_found:
        with open("companies_not_found.txt", "w") as f:
            f.write("# Companies where no ATS API was auto-detected.\n")
            f.write("# You can manually add these to companies.json with their careers page URL.\n\n")
            for name in sorted(not_found):
                f.write(f"{name}\n")
        print(f"Saved {len(not_found)} unresolved companies to companies_not_found.txt")


if __name__ == "__main__":
    asyncio.run(main())
