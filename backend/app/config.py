"""应用配置。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="TRACE_", case_sensitive=False
    )

    # 存储后端类型: memory | file
    storage_backend: str = "memory"
    # file 存储时使用的目录
    file_storage_dir: str = "./data/traces"
    # CORS 允许的前端来源
    cors_origins: list[str] = ["http://localhost:5173"]
    # API 前缀
    api_prefix: str = "/api/v1"


settings = Settings()
