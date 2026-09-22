import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import structlog

from app.core.config import settings
from app.intelligence.pipeline import IntelligencePipeline
from app.execution.engine import ExecutionEngine
from app.paper_trading.engine import PaperTradingEngine


logger = structlog.get_logger()


@dataclass
class IngestionSource:
    name: str
    enabled: bool
    last_fetch: Optional[datetime] = None
    items_fetched: int = 0
    errors: int = 0
    is_healthy: bool = True


class BaseIngestionSource(ABC):
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.last_fetch: Optional[datetime] = None
        self.items_fetched = 0
        self.errors = 0
        self.is_healthy = True

    @abstractmethod
    async def fetch(self) -> list[dict]:
        pass

    @abstractmethod
    async def start_streaming(self):
        pass

    @abstractmethod
    async def stop_streaming(self):
        pass

    def get_status(self) -> IngestionSource:
        return IngestionSource(
            name=self.name,
            enabled=self.enabled,
            last_fetch=self.last_fetch,
            items_fetched=self.items_fetched,
            errors=self.errors,
            is_healthy=self.is_healthy,
        )


class TwitterIngestion(BaseIngestionSource):
    def __init__(self):
        super().__init__("twitter")
        self.client = None

    async def fetch(self) -> list[dict]:
        if not settings.TWITTER_BEARER_TOKEN:
            return []
        # Implement Twitter API v2 fetch
        return []

    async def start_streaming(self):
        # Implement Twitter streaming
        pass

    async def stop_streaming(self):
        pass


class TelegramIngestion(BaseIngestionSource):
    def __init__(self):
        super().__init__("telegram")
        self.client = None

    async def fetch(self) -> list[dict]:
        if not settings.TELEGRAM_BOT_TOKEN:
            return []
        # Implement Telegram fetch
        return []

    async def start_streaming(self):
        # Implement Telegram streaming
        pass

    async def stop_streaming(self):
        pass


class DiscordIngestion(BaseIngestionSource):
    def __init__(self):
        super().__init__("discord")
        self.client = None

    async def fetch(self) -> list[dict]:
        if not settings.DISCORD_BOT_TOKEN:
            return []
        # Implement Discord fetch
        return []

    async def start_streaming(self):
        # Implement Discord streaming
        pass

    async def stop_streaming(self):
        pass


class HeliusIngestion(BaseIngestionSource):
    def __init__(self):
        super().__init__("helius")
        self.ws = None

    async def fetch(self) -> list[dict]:
        if not settings.HELIUS_API_KEY:
            return []
        # Implement Helius REST fetch for new pools
        return []

    async def start_streaming(self):
        # Implement Helius WebSocket streaming for new pools
        pass

    async def stop_streaming(self):
        if self.ws:
            await self.ws.close()


class IngestionManager:
    def __init__(
        self,
        intelligence_pipeline: IntelligencePipeline,
        execution_engine: ExecutionEngine,
        paper_trading_engine: PaperTradingEngine,
    ):
        self.intelligence_pipeline = intelligence_pipeline
        self.execution_engine = execution_engine
        self.paper_trading_engine = paper_trading_engine

        self.sources: dict[str, BaseIngestionSource] = {
            "twitter": TwitterIngestion(),
            "telegram": TelegramIngestion(),
            "discord": DiscordIngestion(),
            "helius": HeliusIngestion(),
        }

        self.running = False
        self.ingestion_task: Optional[asyncio.Task] = None
        self.total_fetched = 0
        self.fetch_times: list[float] = []
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=10000)

    async def start(self):
        if self.running:
            return

        self.running = True

        # Start streaming sources
        for source in self.sources.values():
            if source.enabled:
                try:
                    await source.start_streaming()
                except Exception as e:
                    logger.error("Failed to start source", source=source.name, error=str(e))
                    source.is_healthy = False

        # Start ingestion loop
        self.ingestion_task = asyncio.create_task(self._ingestion_loop())
        logger.info("Ingestion manager started")

    async def stop(self):
        self.running = False

        if self.ingestion_task:
            self.ingestion_task.cancel()
            try:
                await self.ingestion_task
            except asyncio.CancelledError:
                pass

        for source in self.sources.values():
            try:
                await source.stop_streaming()
            except Exception as e:
                logger.error("Failed to stop source", source=source.name, error=str(e))

        logger.info("Ingestion manager stopped")

    async def _ingestion_loop(self):
        while self.running:
            try:
                await self._fetch_all_sources()
                await asyncio.sleep(settings.INGESTION_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Ingestion loop error", error=str(e))
                await asyncio.sleep(5)

    async def _fetch_all_sources(self):
        tasks = []
        for source in self.sources.values():
            if source.enabled and source.is_healthy:
                tasks.append(self._fetch_source(source))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for source, result in zip([s for s in self.sources.values() if s.enabled and s.is_healthy], results):
                if isinstance(result, Exception):
                    source.errors += 1
                    source.is_healthy = source.errors < 5
                    logger.error("Source fetch failed", source=source.name, error=str(result))
                elif isinstance(result, list):
                    source.items_fetched += len(result)
                    self.total_fetched += len(result)
                    for item in result:
                        await self.queue.put(item)

    async def _fetch_source(self, source: BaseIngestionSource) -> list[dict]:
        start = datetime.utcnow()
        try:
            items = await source.fetch()
            source.last_fetch = datetime.utcnow()
            self.fetch_times.append((datetime.utcnow() - start).total_seconds())
            if len(self.fetch_times) > 100:
                self.fetch_times = self.fetch_times[-100:]
            return items
        except Exception as e:
            raise e

    async def process_queue(self):
        while self.running:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await self.intelligence_pipeline.process(item)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Queue processing error", error=str(e))

    def is_running(self) -> bool:
        return self.running

    def is_healthy(self) -> bool:
        return any(s.is_healthy for s in self.sources.values() if s.enabled)

    def get_ingestion_rate(self) -> float:
        if not self.fetch_times:
            return 0.0
        avg_time = sum(self.fetch_times) / len(self.fetch_times)
        return 60.0 / avg_time if avg_time > 0 else 0.0

    def get_queue_depth(self) -> int:
        return self.queue.qsize()

    def get_active_narratives_count(self) -> int:
        return self.intelligence_pipeline.get_active_narratives_count()

    def get_source_status(self) -> list[IngestionSource]:
        return [source.get_status() for source in self.sources.values()]

    async def reload_config(self):
        for source in self.sources.values():
            # Re-enable/disable based on config
            pass