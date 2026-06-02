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

# Total context's per browser
CONTEXT_COUNT = 5

# context refresh count
CONTEXT_REFRESH_COUNT = 50

# dummy user agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
