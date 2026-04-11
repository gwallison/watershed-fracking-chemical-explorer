"""
URL constants extracted from openFF.common.handles for standalone use
in the watershed chemical explorer app.
"""

browser_root = "https://storage.googleapis.com/open-ff-browser/"
browser_chemhaz_root = "https://storage.googleapis.com/open-ff-chem-profiles"
repo_root_url = "https://storage.googleapis.com/open-ff-common/repos/current_repo/"
repo_pickles_url = repo_root_url + "pickles/"
full_url = repo_root_url + "full_df.parquet"

# Local image directory — not available in deployed context, so fingerprint/molecule
# images will fall back gracefully to "not available" in text_handlers.py
pic_dir = ""

browser_api_links_dir = browser_root + "api_links/"
