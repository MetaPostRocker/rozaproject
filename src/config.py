import json
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    google_sheets_id: str
    google_service_account_json: str

    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str = "rental-receipts"
    r2_public_url: str = ""  # Public URL from Cloudflare R2 (e.g., https://pub-xxx.r2.dev)

    owner_telegram_id: int

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def google_credentials(self) -> dict:
        return json.loads(self.google_service_account_json)

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"


settings = Settings()
