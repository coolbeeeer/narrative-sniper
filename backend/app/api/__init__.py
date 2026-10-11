from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.main import (
    get_manager,
    get_ingestion_manager,
    get_intelligence_pipeline,
    get_execution_engine,
    get_paper_trading_engine,
    get_launch_ingestion,
)
from app.ingestion.manager import IngestionManager
from app.intelligence.pipeline import IntelligencePipeline
from app.execution.engine import ExecutionEngine
from app.paper_trading.engine import PaperTradingEngine
from app.core.config import settings


router = APIRouter()


class NarrativeResponse(BaseModel):
    id: str
    label: str
    description: str
    confidence: float
    cluster_size: int
    top_tokens: list[str]
    sources: list[dict]
    created_at: datetime
    updated_at: datetime


class PositionResponse(BaseModel):
    id: str
    token_address: str
    token_symbol: str
    token_name: str
    entry_price: float
    current_price: float
    amount: float
    value_usd: float
    pnl_usd: float
    pnl_percent: float
    narrative_id: str
    narrative_label: str
    entry_time: datetime
    status: str
    tx_signature: Optional[str] = None


class PnLDataPoint(BaseModel):
    timestamp: datetime
    total_value: float
    realized_pnl: float
    unrealized_pnl: float


class LiveStatusResponse(BaseModel):
    is_connected: bool
    last_update: datetime
    ingestion_rate: float
    queue_depth: int
    active_narratives: int
    open_positions: int
    paper_trading: bool


class LaunchStatusResponse(BaseModel):
    enabled: bool
    running: bool
    last_poll: Optional[str] = None
    launches_seen: int
    launches_emitted: int


class ConfigResponse(BaseModel):
    paper_trading: bool
    max_position_size_usd: float
    max_daily_loss_usd: float
    slippage_bps: int
    priority_fee_lamports: int
    narrative_confidence_threshold: float
    # Signal engine (narrative -> trade decisions)
    signal_enabled: bool
    signal_confidence_threshold: float
    signal_min_cluster_size: int
    signal_position_size_usd: float
    signal_max_open_positions: int
    signal_cooldown_hours: int
    signal_take_profit_pct: float
    signal_stop_loss_pct: float


class ConfigUpdate(BaseModel):
    paper_trading: Optional[bool] = None
    max_position_size_usd: Optional[float] = None
    max_daily_loss_usd: Optional[float] = None
    slippage_bps: Optional[int] = None
    priority_fee_lamports: Optional[int] = None
    narrative_confidence_threshold: Optional[float] = None
    # Signal engine (narrative -> trade decisions)
    signal_enabled: Optional[bool] = None
    signal_confidence_threshold: Optional[float] = None
    signal_min_cluster_size: Optional[int] = None
    signal_position_size_usd: Optional[float] = None
    signal_max_open_positions: Optional[int] = None
    signal_cooldown_hours: Optional[int] = None
    signal_take_profit_pct: Optional[float] = None
    signal_stop_loss_pct: Optional[float] = None


@router.get("/narratives", response_model=list[NarrativeResponse])
async def get_narratives(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    pipeline: IntelligencePipeline = Depends(get_intelligence_pipeline),
):
    narratives = pipeline.get_narratives(
        page=page, page_size=page_size, min_confidence=min_confidence
    )
    return narratives


@router.get("/narratives/{narrative_id}", response_model=NarrativeResponse)
async def get_narrative(
    narrative_id: str,
    pipeline: IntelligencePipeline = Depends(get_intelligence_pipeline),
):
    narrative = pipeline.get_narrative(narrative_id)
    if not narrative:
        raise HTTPException(status_code=404, detail="Narrative not found")
    return narrative


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(
    status: Optional[str] = Query(None),
    narrative_id: Optional[str] = Query(None),
    paper_trading: PaperTradingEngine = Depends(get_paper_trading_engine),
):
    positions = await paper_trading.get_positions(status=status, narrative_id=narrative_id)
    return positions


@router.get("/positions/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: str,
    paper_trading: PaperTradingEngine = Depends(get_paper_trading_engine),
):
    position = await paper_trading.get_position(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@router.get("/pnl/history", response_model=list[PnLDataPoint])
async def get_pnl_history(
    range: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    paper_trading: PaperTradingEngine = Depends(get_paper_trading_engine),
):
    history = await paper_trading.get_pnl_history(range)
    return history


@router.get("/status/live", response_model=LiveStatusResponse)
async def get_live_status(
    ingestion: IngestionManager = Depends(get_ingestion_manager),
    paper_trading: PaperTradingEngine = Depends(get_paper_trading_engine),
):
    return LiveStatusResponse(
        is_connected=ingestion.is_healthy(),
        last_update=datetime.utcnow(),
        ingestion_rate=ingestion.get_ingestion_rate(),
        queue_depth=ingestion.get_queue_depth(),
        active_narratives=ingestion.get_active_narratives_count(),
        open_positions=await paper_trading.get_open_positions_count(),
        paper_trading=settings.PAPER_TRADING,
    )


@router.get("/launches/status", response_model=LaunchStatusResponse)
async def get_launches_status():
    try:
        st = get_launch_ingestion().get_status()
        return LaunchStatusResponse(
            enabled=st["enabled"],
            running=st["running"],
            last_poll=st.get("last_poll"),
            launches_seen=st["tracked_mints"],
            launches_emitted=st["received_count"],
        )
    except RuntimeError:
        return LaunchStatusResponse(enabled=False, running=False, launches_seen=0, launches_emitted=0)


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    return ConfigResponse(
        paper_trading=settings.PAPER_TRADING,
        max_position_size_usd=settings.MAX_POSITION_SIZE_USD,
        max_daily_loss_usd=settings.MAX_DAILY_LOSS_USD,
        slippage_bps=settings.SLIPPAGE_BPS,
        priority_fee_lamports=settings.PRIORITY_FEE_LAMPORTS,
        narrative_confidence_threshold=settings.NARRATIVE_CONFIDENCE_THRESHOLD,
        signal_enabled=settings.SIGNAL_ENABLED,
        signal_confidence_threshold=settings.SIGNAL_CONFIDENCE_THRESHOLD,
        signal_min_cluster_size=settings.SIGNAL_MIN_CLUSTER_SIZE,
        signal_position_size_usd=settings.SIGNAL_POSITION_SIZE_USD,
        signal_max_open_positions=settings.SIGNAL_MAX_OPEN_POSITIONS,
        signal_cooldown_hours=settings.SIGNAL_COOLDOWN_HOURS,
        signal_take_profit_pct=settings.SIGNAL_TAKE_PROFIT_PCT,
        signal_stop_loss_pct=settings.SIGNAL_STOP_LOSS_PCT,
    )


@router.patch("/config", response_model=ConfigResponse)
async def update_config(
    config: ConfigUpdate,
    ingestion: IngestionManager = Depends(get_ingestion_manager),
):
    # Update runtime config
    if config.paper_trading is not None:
        settings.PAPER_TRADING = config.paper_trading
    if config.max_position_size_usd is not None:
        settings.MAX_POSITION_SIZE_USD = config.max_position_size_usd
    if config.max_daily_loss_usd is not None:
        settings.MAX_DAILY_LOSS_USD = config.max_daily_loss_usd
    if config.slippage_bps is not None:
        settings.SLIPPAGE_BPS = config.slippage_bps
    if config.priority_fee_lamports is not None:
        settings.PRIORITY_FEE_LAMPORTS = config.priority_fee_lamports
    if config.narrative_confidence_threshold is not None:
        settings.NARRATIVE_CONFIDENCE_THRESHOLD = config.narrative_confidence_threshold
    # Signal engine settings apply immediately: the signal engine reads
    # settings.SIGNAL_* live on every narrative evaluation (no restart needed).
    if config.signal_enabled is not None:
        settings.SIGNAL_ENABLED = config.signal_enabled
    if config.signal_confidence_threshold is not None:
        settings.SIGNAL_CONFIDENCE_THRESHOLD = config.signal_confidence_threshold
    if config.signal_min_cluster_size is not None:
        settings.SIGNAL_MIN_CLUSTER_SIZE = config.signal_min_cluster_size
    if config.signal_position_size_usd is not None:
        if config.signal_position_size_usd <= 0:
            raise HTTPException(status_code=422, detail="signal_position_size_usd must be positive")
        settings.SIGNAL_POSITION_SIZE_USD = config.signal_position_size_usd
    if config.signal_max_open_positions is not None:
        settings.SIGNAL_MAX_OPEN_POSITIONS = config.signal_max_open_positions
    if config.signal_cooldown_hours is not None:
        settings.SIGNAL_COOLDOWN_HOURS = config.signal_cooldown_hours
    if config.signal_take_profit_pct is not None:
        settings.SIGNAL_TAKE_PROFIT_PCT = config.signal_take_profit_pct
    if config.signal_stop_loss_pct is not None:
        settings.SIGNAL_STOP_LOSS_PCT = config.signal_stop_loss_pct

    await ingestion.reload_config()

    return ConfigResponse(
        paper_trading=settings.PAPER_TRADING,
        max_position_size_usd=settings.MAX_POSITION_SIZE_USD,
        max_daily_loss_usd=settings.MAX_DAILY_LOSS_USD,
        slippage_bps=settings.SLIPPAGE_BPS,
        priority_fee_lamports=settings.PRIORITY_FEE_LAMPORTS,
        narrative_confidence_threshold=settings.NARRATIVE_CONFIDENCE_THRESHOLD,
        signal_enabled=settings.SIGNAL_ENABLED,
        signal_confidence_threshold=settings.SIGNAL_CONFIDENCE_THRESHOLD,
        signal_min_cluster_size=settings.SIGNAL_MIN_CLUSTER_SIZE,
        signal_position_size_usd=settings.SIGNAL_POSITION_SIZE_USD,
        signal_max_open_positions=settings.SIGNAL_MAX_OPEN_POSITIONS,
        signal_cooldown_hours=settings.SIGNAL_COOLDOWN_HOURS,
        signal_take_profit_pct=settings.SIGNAL_TAKE_PROFIT_PCT,
        signal_stop_loss_pct=settings.SIGNAL_STOP_LOSS_PCT,
    )


@router.post("/ingestion/start")
async def start_ingestion(ingestion: IngestionManager = Depends(get_ingestion_manager)):
    await ingestion.start()
    return {"status": "started"}


@router.post("/ingestion/stop")
async def stop_ingestion(ingestion: IngestionManager = Depends(get_ingestion_manager)):
    await ingestion.stop()
    return {"status": "stopped"}


@router.get("/ingestion/status")
async def ingestion_status(ingestion: IngestionManager = Depends(get_ingestion_manager)):
    return {
        "running": ingestion.is_running(),
        "sources": ingestion.get_source_status(),
        "rate": ingestion.get_ingestion_rate(),
        "queue_depth": ingestion.get_queue_depth(),
    }