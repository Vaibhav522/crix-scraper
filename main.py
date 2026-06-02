from dotenv import load_dotenv
load_dotenv()


import asyncio
from multiprocessing import Process
from db import AsyncSessionLocal
from playwright.async_api import async_playwright
from worker.scraper import scraper
from utils import zip_worker, upload_worker, BrowserContext, zip_bucket_sync, upload_bucket_sync
from repository import get_or_create_open_bucket


SCRAPER_PROCESSES = 2
WORKERS_PER_PROCESS = 2


async def run_scraper_process(process_id: int):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        ContextManager = BrowserContext(browser=browser)
        await ContextManager.create_context_pool()

        tasks = [asyncio.create_task(scraper(ContextManager)) for _ in range(WORKERS_PER_PROCESS)]

        await asyncio.gather(*tasks)
        await browser.close()

        
def scraper_process_entry(process_id: int):
    asyncio.run(run_scraper_process(process_id))

def zip_process_entry():
    asyncio.run(zip_worker())

def upload_process_entry():
    asyncio.run(upload_worker())

def main():
    processes = []

    for i in range(SCRAPER_PROCESSES):
        process = Process(target=scraper_process_entry, args=(i,))
        process.start()
        processes.append(process)

    zipper = Process(target=zip_process_entry)
    zipper.start()
    processes.append(zipper)

    uploader = Process(target=upload_process_entry)
    uploader.start()
    processes.append(uploader)

    for process in processes:
        process.join()

if __name__ == "__main__":
    main()