import urllib
import os
import pathlib

# MongoDB
MONGODB_USERNAME = ''
MONGODB_PASSWORD = ''
MONGODB_HOST = '127.0.0.1'
MONGODB_URI = f'mongodb://{MONGODB_USERNAME}:{urllib.parse.quote(MONGODB_PASSWORD)}@{MONGODB_HOST}/novel'

DOWNLOAD_DIR = os.path.join(
    str(pathlib.Path(__file__).resolve().parent), '..', 'novel')

LOG_DIR = os.path.join(
    str(pathlib.Path(__file__).resolve().parent), '..', 'log')

SENTRY_INIT_URL = ""

MAX_WORKERS = 6
