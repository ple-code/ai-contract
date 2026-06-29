from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mingheng:mingheng_dev_2026@localhost:5432/mingheng"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    UPLOAD_DIR: str = "./storage/uploads"
    AI_BASE_URL: str = "https://stonerollai.com/v1"
    AI_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-6"
    # 协议：openai（标准 /chat/completions + Bearer）| anthropic（/v1/messages + x-api-key）
    # 智谱 CodePlan（代码套餐）key 必须用 anthropic 兼容端点 /api/anthropic
    AI_PROTOCOL: str = "openai"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
