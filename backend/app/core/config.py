from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Narrative Sniper"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/narrative_sniper"
    REDIS_URL: str = "redis://localhost:6379"

    # API Keys
    TWITTER_API_KEY: Optional[str] = None
    TWITTER_API_SECRET: Optional[str] = None
    TWITTER_BEARER_TOKEN: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_SECRET: Optional[str] = None

    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None

    DISCORD_BOT_TOKEN: Optional[str] = None

    HELIUS_API_KEY: Optional[str] = None
    HELIUS_WS_URL: str = "wss://mainnet.helius-rpc.com"

    JUPITER_API_KEY: Optional[str] = None
    JUPITER_API_URL: str = "https://quote-api.jup.ag/v6"

    JITO_API_KEY: Optional[str] = None
    JITO_BLOCK_ENGINE_URL: str = "https://mainnet.block-engine.jito.wtf"

    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Auth
    SECRET_KEY: str = "dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Ingestion
    INGESTION_BATCH_SIZE: int = 100
    INGESTION_INTERVAL_SECONDS: int = 60
    MAX_CONCURRENT_INGESTIONS: int = 10

    # Intelligence
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    CLUSTER_MIN_SIZE: int = 5
    CLUSTER_MIN_SAMPLES: int = 3
    NARRATIVE_CONFIDENCE_THRESHOLD: float = 0.6

    # Execution
    PAPER_TRADING: bool = True
    MAX_POSITION_SIZE_USD: float = 1000.0
    MAX_DAILY_LOSS_USD: float = 500.0
    SLIPPAGE_BPS: int = 100
    PRIORITY_FEE_LAMPORTS: int = 10000

    # Monitoring
    PROMETHEUS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"


settings = Settings()