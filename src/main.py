"""
Narrative Sniper - Main Entry Point.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

import click
import structlog
from rich.console import Console
from rich.logging import RichHandler

from .config import load_settings, get_settings
from .ingestion.manager import IngestionManager, create_ingestion_manager
from .intelligence.detector import NarrativeDetector, create_detector
from .execution.sniper import Sniper, create_sniper
from .management.position_manager import PositionManager
from .paper.paper_trader import PaperTrader
from .dashboard.server import create_app

console = Console()


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure logging."""
    if log_format == "json":
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


class NarrativeSniperApp:
    """Main application class."""
    
    def __init__(self):
        self.settings = None
        self.detector: Optional[NarrativeDetector] = None
        self.sniper: Optional[Sniper] = None
        self.position_manager: Optional[PositionManager] = None
        self.paper_trader: Optional[PaperTrader] = None
        self.ingestion_manager: Optional[IngestionManager] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """Initialize all components."""
        self.settings = load_settings()
        setup_logging(self.settings.app.log_level, self.settings.app.log_format)
        
        logger = logging.getLogger(__name__)
        logger.info("Initializing Narrative Sniper...")
        
        # Initialize paper trader
        self.paper_trader = PaperTrader(
            starting_balance_usd=self.settings.paper_trading.starting_balance_usd,
            simulate_slippage=self.settings.paper_trading.simulate_slippage,
            simulate_price_impact=self.settings.paper_trading.simulate_price_impact,
            simulate_failures=self.settings.paper_trading.simulate_failures,
            failure_rate=self.settings.paper_trading.failure_rate,
            latency_ms=self.settings.paper_trading.latency_ms,
        )
        await self.paper_trader.initialize()
        
        # Initialize ingestion
        self.ingestion_manager = await create_ingestion_manager(self.settings.ingestion)
        
        # Initialize detector
        self.detector = await create_detector(
            self.settings.ingestion,
            self.settings.intelligence.detector,
        )
        
        # Initialize sniper
        from solders.keypair import Keypair
        wallet = None
        if self.settings.solana.wallet.private_key:
            try:
                wallet = Keypair.from_base58_string(self.settings.solana.wallet.private_key)
            except Exception as e:
                logger.warning(f"Failed to load wallet: {e}")
        
        self.sniper = await create_sniper(
            config=self.settings.execution.sniper,
            risk_config=self.settings.risk,
            wallet=wallet,
        )
        self.sniper.paper_trading = self.settings.execution.paper_trading
        
        # Initialize position manager
        self.position_manager = PositionManager(self.sniper)
        await self.position_manager.start()
        
        logger.info("Narrative Sniper initialized successfully")
    
    async def start(self) -> None:
        """Start the application."""
        self._running = True
        console.print("[green]Narrative Sniper started[/green]")
        console.print(f"Dashboard: http://{self.settings.dashboard.host}:{self.settings.dashboard.port}")
        console.print("Press Ctrl+C to stop")
        
        # Wait for shutdown signal
        await self._shutdown_event.wait()
    
    async def stop(self) -> None:
        """Stop the application."""
        self._running = False
        console.print("[yellow]Shutting down...[/yellow]")
        
        if self.position_manager:
            await self.position_manager.stop()
        if self.sniper:
            await self.sniper.stop()
        if self.detector:
            await self.detector.stop()
        if self.ingestion_manager:
            await self.ingestion_manager.stop()
        if self.paper_trader:
            await self.paper_trader.close()
        
        console.print("[green]Narrative Sniper stopped[/green]")
        self._shutdown_event.set()
    
    def handle_signal(self, signum, frame) -> None:
        """Handle shutdown signals."""
        console.print(f"\n[yellow]Received signal {signum}, shutting down...[/yellow]")
        asyncio.create_task(self.stop())


async def run_dashboard() -> None:
    """Run the FastAPI dashboard server."""
    import uvicorn
    
    settings = get_settings()
    app = create_app()
    
    config = uvicorn.Config(
        app,
        host=settings.dashboard.host,
        port=settings.dashboard.port,
        log_level=settings.app.log_level.lower(),
        reload=settings.app.environment == "development",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_full() -> None:
    """Run full application with dashboard."""
    app = NarrativeSniperApp()
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, app.handle_signal, sig, None)
    
    await app.initialize()
    
    # Run dashboard in background
    dashboard_task = asyncio.create_task(run_dashboard())
    
    # Run main app
    await app.start()
    
    # Cancel dashboard
    dashboard_task.cancel()
    try:
        await dashboard_task
    except asyncio.CancelledError:
        pass


@click.group()
def cli():
    """Narrative Sniper - AI-powered narrative detection and trading."""
    pass


@cli.command()
def dashboard():
    """Run only the dashboard server."""
    asyncio.run(run_dashboard())


@cli.command()
def full():
    """Run the full application (detector + sniper + dashboard)."""
    asyncio.run(run_full())


@cli.command()
def detector():
    """Run only the narrative detector."""
    async def run_detector():
        settings = load_settings()
        setup_logging(settings.app.log_level, settings.app.log_format)
        
        detector = await create_detector(settings.ingestion, settings.intelligence.detector)
        
        console.print("[green]Narrative Detector started[/green]")
        console.print("Press Ctrl+C to stop")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await detector.stop()
    
    asyncio.run(run_detector())


@cli.command()
def paper():
    """Run paper trading simulation."""
    async def run_paper():
        settings = load_settings()
        setup_logging(settings.app.log_level, settings.app.log_format)
        
        from .execution.sniper import Sniper
        from solders.keypair import Keypair
        
        wallet = None
        if settings.solana.wallet.private_key:
            try:
                wallet = Keypair.from_base58_string(settings.solana.wallet.private_key)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load wallet: {e}[/yellow]")
        
        sniper = await create_sniper(
            config=settings.execution.sniper,
            risk_config=settings.risk,
            wallet=wallet,
        )
        sniper.paper_trading = True
        
        console.print("[green]Paper Trading Mode started[/green]")
        console.print(f"Starting balance: ${settings.paper_trading.starting_balance_usd:.2f}")
        console.print("Press Ctrl+C to stop")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await sniper.stop()
            console.print(f"[green]Final balance: ${sniper._paper_balance:.2f}[/green]")
    
    asyncio.run(run_paper())


@cli.command()
def test():
    """Run tests."""
    import pytest
    sys.exit(pytest.main(["-v", "tests/"]))


if __name__ == "__main__":
    cli()