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


class ConfigResponse(BaseModel):
    paper_trading: bool
    max_position_size_usd: float
    max_daily_loss_usd: float
    slippage_bps: int
    priority_fee_lamports: int
    narrative_confidence_threshold: float


class ConfigUpdate(BaseModel):
    paper_trading: Optional[bool] = None
    max_position_size_usd: Optional[float] = None
    max_daily_loss_usd: Optional[float] = None
    slippage_bps: Optional[int] = None
    priority_fee_lamports: Optional[int] = None
    narrative_confidence_threshold: Optional[float] = None


@router.get("/narratives", response_model=list[NarrativeResponse])
async def get_narratives(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    pipeline: IntelligencePipeline = Depends(get_intelligence_pipeline),
):
    narratives = await pipeline.get_narratives(
        page=page, page_size=page_size, min_confidence=min_confidence
    )
    return narratives


@router.get("/narratives/{narrative_id}", response_model=NarrativeResponse)
async def get_narrative(
    narrative_id: str,
    pipeline: IntelligencePipeline = Depends(get_intelligence_pipeline),
):
    narrative = await pipeline.get_narrative(narrative_id)
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


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    return ConfigResponse(
        paper_trading=settings.PAPER_TRADING,
        max_position_size_usd=settings.MAX_POSITION_SIZE_USD,
        max_daily_loss_usd=settings.MAX_DAILY_LOSS_USD,
        slippage_bps=settings.SLIPPAGE_BPS,
        priority_fee_lamports=settings.PRIORITY_FEE_LAMPORTS,
        narrative_confidence_threshold=settings.NARRATIVE_CONFIDENCE_THRESHOLD,
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

    await ingestion.reload_config()

    return ConfigResponse(
        paper_trading=settings.PAPER_TRADING,
        max_position_size_usd=settings.MAX_POSITION_SIZE_USD,
        max_daily_loss_usd=settings.MAX_DAILY_LOSS_USD,
        slippage_bps=settings.SLIPPAGE_BPS,
        priority_fee_lamports=settings.PRIORITY_FEE_LAMPORTS,
        narrative_confidence_threshold=settings.NARRATIVE_CONFIDENCE_THRESHOLD,
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