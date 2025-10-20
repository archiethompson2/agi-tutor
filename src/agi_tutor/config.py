import os

class Settings:
    # Read from env; allow a backup var name if you prefer
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # pick any chat-capable model you have access to

settings = Settings()
