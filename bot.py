"""
Marketing Job Scanner — Telegram Bot
Scrapes career pages for marketing jobs in London and sends results via Telegram.
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SEEN_JOBS_FILE,
    TELEGRAM_MAX_LENGTH,
)
from scraper import scrape_all_companies, Job, load_companies

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── State tracking ──────────────────────────────────────────────────────────

last_scan_time: str | None = None
last_scan_stats: dict | None = None


def load_seen_jobs() -> set[str]:
    path = Path(SEEN_JOBS_FILE)
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        return set(data.get("seen_urls", []))
    return set()


def save_seen_jobs(seen: set[str]):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump({"seen_urls": sorted(seen)}, f, indent=2)


# ─── Message formatting ─────────────────────────────────────────────────────


def escape_md(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    special = r"_*[]()~`>#+-=|{}.!\\"
    result = ""
    for c in text:
        if c in special:
            result += f"\\{c}"
        else:
            result += c
    return result


def format_jobs_message(jobs: list[Job]) -> list[str]:
    """
    Format jobs grouped by company into Telegram messages.
    Returns list of message strings (split if too long).
    """
    if not jobs:
        return ["No marketing jobs found\\."]

    # Group by company
    by_company: dict[str, list[Job]] = {}
    for job in jobs:
        by_company.setdefault(job.company, []).append(job)

    messages = []
    current_msg = ""

    for company, company_jobs in sorted(by_company.items()):
        block = f"🏢 *{escape_md(company)}*\n\n"

        for job in company_jobs:
            title_escaped = escape_md(job.title)
            desc_escaped = escape_md(job.description) if job.description else "No description available"
            url_escaped = job.url.replace(")", "%29")  # escape parens in URLs

            job_block = (
                f"📌 {title_escaped}\n"
                f"📝 {desc_escaped}\n"
                f"🔗 [Apply]({url_escaped})\n\n"
            )
            block += job_block

        block += "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n\n"

        # Check if adding this block would exceed the limit
        if len(current_msg) + len(block) > TELEGRAM_MAX_LENGTH:
            if current_msg:
                messages.append(current_msg)
            current_msg = block
        else:
            current_msg += block

    if current_msg:
        messages.append(current_msg)

    return messages


# ─── Bot commands ────────────────────────────────────────────────────────────


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scrape all companies and send only NEW jobs."""
    global last_scan_time, last_scan_stats

    await update.message.reply_text("🔍 Scanning all companies for new marketing jobs... This may take a few minutes.")

    try:
        jobs, stats = await scrape_all_companies()
        last_scan_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        last_scan_stats = stats

        # Filter to new jobs only
        seen = load_seen_jobs()
        new_jobs = [j for j in jobs if j.url and j.url not in seen]

        if not new_jobs:
            summary = (
                f"No new marketing jobs found\\.\n\n"
                f"📊 Scanned {stats['total_companies']} companies, "
                f"{stats['total_marketing_jobs']} total marketing jobs "
                f"\\(all previously seen\\)\\."
            )
            if stats["failed_names"]:
                failed = ", ".join(escape_md(n) for n in stats["failed_names"])
                summary += f"\n⚠️ Failed: {failed}"
            await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN_V2)
            return

        # Send new jobs
        messages = format_jobs_message(new_jobs)
        for msg in messages:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2,
                                            disable_web_page_preview=True)

        # Update seen jobs
        for j in new_jobs:
            if j.url:
                seen.add(j.url)
        save_seen_jobs(seen)

        summary = (
            f"✅ Found {len(new_jobs)} new marketing job\\(s\\) "
            f"from {stats['successful']}/{stats['total_companies']} companies\\."
        )
        if stats["failed_names"]:
            failed = ", ".join(escape_md(n) for n in stats["failed_names"])
            summary += f"\n⚠️ Failed to scrape: {failed}"
        await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")


async def cmd_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scrape all companies and send the FULL list (don't update seen)."""
    global last_scan_time, last_scan_stats

    await update.message.reply_text("📋 Fetching all current marketing jobs... This may take a few minutes.")

    try:
        jobs, stats = await scrape_all_companies()
        last_scan_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        last_scan_stats = stats

        if not jobs:
            await update.message.reply_text("No marketing jobs found across all companies.")
            return

        messages = format_jobs_message(jobs)
        for msg in messages:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2,
                                            disable_web_page_preview=True)

        summary = (
            f"✅ {stats['total_marketing_jobs']} marketing job\\(s\\) "
            f"from {stats['successful']}/{stats['total_companies']} companies\\."
        )
        if stats["failed_names"]:
            failed = ", ".join(escape_md(n) for n in stats["failed_names"])
            summary += f"\n⚠️ Failed to scrape: {failed}"
        await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        logger.error(f"All scan failed: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status info."""
    companies = load_companies()
    seen = load_seen_jobs()

    status_lines = [
        f"📊 *Job Scanner Status*\n",
        f"Companies configured: {len(companies)}",
        f"Jobs tracked \\(seen\\): {len(seen)}",
        f"Last scan: {escape_md(last_scan_time) if last_scan_time else 'Never'}",
    ]

    if last_scan_stats:
        s = last_scan_stats
        status_lines.append(
            f"Last scan results: {s['total_marketing_jobs']} marketing jobs "
            f"from {s['successful']}/{s['total_companies']} companies"
        )
        if s["failed_names"]:
            failed = ", ".join(escape_md(n) for n in s["failed_names"])
            status_lines.append(f"⚠️ Failed: {failed}")

    await update.message.reply_text(
        "\n".join(status_lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Marketing Job Scanner Bot\n\n"
        "Commands:\n"
        "/scan — Find new marketing jobs\n"
        "/all — Show all current marketing jobs\n"
        "/status — Bot status\n"
    )


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable not set")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("all", cmd_all))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("Bot starting... Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
