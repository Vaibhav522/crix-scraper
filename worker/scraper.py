from .commentary import extract_commentary
from .scorecard import extract_scorecard
from .extract_page import extract_page
from db import AsyncSessionLocal, UrlType
from repository import claim_next_url, mark_url_failed
from playwright_stealth import Stealth




async def scraper(ContextManager):
    while True:
        slot = None
        page = None

        async with AsyncSessionLocal() as session:
            job = await claim_next_url(session=session)

        if not job:
            break

        try:
            # getting a random context from context pool
            slot, context = await ContextManager.acquire_context()

            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            if job.url_type == UrlType.scorecard:
                await extract_scorecard(page, job.url)
            elif job.url_type == UrlType.commentary:
                await extract_commentary(page, job.url)
            elif job.url_type in (UrlType.venue, UrlType.cricketer):
                await extract_page(page, job.url)

        except Exception as e:
            async with AsyncSessionLocal() as session:
                await mark_url_failed(session=session, url=job.url, error=str(e))
        
        finally:
            if page:
                await page.close()
            if slot:
                await ContextManager.release_context(slot)

            
                
