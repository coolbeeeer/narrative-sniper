import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
import structlog
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from src.dashboard.models import WebSocketMessage, NarrativeData, PositionData, TradeData, SystemStatus, PerformanceData, NarrativeStatus, PositionStatus, HealthStatus


logger = structlog.get_logger()


@dataclass
class ConnectionManager:
    active_connections: Dict[str, WebSocket] = field(default_factory=dict)
    subscriptions: Dict[str, Set[str]] = field(default_factory=dict)

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        logger.info("websocket_connected", client_id=client_id, total=len(self.active_connections))

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        self.subscriptions.pop(client_id, None)
        logger.info("websocket_disconnected", client_id=client_id, total=len(self.active_connections))

    def subscribe(self, client_id: str, channel: str):
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(channel)

    def unsubscribe(self, client_id: str, channel: str):
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(channel)

    async def send_personal_message(self, client_id: str, message: WebSocketMessage):
        websocket = self.active_connections.get(client_id)
        if websocket and websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(message.model_dump())
            except Exception as e:
                logger.error("websocket_send_failed", client_id=client_id, error=str(e))

    async def broadcast(self, message: WebSocketMessage, channel: Optional[str] = None):
        if channel:
            clients = [
                cid for cid, subs in self.subscriptions.items()
                if channel in subs
            ]
        else:
            clients = list(self.active_connections.keys())

        for client_id in clients:
            await self.send_personal_message(client_id, message)

    async def broadcast_narrative_update(self, narrative: NarrativeData):
        message = WebSocketMessage(
            type="narrative_update",
            data=narrative.__dict__,
        )
        await self.broadcast(message, "narratives")

    async def broadcast_position_update(self, position: PositionData):
        message = WebSocketMessage(
            type="position_update",
            data=position.__dict__,
        )
        await self.broadcast(message, "positions")

    async def broadcast_trade(self, trade: TradeData):
        message = WebSocketMessage(
            type="trade",
            data=trade.__dict__,
        )
        await self.broadcast(message, "trades")

    async def broadcast_system_status(self, status: SystemStatus):
        message = WebSocketMessage(
            type="system_status",
            data=status.__dict__,
        )
        await self.broadcast(message, "system")

    async def broadcast_performance(self, performance: PerformanceData):
        message = WebSocketMessage(
            type="performance",
            data=performance.__dict__,
        )
        await self.broadcast(message, "performance")


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_client_message(client_id, message)
            except json.JSONDecodeError:
                logger.warning("websocket_invalid_json", client_id=client_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error("websocket_error", client_id=client_id, error=str(e))
        manager.disconnect(client_id)


async def handle_client_message(client_id: str, message: Dict[str, Any]):
    msg_type = message.get("type")

    if msg_type == "subscribe":
        channels = message.get("channels", [])
        for channel in channels:
            manager.subscribe(client_id, channel)
        await manager.send_personal_message(client_id, WebSocketMessage(
            type="subscribed",
            data={"channels": list(manager.subscriptions.get(client_id, set()))},
        ))

    elif msg_type == "unsubscribe":
        channels = message.get("channels", [])
        for channel in channels:
            manager.unsubscribe(client_id, channel)
        await manager.send_personal_message(client_id, WebSocketMessage(
            type="unsubscribed",
            data={"channels": list(manager.subscriptions.get(client_id, set()))},
        ))

    elif msg_type == "ping":
        await manager.send_personal_message(client_id, WebSocketMessage(
            type="pong",
            data={"timestamp": datetime.now(timezone.utc).isoformat()},
        ))

    elif msg_type == "get_state":
        await manager.send_personal_message(client_id, WebSocketMessage(
            type="state",
            data={"subscriptions": list(manager.subscriptions.get(client_id, set()))},
        ))


async def start_heartbeat(interval: int = 30):
    while True:
        await asyncio.sleep(interval)
        for client_id in list(manager.active_connections.keys()):
            await manager.send_personal_message(client_id, WebSocketMessage(
                type="heartbeat",
                data={"timestamp": datetime.now(timezone.utc).isoformat()},
            ))


def get_connection_manager() -> ConnectionManager:
    return manager