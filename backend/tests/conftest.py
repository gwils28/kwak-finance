import os

# Settings default to prod, which requires KWAK_SECRET_KEY. Set before any kwak_api import:
# kwak_api.main builds the app at import time.
os.environ["KWAK_ENV"] = "dev"
