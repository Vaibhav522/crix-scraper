import os
from settings import ARCHIVAL_PATH, REQUEST_TIMEOUT
from utils import gen_filename
from db import AsyncSessionLocal, UrlType
from repository import complete_scorecard, mark_url_failed


async def extract_scorecard(page, score_card_url):
    await page.goto(score_card_url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
    content = await page.content()

    extraction_script = """
        (() => {
            let data = {
                is_commentary: null,
                cricketers: [],
                venue: []
            }

            // extracting commentary page link
            let commentary_element = document.querySelector('a[href*="/ball-by-ball-commentary"]');
            data.is_commentary = commentary_element ? commentary_element.href : null;

            // extracting all cricketer pages links
            let cricketer_elements = document.querySelectorAll('a[href*="/cricketers/"]');
            if (cricketer_elements) {
                cricketer_elements.forEach(item => data.cricketers.push(item.href))
            } else {
                data.cricketers = null
            }

            // extracting all venue pages links
            let venue_element = document.querySelectorAll('a[href*="/cricket-grounds/"]');
            if (venue_element) {
                venue_element.forEach(item => data.venue.push(item.href))
            } else {
                data.venue = null
            }

            return data
        })();
    """
    # checking if commentary is present or not
    data = await page.evaluate(extraction_script)
    
    
    discovered_urls = []

    if data["is_commentary"]:
        discovered_urls.append((data["is_commentary"], UrlType.commentary))

    if data["cricketers"]:
        for i in data["cricketers"]:
            discovered_urls.append((i, UrlType.cricketer))

    if data["venue"]:
        for i in data["venue"]:
            discovered_urls.append((i, UrlType.venue))
        
    file_name = f"{gen_filename(score_card_url)}.html"

    file_path = os.path.join(ARCHIVAL_PATH, file_name)


    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)
    
    if os.path.getsize(file_path) > 2048:
        async with AsyncSessionLocal() as session:
            await complete_scorecard(
                session=session,
                url=score_card_url,
                file_name=file_name,
                raw_file_size=os.path.getsize(file_path),
                discovered_urls=discovered_urls,
            )
    else:
        async with AsyncSessionLocal() as session:
            await mark_url_failed(session=session, url=score_card_url, error="File size: smaller than acceptable")
        os.remove(file_path)