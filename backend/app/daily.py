"""The morning paper by email.

Every morning (DAILY_EMAIL_HOUR, default 7, in DAILY_EMAIL_TIMEZONE, default Asia/Karachi),
each signed-in reader who wants daily email gets today's paper: printed if it isn't yet,
then emailed with the PDF attached. A reader never gets the morning email twice in a day.

Two ways to trigger it:
- a small thread inside the server checks every few minutes (fine while the server runs);
- POST /api/cron/daily with the CRON_SECRET header, for an outside scheduler once Vale is
  hosted on a server that sleeps when idle.
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

from app import editions, mailer, store

log = logging.getLogger(__name__)
CHECK_EVERY_SECONDS = 300
_run_lock = threading.Lock()
_last_run_day: str | None = None


def timezone() -> ZoneInfo:
    try:
        return ZoneInfo(os.getenv("DAILY_EMAIL_TIMEZONE", "Asia/Karachi").strip() or "Asia/Karachi")
    except Exception:
        return ZoneInfo("UTC")


def send_hour() -> int:
    try:
        return min(23, max(0, int(os.getenv("DAILY_EMAIL_HOUR", "7"))))
    except ValueError:
        return 7


def local_today(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone())).date().isoformat()


def wants_email(user: dict, today: str) -> bool:
    return (
        bool(user.get("onboarded"))
        and bool((user.get("email") or "").strip())
        and user.get("daily_email", True)
        and user.get("last_daily_email") != today
    )


def send_one(uid: str, today: str) -> str:
    """Print (if needed) and email one reader's paper. Returns "sent", "skipped" or an error."""
    try:
        if not wants_email(store.load(uid)["user"], today):
            return "skipped"
        edition = editions.get_or_create_today(uid)
        user = store.load(uid)["user"]
        mailer.send_edition(uid, user, edition)
        store.update(lambda d: d["user"].update(last_daily_email=today), uid)
        return "sent"
    except Exception as exc:  # one reader's problem must not stop the others
        log.warning("daily email for %s failed: %s", uid, exc)
        return f"error: {exc}"


def run(now: datetime | None = None, workers: int = 2) -> dict:
    """Send everyone's morning paper. Safe to call more than once a day."""
    today = local_today(now)
    if not mailer.configured():
        return {"day": today, "sent": 0, "skipped": 0, "errors": ["email is not configured"]}
    with _run_lock:
        uids = [uid for uid, user in store.list_readers() if wants_email(user, today)]
        # Two at a time: each new edition is one Gemini call.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda u: send_one(u, today), uids))
    return {
        "day": today,
        "sent": results.count("sent"),
        "skipped": results.count("skipped"),
        "errors": [r for r in results if r.startswith("error")],
    }


def due(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone())
    return now.hour >= send_hour() and _last_run_day != local_today(now)


def _loop(stop: threading.Event) -> None:
    global _last_run_day
    while not stop.wait(CHECK_EVERY_SECONDS):
        try:
            if due():
                summary = run()
                _last_run_day = summary["day"]
                log.info("morning papers: %s", summary)
        except Exception as exc:
            log.warning("morning paper run failed: %s", exc)


def start_scheduler() -> threading.Event | None:
    """Start the in-server morning check if email is set up (and not switched off)."""
    if not mailer.configured() or os.getenv("DAILY_EMAIL_ENABLED", "true").lower() == "false":
        return None
    stop = threading.Event()
    threading.Thread(target=_loop, args=(stop,), name="vale-morning-paper", daemon=True).start()
    return stop
