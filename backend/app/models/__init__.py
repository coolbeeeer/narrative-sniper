from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class SourceRef(BaseModel):
    platform: str
    handle: str
    url: str
    timestamp: str
    engagement: int = 0


class Narrative(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    description: str
    confidence: float
    cluster_size: int
    top_tokens: list[str] = []
    sources: list[SourceRef] = []
    # Exact mint propagated from launch/social items so the signal engine
    # never has to guess which token a symbol refers to.
    token_mint: Optional[str] = None
    token_symbol: Optional[str] = None
    token_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NarrativeCluster(BaseModel):
    id: str
    narrative_id: str
    centroid: list[float]
    items: list[dict] = []


class Token(BaseModel):
    address: str
    symbol: str
    name: str
    decimals: int = 9
    price_usd: float = 0.0
    volume_24h: float = 0.0
    liquidity_usd: float = 0.0
    market_cap: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str
    token_symbol: str
    token_name: str
    entry_price: float
    current_price: float
    amount: float
    value_usd: float = 0.0
    pnl_usd: float = 0.0
    pnl_percent: float = 0.0
    narrative_id: str
    narrative_label: str
    entry_time: datetime = Field(default_factory=datetime.utcnow)
    status: str = "open"  # open, closed, partial
    tx_signature: Optional[str] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    realized_pnl: float = 0.0


class PnLDataPoint(BaseModel):
    timestamp: datetime
    total_value: float
    realized_pnl: float
    unrealized_pnl: float