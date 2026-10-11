from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import settings
from app.ingestion.manager import IngestionManager
from app.ingestion.j7 import J7Ingestion
from app.ingestion.launches import LaunchIngestion
from app.ingestion.volume import VolumeWatcher
from app.intelligence.pipeline import IntelligencePipeline
from app.execution.engine import ExecutionEngine
from app.paper_trading.engine import PaperTradingEngine
from app.signals.engine import SignalEngine
from app.live.wallet import BotWallet
from app.live.jupiter import JupiterClient
from app.live.engine import LiveTradingEngine


logger = structlog.get_logger()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected", total=len(self.active_connections))

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()
ingestion_manager: IngestionManager | None = None
intelligence_pipeline: IntelligencePipeline | None = None
execution_engine: ExecutionEngine | None = None
paper_trading_engine: PaperTradingEngine | None = None
signal_engine: SignalEngine | None = None
bot_wallet: BotWallet | None = None
live_trading_engine: LiveTradingEngine | None = None
j7_ingestion: J7Ingestion | None = None
launch_ingestion: LaunchIngestion | None = None
volume_watcher: VolumeWatcher | None = None


async def _broadcast_event(event: dict):
    await manager.broadcast({"channel": "signals", "event": event})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ingestion_manager, intelligence_pipeline, execution_engine, paper_trading_engine, signal_engine, j7_ingestion, launch_ingestion, volume_watcher, bot_wallet, live_trading_engine

    logger.info("Starting Narrative Sniper backend")

    # Initialize components
    intelligence_pipeline = IntelligencePipeline()
    await intelligence_pipeline.initialize()

    execution_engine = ExecutionEngine()
    await execution_engine.initialize()

    paper_trading_engine = PaperTradingEngine()
    await paper_trading_engine.initialize()
    paper_trading_engine.set_execution_engine(execution_engine)

    # Live trading: the bot wallet and live engine exist only when a
    # wallet key is configured. A malformed key must never take the app
    # down — log it loudly and carry on in paper mode.
    bot_wallet = None
    live_trading_engine = None
    try:
        bot_wallet = BotWallet.load()
    except ValueError as e:
        logger.error("Bot wallet key is invalid; live trading unavailable", error=str(e))
    if bot_wallet is not None:
        live_trading_engine = LiveTradingEngine(bot_wallet, JupiterClient(bot_wallet))
        await live_trading_engine.initialize()
        logger.info("Live trading engine ready", wallet=bot_wallet.address)

    # Signal engine: narrative -> trade decisions (paper, or live when the
    # live toggle is on and a wallet is configured)
    signal_engine = SignalEngine(
        paper_trading_engine, on_event=_broadcast_event, live_trading=live_trading_engine,
    )
    intelligence_pipeline.on_narrative(signal_engine.evaluate)
    await signal_engine.start()

    ingestion_manager = IngestionManager(
        intelligence_pipeline=intelligence_pipeline,
        execution_engine=execution_engine,
        paper_trading_engine=paper_trading_engine,
    )
    await ingestion_manager.start()

    # J7 X stream ingestion
    j7_ingestion = J7Ingestion(intelligence_pipeline)
    await j7_ingestion.start()

    # New-launch ingestion: fresh tokens from RugCheck + DexScreener feed the
    # pipeline with exact mints so the signal engine never guesses by symbol.
    launch_ingestion = LaunchIngestion(intelligence_pipeline)
    await launch_ingestion.start()

    # Volume watcher: catches silent buying surges on the tracked launches
    # (trading activity with no social posts behind it).
    volume_watcher = VolumeWatcher(intelligence_pipeline, launch_ingestion)
    await volume_watcher.start()

    logger.info("All components initialized")

    yield

    logger.info("Shutting down Narrative Sniper backend")

    if j7_ingestion:
        await j7_ingestion.stop()

    if volume_watcher:
        await volume_watcher.stop()

    if launch_ingestion:
        await launch_ingestion.stop()

    if signal_engine:
        await signal_engine.stop()

    if ingestion_manager:
        await ingestion_manager.stop()

    if intelligence_pipeline:
        await intelligence_pipeline.shutdown()

    if execution_engine:
        await execution_engine.shutdown()

    if paper_trading_engine:
        await paper_trading_engine.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            logger.debug("WebSocket message received", data=data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def get_manager() -> ConnectionManager:
    return manager


def get_ingestion_manager() -> IngestionManager:
    if ingestion_manager is None:
        raise RuntimeError("Ingestion manager not initialized")
    return ingestion_manager


def get_intelligence_pipeline() -> IntelligencePipeline:
    if intelligence_pipeline is None:
        raise RuntimeError("Intelligence pipeline not initialized")
    return intelligence_pipeline


def get_execution_engine() -> ExecutionEngine:
    if execution_engine is None:
        raise RuntimeError("Execution engine not initialized")
    return execution_engine


def get_paper_trading_engine() -> PaperTradingEngine:
    if paper_trading_engine is None:
        raise RuntimeError("Paper trading engine not initialized")
    return paper_trading_engine


def get_signal_engine() -> SignalEngine:
    if signal_engine is None:
        raise RuntimeError("Signal engine not initialized")
    return signal_engine


def get_j7_ingestion() -> J7Ingestion:
    if j7_ingestion is None:
        raise RuntimeError("J7 ingestion not initialized")
    return j7_ingestion


def get_launch_ingestion() -> LaunchIngestion:
    if launch_ingestion is None:
        raise RuntimeError("Launch ingestion not initialized")
    return launch_ingestion


def get_volume_watcher() -> VolumeWatcher:
    if volume_watcher is None:
        raise RuntimeError("Volume watcher not initialized")
    return volume_watcher


def get_bot_wallet() -> BotWallet | None:
    """The configured bot wallet, or None when no key is set. Callers
    (status endpoint, config guards) handle None explicitly."""
    return bot_wallet


def get_live_trading_engine() -> LiveTradingEngine | None:
    """The live engine, or None when no bot wallet is configured."""
    return live_trading_engine


# Imported after the getter functions to avoid a circular import:
# app.api imports the getters from this module.
from app.api import router as api_router  # noqa: E402

app.include_router(api_router, prefix="/api")