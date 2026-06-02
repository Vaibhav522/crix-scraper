import os
from utils import gen_filename
from db import AsyncSessionLocal
from settings import ARCHIVAL_PATH, REQUEST_TIMEOUT
from repository import mark_url_completed


# both the player, venue is a single page download we can achieve this from a single function


async def extract_page(page, url):
    await page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
    content = await page.content()
    
    file_name = f"{gen_filename(url)}.html"

    file_path = os.path.join(ARCHIVAL_PATH, file_name)

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)

    async with AsyncSessionLocal() as session:
        await mark_url_completed(session=session, url=url, file_name=file_name)