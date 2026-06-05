import os
import json
import asyncio
from settings import ARCHIVAL_PATH
from playwright_stealth import Stealth # type: ignore
from utils import gen_filename
from db import AsyncSessionLocal
from repository import mark_url_completed, mark_url_failed


COMMENTARY_PATH = "/v1/pages/match/comments"

class CommentaryTracker:
    """Tracks API requests/responses and signals when data arrives."""

    def __init__(self):
        self.captured_data = []
        self._new_data = asyncio.Event()

    # ── Use page.on("request") to OBSERVE (no continue_ needed) ──
    async def on_request(self, request):
        if COMMENTARY_PATH in request.url:
            print(f"  → API request fired: {request.url[:100]}...")

    # ── Ring the doorbell when a response lands ──
    async def on_response(self, response):
        if COMMENTARY_PATH in response.url:
            try:
                data = await response.json()
                self.captured_data.append({
                    "url": response.url,
                    "data": data,
                })
                self._new_data.set()  # 🔔 Ring!
                print(f"  ← Response #{len(self.captured_data)} captured")
            except Exception as e:
                print(f"  ✗ Parse error: {e}")

    async def wait_for_data(self, timeout=10):
        """Block until new data arrives or timeout. Returns True if data came."""
        self._new_data.clear()
        try:
            await asyncio.wait_for(self._new_data.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


async def scroll_until_done(page, tracker, max_misses=4):
    """Scroll down, wait for API responses, stop when no new data arrives."""

    # First, wait for the initial data load (page might auto-fetch on load)
    print("  Waiting for initial data load...")
    got_initial = await tracker.wait_for_data(timeout=15)

    if not got_initial and len(tracker.captured_data) == 0:
        print("  ⚠ No initial data captured! API path may be wrong.")
        print("  Open DevTools → Network tab and verify the actual URL.")

    consecutive_misses = 0

    while consecutive_misses < max_misses:
        prev_count = len(tracker.captured_data)

        # Scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        # Wait for the doorbell 🔔
        got_data = await tracker.wait_for_data(timeout=10)

        current_count = len(tracker.captured_data)

        if current_count > prev_count:
            consecutive_misses = 0
            print(f"  ✓ New data: {prev_count} → {current_count} responses")
        else:
            consecutive_misses += 1
            print(f"  ○ No new data after scroll (miss {consecutive_misses}/{max_misses})")

    print(f"  Done scrolling. Total: {len(tracker.captured_data)} responses")


async def extract_commentary(page, commentary_url):
    tracker = CommentaryTracker()

    # ── OBSERVE requests (no interception, no continue_ needed) ──
    page.on("request", lambda req: asyncio.ensure_future(tracker.on_request(req)))
    page.on("response", lambda res: asyncio.ensure_future(tracker.on_response(res)))

    
    await page.goto(commentary_url, wait_until="domcontentloaded", timeout=120000)
    await asyncio.sleep(3)

    # ── Get innings count ──
    await page.evaluate(
        "document.querySelectorAll(\"button[aria-expanded='false']\")[0].click()"
    )
    await page.wait_for_selector(".tippy-content li", timeout=5000)
    innings_count = await page.evaluate(
        "document.querySelectorAll('.tippy-content li').length"
    )
    print(f"Found {innings_count} innings")

    await page.evaluate(
        "document.querySelectorAll(\"button[aria-expanded='true']\")[0].click()"
    )
    await asyncio.sleep(1)

    # ── Process each inning ──
    all_data = []

    for idx in range(innings_count):
        print(f"\n{'='*50}")
        print(f"Inning {idx + 1} of {innings_count}")
        print(f"{'='*50}")

        # Reset tracker for this inning
        tracker.captured_data.clear()

        # Select inning from dropdown
        await page.evaluate(
            "document.querySelectorAll(\"button[aria-expanded='false']\")[0].click()"
        )
        await page.wait_for_selector(".tippy-content li", timeout=5000)
        await page.evaluate(
            f"document.querySelectorAll('.tippy-content li')[{idx}].querySelector('div').click()"
        )
        await asyncio.sleep(2)

        # Scroll and capture
        await scroll_until_done(page, tracker, max_misses=4)

        # Accumulate THIS inning's data before clearing
        all_data.extend(tracker.captured_data)
        print(f"  Inning {idx+1} total: {len(tracker.captured_data)} responses")

        # ── Save everything ──
        print(f"\nTotal across all innings: {len(all_data)} responses")
    
    file_name = f"{gen_filename(commentary_url)}.json"
    

    file_path = os.path.join(ARCHIVAL_PATH, file_name)
        
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(all_data, file, indent=2)

    if os.path.getsize(file_path) > 2048:
        async with AsyncSessionLocal() as session:
            await mark_url_completed(session=session, url=commentary_url, file_name=file_name, raw_file_size=os.path.getsize(file_path))
    else:
        async with AsyncSessionLocal() as session:
            await mark_url_failed(session=session, url=commentary_url, error="File size: smaller than acceptable")
        os.remove(file_path)

