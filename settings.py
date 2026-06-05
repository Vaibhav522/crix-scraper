# settings.py

import os

# project working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Scraper variabls
REQUEST_TIMEOUT = 120000

# maximum attempts
MAX_ATTEMPTS = 4

# Blackblaze bucket name
BUCKET_NAME = "crix-archive"

# archival path
ARCHIVAL_PATH = os.path.join(BASE_DIR, "storage", "archival")
os.makedirs(ARCHIVAL_PATH, exist_ok=True)

# zipped path
ZIPPED_PATH = os.path.join(BASE_DIR, "storage", "zipped")
os.makedirs(ZIPPED_PATH, exist_ok=True)

# total files in a single zipped bucket
BUCKET_SIZE = 50 #10000

# dummy user agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


# Total browser instances per process
BROWSER_COUNT = 1

# Total scraper process 
SCRAPER_PROCESSES = 2

# Total active concurrent workers 
SCRAPER_PER_PROCESS = 2


# Recycle browser after this use
BROWSER_MAX_USE = 100



# Defining index of shared memory state



SRAPER_WORKER_STATUS = 0
ZIPPER_WORKER_STATUS = 1
UPLOAD_WORKER_STATUS = 3