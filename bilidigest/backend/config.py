from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    llm_api_key: str = ""
    llm_base_url: str = "https://api.minimax.chat/v1"
    llm_model: str = "MiniMax-Text-01"

    data_dir: str = "../data"
    max_video_duration: int = 14400
    max_process_duration: int = 7200

    backend_port: int = 8000
    frontend_port: int = 3000
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def assets_path(self) -> Path:
        return self.data_path / "assets"

    @property
    def db_path(self) -> Path:
        return self.data_path / "bilidigest.db"


settings = Settings()

# 确保数据目录存在
settings.data_path.mkdir(parents=True, exist_ok=True)
settings.assets_path.mkdir(parents=True, exist_ok=True)
