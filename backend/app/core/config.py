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

    # J7Tracker X stream (unofficial socket.io feed, JWT session token)
    J7_ENABLED: bool = True
    J7_SESSION_TOKEN: Optional[str] = None

    HELIUS_API_KEY: Optional[str] = None
    HELIUS_WS_URL: str = "wss://mainnet.helius-rpc.com"

    JUPITER_API_KEY: Optional[str] = None
    JUPITER_API_URL: str = "https://quote-api.jup.ag/v6"

    JITO_API_KEY: Optional[str] = None
    JITO_BLOCK_ENGINE_URL: str = "https://mainnet.block-engine.jito.wtf"

    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # NVIDIA NIM (OpenAI-compatible, free tier)
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_API_BASE: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-lightning-30b-a3b"

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

    # Signal engine (narrative -> trade decisions)
    SIGNAL_ENABLED: bool = True
    SIGNAL_CONFIDENCE_THRESHOLD: float = 0.7
    SIGNAL_MIN_CLUSTER_SIZE: int = 10
    SIGNAL_POSITION_SIZE_USD: float = 100.0
    SIGNAL_MAX_OPEN_POSITIONS: int = 5
    SIGNAL_COOLDOWN_HOURS: int = 24
    SIGNAL_TAKE_PROFIT_PCT: float = 30.0
    SIGNAL_STOP_LOSS_PCT: float = 15.0

    # Token launch discovery (RugCheck + DexScreener new launches)
    LAUNCHES_ENABLED: bool = True
    LAUNCHES_POLL_SECONDS: int = 60
    LAUNCHES_MAX_PER_POLL: int = 50

    # Volume watcher (catches silent buying: trading surges with no posts)
    VOLUME_ENABLED: bool = True
    VOLUME_POLL_SECONDS: int = 60
    VOLUME_WATCH_LIMIT: int = 40          # newest tracked tokens checked per poll
    VOLUME_MIN_BUYS_H1: int = 150         # buys in the last hour
    VOLUME_MIN_VOLUME_H1_USD: float = 25000.0
    VOLUME_SPIKE_MULTIPLE: float = 3.0    # h1 volume vs the previous reading
    VOLUME_COOLDOWN_HOURS: int = 6        # per-token silence after an alert

    # Token safety gate (pre-trade rug checks, ported from RugRadar)
    SAFETY_ENABLED: bool = True
    SAFETY_MAX_RISK_SCORE: int = 60          # AVOID / scores above this are blocked
    SAFETY_MIN_LIQUIDITY_USD: float = 20000.0
    SAFETY_MIN_VOLUME_H24_USD: float = 10000.0

    # Monitoring
    PROMETHEUS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"


settings = Settings()