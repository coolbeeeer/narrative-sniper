import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from src.config import config
from src.dashboard.models import (
    NarrativeResponse, PositionResponse, TradeResponse,
    SystemStatusResponse, PerformanceResponse, HealthResponse,
    NarrativeStatus, PositionStatus, HealthStatus,
)
from src.dashboard.websocket import manager, handle_websocket, start_heartbeat
from src.token.dashboard_api import router as token_router, init_dashboard_state
from src.intelligence.detector import NarrativeDetector, DetectedNarrative
from src.management.position_manager import PositionManager, Position, PositionStatus as PMStatus
from src.management.portfolio import PortfolioManager, PortfolioSnapshot
from src.management.risk import RiskManager
from src.paper.paper_trader import PaperTrader
from src.utils.helpers import now_utc, format_sol


logger = structlog.get_logger()


_dashboard_state: Dict[str, Any] = {
    "narrative_detector": None,
    "position_manager": None,
    "portfolio_manager": None,
    "risk_manager": None,
    "paper_trader": None,
    "start_time": None,
}


def init_dashboard_services(
    narrative_detector: NarrativeDetector,
    position_manager: PositionManager,
    portfolio_manager: PortfolioManager,
    risk_manager: RiskManager,
    paper_trader: PaperTrader,
):
    global _dashboard_state
    _dashboard_state = {
        "narrative_detector": narrative_detector,
        "position_manager": position_manager,
        "portfolio_manager": portfolio_manager,
        "risk_manager": risk_manager,
        "paper_trader": paper_trader,
        "start_time": now_utc(),
    }
    init_dashboard_state(
        clawpump_client=None,
        tokenomics_engine=None,
        paper_trader=paper_trader,
        portfolio_manager=portfolio_manager,
        position_manager=position_manager,
        narrative_detector=narrative_detector,
    )


def create_app(
    dashboard_config: Any,
    narrative_detector: NarrativeDetector,
    position_manager: PositionManager,
    portfolio_manager: PortfolioManager,
    risk_manager: RiskManager,
    paper_trader: PaperTrader,
) -> FastAPI:
    init_dashboard_services(
        narrative_detector, position_manager, portfolio_manager, risk_manager, paper_trader
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        heartbeat_task = asyncio.create_task(start_heartbeat(30))
        yield
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    app = FastAPI(
        title="Narrative Sniper Dashboard API",
        description="Real-time dashboard for Solana narrative detection and auto-sniper system",
        version=config.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=dashboard_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(token_router)

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        state = _dashboard_state
        uptime = (now_utc() - state["start_time"]).total_seconds() if state["start_time"] else 0

        components = {
            "ingestion": "healthy" if state["narrative_detector"] and state["narrative_detector"].is_running else "down",
            "detection": "healthy" if state["narrative_detector"] and state["narrative_detector"].is_running else "down",
            "execution": "healthy" if state["position_manager"] else "down",
            "risk": "healthy" if state["risk_manager"] else "down",
            "paper_trading": "healthy" if state["paper_trader"] else "down",
            "database": "healthy",
        }

        overall = "healthy" if all(v == "healthy" for v in components.values()) else "degraded"

        return HealthResponse(
            status=overall,
            version=config.version,
            uptime_seconds=uptime,
            components=components,
        )

    @app.get("/status", response_model=SystemStatusResponse)
    async def system_status():
        state = _dashboard_state
        detector = state["narrative_detector"]
        position_mgr = state["position_manager"]

        return SystemStatusResponse(
            ingestion="healthy" if detector and detector.ingestion_manager and detector.ingestion_manager.is_running else "down",
            detection="healthy" if detector and detector.is_running else "down",
            execution="healthy" if position_mgr and position_mgr.is_running else "down",
            risk="healthy" if state["risk_manager"] else "down",
            paper_trading="healthy" if state["paper_trader"] else "down",
            database="healthy",
            last_update=now_utc(),
        )

    @app.get("/narratives", response_model=List[NarrativeResponse])
    async def get_narratives(
        status: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
    ):
        detector = _dashboard_state["narrative_detector"]
        if not detector:
            return []

        narratives = detector.get_active_narratives()
        result = []

        for nar in narratives[:limit]:
            if status and nar.status != status:
                continue

            result.append(NarrativeResponse(
                id=nar.id,
                narrative_id=nar.narrative_score.narrative_id,
                name=nar.narrative_score.narrative_name,
                score=nar.narrative_score.score,
                confidence=nar.narrative_score.confidence,
                volume=nar.narrative_score.volume,
                velocity=nar.narrative_score.velocity,
                sentiment=nar.narrative_score.sentiment,
                status=nar.status,
                created_at=nar.created_at,
                token_candidates=len(nar.token_candidates),
                top_keywords=nar.narrative_score.label.matched_keywords[:10],
            ))

        return result

    @app.get("/narratives/{narrative_id}", response_model=NarrativeResponse)
    async def get_narrative(narrative_id: str):
        detector = _dashboard_state["narrative_detector"]
        if not detector:
            raise HTTPException(status_code=404, detail="Narrative not found")

        narrative = detector.get_narrative_by_id(narrative_id)
        if not narrative:
            raise HTTPException(status_code=404, detail="Narrative not found")

        return NarrativeResponse(
            id=narrative.id,
            narrative_id=narrative.narrative_score.narrative_id,
            name=narrative.narrative_score.narrative_name,
            score=narrative.narrative_score.score,
            confidence=narrative.narrative_score.confidence,
            volume=narrative.narrative_score.volume,
            velocity=narrative.narrative_score.velocity,
            sentiment=narrative.narrative_score.sentiment,
            status=narrative.status,
            created_at=narrative.created_at,
            token_candidates=len(narrative.token_candidates),
            top_keywords=narrative.narrative_score.label.matched_keywords[:10],
        )

    @app.get("/positions", response_model=List[PositionResponse])
    async def get_positions(
        status: Optional[str] = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ):
        position_mgr = _dashboard_state["position_manager"]
        paper_trader = _dashboard_state["paper_trader"]

        if not position_mgr:
            return []

        positions = position_mgr.get_open_positions()
        result = []

        for pos in positions[:limit]:
            if status and pos.status.value != status:
                continue

            current_price = await paper_trader.get_price(pos.mint) if paper_trader else pos.current_price

            result.append(PositionResponse(
                id=pos.id,
                mint=pos.mint,
                symbol=pos.symbol,
                name=pos.name,
                entry_price=pos.entry_price,
                current_price=current_price or pos.current_price,
                amount_in_sol=pos.amount_in_sol,
                amount_out_tokens=pos.amount_out_tokens,
                remaining_tokens=pos.remaining_tokens,
                pnl_sol=pos.pnl_sol,
                pnl_percentage=pos.pnl_percentage,
                status=pos.status.value,
                opened_at=pos.opened_at,
                narrative_id=pos.narrative_id,
                stop_loss_price=pos.stop_loss_price,
                trailing_stop_price=pos.trailing_stop_price,
            ))

        return result

    @app.get("/positions/{position_id}", response_model=PositionResponse)
    async def get_position(position_id: str):
        position_mgr = _dashboard_state["position_manager"]
        paper_trader = _dashboard_state["paper_trader"]

        if not position_mgr:
            raise HTTPException(status_code=404, detail="Position not found")

        pos = position_mgr.get_position(position_id)
        if not pos:
            raise HTTPException(status_code=404, detail="Position not found")

        current_price = await paper_trader.get_price(pos.mint) if paper_trader else pos.current_price

        return PositionResponse(
            id=pos.id,
            mint=pos.mint,
            symbol=pos.symbol,
            name=pos.name,
            entry_price=pos.entry_price,
            current_price=current_price or pos.current_price,
            amount_in_sol=pos.amount_in_sol,
            amount_out_tokens=pos.amount_out_tokens,
            remaining_tokens=pos.remaining_tokens,
            pnl_sol=pos.pnl_sol,
            pnl_percentage=pos.pnl_percentage,
            status=pos.status.value,
            opened_at=pos.opened_at,
            narrative_id=pos.narrative_id,
            stop_loss_price=pos.stop_loss_price,
            trailing_stop_price=pos.trailing_stop_price,
        )

    @app.get("/trades", response_model=List[TradeResponse])
    async def get_trades(
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        portfolio_mgr = _dashboard_state["portfolio_manager"]
        if not portfolio_mgr:
            return []

        history = portfolio_mgr.get_trade_history(limit=limit + offset)
        trades = history[offset:offset + limit]

        return [
            TradeResponse(
                id=t.get("order_id", ""),
                position_id=t.get("position_id", ""),
                mint=t.get("mint", ""),
                symbol=t.get("symbol", ""),
                side=t.get("side", ""),
                price=t.get("price", 0),
                amount_sol=t.get("amount_sol", 0),
                amount_tokens=t.get("amount_tokens", 0),
                fees_sol=t.get("fees_paid", 0),
                timestamp=datetime.fromisoformat(t["timestamp"]) if "timestamp" in t else now_utc(),
                pnl_sol=t.get("pnl_sol", 0),
            )
            for t in trades
        ]

    @app.get("/performance", response_model=PerformanceResponse)
    async def get_performance():
        portfolio_mgr = _dashboard_state["portfolio_manager"]
        paper_trader = _dashboard_state["paper_trader"]

        if not portfolio_mgr:
            raise HTTPException(status_code=503, detail="Portfolio manager not initialized")

        metrics = portfolio_mgr.get_performance_metrics()
        snapshot = portfolio_mgr.get_current_snapshot()

        daily_pnl = portfolio_mgr.get_daily_pnl(30)
        equity_curve = [s.total_value_sol for s in portfolio_mgr.get_snapshots(100)]

        return PerformanceResponse(
            total_value_sol=snapshot.total_value_sol if snapshot else 0,
            total_pnl_sol=metrics.total_pnl_sol if hasattr(metrics, 'total_pnl_sol') else 0,
            total_pnl_percentage=metrics.total_pnl_percentage if hasattr(metrics, 'total_pnl_percentage') else 0,
            win_rate=metrics.win_rate,
            open_positions=metrics.open_positions if hasattr(metrics, 'open_positions') else 0,
            closed_positions=metrics.closed_positions if hasattr(metrics, 'closed_positions') else 0,
            max_drawdown_percentage=metrics.max_drawdown_percentage,
            sharpe_ratio=metrics.sharpe_ratio,
            daily_pnl=daily_pnl,
            equity_curve=equity_curve,
        )

    @app.get("/portfolio/summary")
    async def get_portfolio_summary():
        portfolio_mgr = _dashboard_state["portfolio_manager"]
        if not portfolio_mgr:
            raise HTTPException(status_code=503, detail="Portfolio manager not initialized")

        return portfolio_mgr.get_positions_summary()

    @app.get("/risk/status")
    async def get_risk_status():
        risk_mgr = _dashboard_state["risk_manager"]
        if not risk_mgr:
            raise HTTPException(status_code=503, detail="Risk manager not initialized")

        return risk_mgr.get_risk_status()

    @app.post("/risk/reset-emergency")
    async def reset_emergency_stop():
        risk_mgr = _dashboard_state["risk_manager"]
        if not risk_mgr:
            raise HTTPException(status_code=503, detail="Risk manager not initialized")

        risk_mgr.reset_emergency_stop()
        return {"success": True, "message": "Emergency stop reset"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        client_id = f"client_{id(websocket)}"
        await handle_websocket(websocket, client_id)

    @app.get("/config")
    async def get_config():
        return {
            "execution": {
                "max_position_size_sol": config.execution.max_position_size_sol,
                "max_positions": config.execution.max_positions,
                "min_liquidity_sol": config.execution.min_liquidity_sol,
                "max_buy_tax": config.execution.max_buy_tax,
                "max_sell_tax": config.execution.max_sell_tax,
                "min_narrative_score": config.execution.min_narrative_score,
                "min_dev_score": config.execution.min_dev_score,
                "stop_loss_percentage": config.execution.stop_loss_percentage,
                "trailing_stop_percentage": config.execution.trailing_stop_percentage,
                "max_hold_time_hours": config.execution.max_hold_time_hours,
            },
            "risk": {
                "max_daily_loss_sol": config.risk.max_daily_loss_sol,
                "max_daily_loss_percentage": config.risk.max_daily_loss_percentage,
                "max_drawdown_percentage": config.risk.max_drawdown_percentage,
                "max_position_percentage": config.risk.max_position_percentage,
                "max_concurrent_snipes": config.risk.max_concurrent_snipes,
            },
            "detection": {
                "min_tweets_for_cluster": config.detection.min_tweets_for_cluster,
                "min_cluster_size": config.detection.min_cluster_size,
                "similarity_threshold": config.detection.similarity_threshold,
                "narrative_score_threshold": config.detection.narrative_score_threshold,
                "lookback_hours": config.detection.lookback_hours,
            },
            "paper_trading": {
                "enabled": config.paper_trading.enabled,
                "starting_balance_sol": config.paper_trading.starting_balance_sol,
                "starting_balance_usdc": config.paper_trading.starting_balance_usdc,
                "fee_bps": config.paper_trading.fee_bps,
                "slippage_bps": config.paper_trading.slippage_bps,
            },
        }

    return app


async def run_dashboard_server(
    dashboard_config: Any,
    narrative_detector: NarrativeDetector,
    position_manager: PositionManager,
    portfolio_manager: PortfolioManager,
    risk_manager: RiskManager,
    paper_trader: PaperTrader,
):
    app = create_app(
        dashboard_config,
        narrative_detector,
        position_manager,
        portfolio_manager,
        risk_manager,
        paper_trader,
    )

    server_config = uvicorn.Config(
        app=app,
        host=dashboard_config.host,
        port=dashboard_config.port,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(server_config)
    await server.serve()