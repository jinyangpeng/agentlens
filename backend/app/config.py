"""应用配置。"""
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="TRACE_", case_sensitive=False
    )

    # 存储后端类型: memory | file | sqlite | postgresql
    storage_backend: str = "memory"
    # file 存储时使用的目录
    file_storage_dir: str = "./data/traces"
    # 数据库连接串（sqlite/postgresql 后端使用）。留空时按 backend 自动推导默认值。
    database_url: str = ""
    # CORS 允许的前端来源
    cors_origins: list[str] = ["http://localhost:5173"]
    # API 前缀
    api_prefix: str = "/api/v1"

    @model_validator(mode="after")
    def _default_database_url(self) -> "Settings":
        """未显式配置 database_url 时，按 storage_backend 推导默认值。"""
        if not self.database_url:
            if self.storage_backend == "sqlite":
                # Docker: /app/data/db/traces.db；本地: ./data/db/traces.db
                self.database_url = "sqlite+aiosqlite:///./data/db/traces.db"
            elif self.storage_backend == "postgresql":
                # postgresql 必须通过 TRACE_DATABASE_URL 显式提供连接串
                raise ValueError(
                    "storage_backend=postgresql 时必须配置 TRACE_DATABASE_URL"
                )
        return self


settings = Settings()
