from dotenv import load_dotenv
load_dotenv()

import logging
import os
import uuid
import hashlib
import asyncio
import zstandard as zstd
from db import AsyncSessionLocal
from b2sdk.v2 import B2Api, InMemoryAccountInfo
from settings import ARCHIVAL_PATH, ZIPPED_PATH, BUCKET_NAME, SRAPER_WORKER_STATUS, UPLOAD_WORKER_STATUS, ZIPPER_WORKER_STATUS
from repository import claim_file_for_upload, claim_file_for_zipping, mark_file_zipped, mark_file_uploaded
from multiprocessing.shared_memory import SharedMemory


logger = logging.getLogger(__name__)


# generating filename from url with a hashing algorithm, gauranteing same text generates same hash
def gen_filename(url:str):
    # Output is always 32 characters long
    md5_hash = hashlib.md5(url.encode()).hexdigest()
    return md5_hash

def gen_bucket_id():
    return uuid.uuid4()


def get_b2_bucket():
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", os.getenv("B2_KEY_ID"), os.getenv("B2_APPLICATION_KEY"))
    return b2_api.get_bucket_by_name(BUCKET_NAME)


def upload_file(zipped_file_name: str):
    bucket = get_b2_bucket()
    local_path = os.path.join(ZIPPED_PATH, zipped_file_name)
    remote_name = f"archival/{zipped_file_name}"
    uploaded = bucket.upload_local_file(local_file=local_path, file_name=remote_name)
    return uploaded.id_


def zip_file(file_name: str):
    file_path = os.path.join(ARCHIVAL_PATH, file_name)
    final_name = f"{file_name}.zst"
    final_path = os.path.join(ZIPPED_PATH, final_name)

    # Initialize the compressor (level 3 is default, max is 22)
    cctx = zstd.ZstdCompressor(level=19)

    with open(file_path, "rb") as f_in:
        with open(final_path, "wb") as f_out:
            # Stream the compression to handle large files efficiently
            cctx.copy_stream(f_in, f_out)
    
    return final_name


status = SharedMemory(name="worker_status")

async def upload_worker():
    logger.info("Intialized upload worker")
    while True:
        async with AsyncSessionLocal() as session:
            file = await claim_file_for_upload(session=session)
        
        if not file:
            zipper_status = bool(status.buf[ZIPPER_WORKER_STATUS])
            if not zip_worker:
                status.buf[UPLOAD_WORKER_STATUS] = 0
                break
            
            await asyncio.sleep(5)
            continue

        try:
            logger.info(f"Got zip job, {file.zipped_name}")
            # uploading zipped file
            uploaded_id = await asyncio.to_thread(upload_file, file.zipped_name)

            # marking file uploaded 
            async with AsyncSessionLocal() as session:
                await mark_file_uploaded(session=session, file_name=file.file_name, uploaded_id=uploaded_id)
            
            if ZIPPED_PATH and file.zipped_name and file.file_name:
                raw_file, zip_file = os.path.join(ARCHIVAL_PATH, file.file_name), os.path.join(ZIPPED_PATH, file.zipped_name)
                if os.path.exists(raw_file):
                    os.remove(raw_file)
                if os.path.exists(zip_file):
                    os.remove(zip_file)
        
        except Exception as e:
            logger.error(f'Error in upload worker: {e}')



async def zip_worker():
    logger.info("Initalized zip worker")

    while True:
        async with AsyncSessionLocal() as session:
            file = await claim_file_for_zipping(session=session)
        
        if not file:
            scraper_status = bool(status.buf[SRAPER_WORKER_STATUS])

            if not scraper_status:
                status.buf[ZIPPER_WORKER_STATUS] = 0
                break

            await asyncio.sleep(5)
            continue
        
        try:
            logger.info(f"Got zip job, {file.file_name}")
            # zipping the file
            zipped_file_name = zip_file(file.file_name)

            # marking zipped
            async with AsyncSessionLocal() as session:
                await mark_file_zipped(session=session, file_name=file.file_name, zipped_name=zipped_file_name)
        except Exception as e:
            logger.error(f'Error in zip worker: {e}')
