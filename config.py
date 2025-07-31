import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FACEBOOK_ID = os.getenv("FACEBOOK_ID")
INSTAGRAM_ID = os.getenv("INSTAGRAM_ID")
GA_PROPERTY_ID = os.getenv("GA_PROPERTY_ID")
GA_KEY_PATH = os.getenv("GA_KEY_PATH")
LOGO_PATH = os.getenv("LOGO_PATH")