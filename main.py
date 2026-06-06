import multiprocessing
from dotenv import load_dotenv
load_dotenv()

# Python imports
import logging
import asyncio
from multiprocessing import Process, set_start_method

# Package imports
from db import init_db
from worker.scraper import scraper
from utils import zip_worker, upload_worker
from settings import SCRAPER_PROCESSES, SCRAPER_PER_PROCESS, SCRAPER_WORKER_STATUS, ZIPPER_WORKER_STATUS, UPLOAD_WORKER_STATUS

# shared memory
from multiprocessing.shared_memory import SharedMemory




try:
    worker_status = SharedMemory(create=True, name="worker_status", size=3)
except:
    worker_status = SharedMemory(name="worker_status")


worker_status.buf[0:3] = b'\x00\x00\x00'


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("project.log"), # Saves to file
        logging.StreamHandler()             # Prints to console
    ]
)



logger = logging.getLogger(__name__)


async def run_scraper_process(process_id: int):
    tasks = [asyncio.create_task(scraper(index=i)) for i in range(SCRAPER_PER_PROCESS)]
    await asyncio.gather(*tasks)

        
def scraper_process_entry(process_id: int):
    logger.info("Starting scraper worker")
    asyncio.run(run_scraper_process(process_id))
    worker_status.buf[SCRAPER_WORKER_STATUS] = 0

def zip_process_entry():
    logger.info("Starting zipper worker")
    asyncio.run(zip_worker())

def upload_process_entry():
    logger.info("Starting upload worker")
    asyncio.run(upload_worker())

def main():
    # intializing db
    asyncio.run(init_db())
    
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


    worker_status.buf[SCRAPER_WORKER_STATUS] = 1
    worker_status.buf[ZIPPER_WORKER_STATUS] = 1
    worker_status.buf[UPLOAD_WORKER_STATUS] = 1


    for process in processes:
        process.join()
    
    worker_status.close()
    worker_status.unlink()


if __name__ == "__main__":
    set_start_method("spawn")
    main()