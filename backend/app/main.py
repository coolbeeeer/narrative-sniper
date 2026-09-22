from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import settings
from app.api import router as api_router
from app.ingestion.manager import IngestionManager
from app.intelligence.pipeline import IntelligencePipeline
from app.execution.engine import ExecutionEngine
from app.paper_trading.engine import PaperTradingEngine


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ingestion_manager, intelligence_pipeline, execution_engine, paper_trading_engine

    logger.info("Starting Narrative Sniper backend")

    # Initialize components
    intelligence_pipeline = IntelligencePipeline()
    await intelligence_pipeline.initialize()

    execution_engine = ExecutionEngine()
    await execution_engine.initialize()

    paper_trading_engine = PaperTradingEngine()
    await paper_trading_engine.initialize()

    ingestion_manager = IngestionManager(
        intelligence_pipeline=intelligence_pipeline,
        execution_engine=execution_engine,
        paper_trading_engine=paper_trading_engine,
    )
    await ingestion_manager.start()

    logger.info("All components initialized")

    yield

    logger.info("Shutting down Narrative Sniper backend")

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

app.include_router(api_router, prefix="/api")


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