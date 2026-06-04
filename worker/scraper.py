import logging

from .commentary import extract_commentary
from .scorecard import extract_scorecard
from .extract_page import extract_page
from db import AsyncSessionLocal, UrlType
from repository import claim_next_url, mark_url_failed
from playwright_stealth import Stealth
from playwright.async_api import async_playwright
from settings import USER_AGENT, BROWSER_MAX_USE


logger = logging.getLogger(__name__)


async def create_browser():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)

    logger.info("Created new browser")
    return browser

async def scraper(index):
    browser = None
    browser_used_for = 0
    browser = await create_browser()

    logger.info(f"Started scraper worker: {index}")

    while True:
        page = None
        context = None
        
        async with AsyncSessionLocal() as session:
            job = await claim_next_url(session=session)

        if not job:
            logger.info("No scraping job present, closing scraper worker")
            await browser.close()
            break

        try:
            logger.info(f"Got a job for scraper worker of type: {job.url_type}")
            # getting a random context from browser pool
            context = await browser.new_context(viewport={"width": 1920, "height": 1080}, user_agent=USER_AGENT)

            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            if job.url_type == UrlType.scorecard:
                await extract_scorecard(page, job.url)
            elif job.url_type == UrlType.commentary:
                await extract_commentary(page, job.url)
            elif job.url_type in (UrlType.venue, UrlType.cricketer):
                await extract_page(page, job.url)

        except Exception as e:
            logger.error(f"Scraper worker {index} faced error: {e}")
            async with AsyncSessionLocal() as session:
                await mark_url_failed(session=session, url=job.url, error=str(e))
        
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
            
            if browser_used_for > BROWSER_MAX_USE:
                await browser.close()

                browser_used_for = 0
                browser = await create_browser()
            
            browser_used_for += 1

            
                
