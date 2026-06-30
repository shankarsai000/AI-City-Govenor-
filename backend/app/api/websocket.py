"""
WebSocket router for real-time event streaming.

Provides live feeds for:
- /ws/events     — All city events (dashboard)
- /ws/approvals  — Pending approval queue updates
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.redis_client import get_redis_pubsub
from app.security.jwt_service import JWTService
from app.security.token_store import is_token_revoked

logger = get_logger(__name__)

router = APIRouter()

# Track active WebSocket connections for broadcasting
_active_connections: list[WebSocket] = []


async def _authenticate_websocket(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing access token.")
        return False

    try:
        principal, _ = JWTService.decode_token(token, expected_type="access")
        if await is_token_revoked(principal.token_id):
            await websocket.close(code=1008, reason="Token has been revoked.")
            return False
    except Exception:
        await websocket.close(code=1008, reason="Invalid access token.")
        return False

    return True


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """
    Real-time city event stream.
    Subscribes to all city_governor:* Redis channels and forwards to client.
    """
    await websocket.accept()
    if not await _authenticate_websocket(websocket):
        return
    _active_connections.append(websocket)
    logger.info("WebSocket client connected", total=len(_active_connections))

    pubsub = await get_redis_pubsub()
    await pubsub.psubscribe("city_governor:*")

    try:
        async for message in pubsub.listen():
            if message["type"] not in ("pmessage", "message"):
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        _active_connections.remove(websocket)
        await pubsub.unsubscribe()
        await pubsub.close()


@router.websocket("/ws/approvals")
async def websocket_approvals(websocket: WebSocket) -> None:
    """Real-time approval queue updates."""
    await websocket.accept()
    if not await _authenticate_websocket(websocket):
        return
    pubsub = await get_redis_pubsub()
    await pubsub.psubscribe("city_governor:approval.*")

    try:
        async for message in pubsub.listen():
            if message["type"] not in ("pmessage", "message"):
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.punsubscribe("city_governor:approval.*")
        await pubsub.close()
