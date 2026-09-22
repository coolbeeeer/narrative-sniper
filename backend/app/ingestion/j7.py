"""J7Tracker X stream ingestion (unofficial socket.io feed).

Connects with the account's JWT session token, receives live tweets plus
J7's own AI ticker predictions, and feeds them into the intelligence
pipeline as X posts. Reconnects with backoff; the JWT expires (~15 days)
and must be refreshed in the .env when auth starts failing.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
import socketio
import structlog

from app.core.config import settings


logger = structlog.get_logger()

J7_SERVERS = ["https://nyc.j7tracker.io", "https://ash.j7tracker.io"]


def _to_iso(ts) -> str:
    try:
        ms = int(ts)
        if ms > 1e12:
            ms = ms // 1000
        # values look like ms already in the 1.7e12 range
        dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


class J7Ingestion:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.token = settings.J7_SESSION_TOKEN
        self.sio: Optional[socketio.AsyncClient] = None
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.server_idx = 0
        self.received = 0

    async def start(self):
        if not settings.J7_ENABLED or not self.token:
            logger.warning("J7 ingestion disabled (no token or J7_ENABLED=false)")
            return
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info("J7 ingestion started")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.sio:
            try:
                await self.sio.disconnect()
            except Exception:
                pass
        logger.info("J7 ingestion stopped", received=self.received)

    async def _run_loop(self):
        backoff = 5
        while self.running:
            try:
                await self._connect_once()
                backoff = 5  # reset on clean disconnect
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("J7 connection failed", error=str(e), backoff=backoff)
            if self.running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)
                self.server_idx += 1  # try the other region next

    async def _connect_once(self):
        server = J7_SERVERS[self.server_idx % len(J7_SERVERS)]
        sio = socketio.AsyncClient(reconnection=False)
        self.sio = sio

        @sio.event
        async def connect():
            logger.info("J7 connected", server=server)
            await sio.emit("user_connected", self.token)

        @sio.on("tweet")
        async def on_tweet(data):
            await self._handle_tweet(data)

        @sio.on("tweet_update")
        async def on_update(data):
            await self._handle_tweet(data)

        @sio.on("initialTweets")
        async def on_initial(data):
            items = data if isinstance(data, list) else []
            logger.info("J7 backfill", count=len(items))
            for tw in items:
                await self._handle_tweet(tw)

        @sio.on("ai_suggestion")
        async def on_ai(data):
            await self._handle_ai_suggestion(data)

        @sio.on("auth_error")
        async def on_auth_error(data):
            logger.error("J7 auth rejected the token (refresh J7_SESSION_TOKEN)", data=str(data)[:200])
            self.running = False  # don't hammer with a dead token

        @sio.on("tweet_deleted")
        async def on_delete(data):
            pass  # nothing to retract in the pipeline

        logger.info("J7 connecting", server=server)
        await sio.connect(
            server,
            transports=["websocket"],
            auth={"token": self.token},
        )
        await sio.wait()

    # ---- normalization ----

    async def _handle_tweet(self, raw: dict):
        if not isinstance(raw, dict):
            return
        text = (raw.get("text") or "").strip()
        if not text:
            return
        author = raw.get("author") or {}
        item = {
            "text": text,
            "platform": "x",
            "handle": author.get("handle") or "unknown",
            "url": raw.get("url") or "",
            "timestamp": _to_iso(raw.get("createdAt") or raw.get("ts")),
            "engagement": int(raw.get("likes") or 0) + int(raw.get("retweets") or 0),
        }
        self.received += 1
        await self.pipeline.process(item)

    async def _handle_ai_suggestion(self, data: dict):
        """J7's ticker prediction for a tweet -> inject $TICKER so the
        pipeline's token extractor picks it up."""
        if not isinstance(data, dict):
            return
        ticker = (data.get("ticker") or data.get("ai_ticker") or "").strip()
        prediction = (data.get("prediction") or "").strip()
        url = data.get("tweet_url") or ""
        if not ticker and not prediction:
            return
        clean = ticker.replace("\u2060", "").strip().upper().lstrip("$")
        text = f"${clean} {prediction}".strip() if clean else prediction
        if not text:
            return
        self.received += 1
        await self.pipeline.process({
            "text": text,
            "platform": "x",
            "handle": "j7_ai",
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engagement": 0,
        })

    def get_status(self) -> dict:
        return {
            "enabled": settings.J7_ENABLED and bool(self.token),
            "running": self.running,
            "connected": bool(self.sio and self.sio.connected),
            "server": J7_SERVERS[self.server_idx % len(J7_SERVERS)],
            "received": self.received,
        }
