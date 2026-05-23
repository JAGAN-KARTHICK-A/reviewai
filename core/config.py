import dotenv
import os

dotenv.load_dotenv()

class Settings:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
    GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
    GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "")

settings = Settings()
