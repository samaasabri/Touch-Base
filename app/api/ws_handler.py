from __future__ import annotations

import asyncio
import base64
import json
from typing import AsyncIterable

from fastapi import Query, WebSocket
from fastapi.websockets import WebSocketDisconnect
from google.adk.agents import LiveRequestQueue
from google.adk.events.event import Event
from google.genai import types


async def agent_to_client_messaging(websocket: WebSocket, live_events: AsyncIterable[Event | None]):
    async for event in live_events:
        if event is None:
            continue
        if event.turn_complete or event.interrupted:
            await websocket.send_text(
                json.dumps({"turn_complete": event.turn_complete, "interrupted": event.interrupted})
            )
            continue
        part = event.content and event.content.parts and event.content.parts[0]
        if not part or not isinstance(part, types.Part):
            continue
        if part.text and event.partial:
            await websocket.send_text(
                json.dumps({"mime_type": "text/plain", "data": part.text, "role": "model"})
            )
        is_audio = (
            part.inline_data
            and part.inline_data.mime_type
            and part.inline_data.mime_type.startswith("audio/pcm")
        )
        if is_audio and part.inline_data.data:
            await websocket.send_text(
                json.dumps(
                    {
                        "mime_type": "audio/pcm",
                        "data": base64.b64encode(part.inline_data.data).decode("ascii"),
                        "role": "model",
                    }
                )
            )


async def client_to_agent_messaging(websocket: WebSocket, live_request_queue: LiveRequestQueue):
    while True:
        try:
            message_json = await websocket.receive_text()
        except WebSocketDisconnect:
            break
        except Exception:
            break

        message = json.loads(message_json)
        mime_type = message["mime_type"]
        data = message["data"]
        role = message.get("role", "user")

        if mime_type == "text/plain":
            content = types.Content(role=role, parts=[types.Part.from_text(text=data)])
            live_request_queue.send_content(content=content)
        elif mime_type == "audio/pcm":
            decoded_data = base64.b64decode(data)
            live_request_queue.send_realtime(types.Blob(data=decoded_data, mime_type=mime_type))


async def keepalive_ping(websocket: WebSocket, interval: int = 20):
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except Exception:
        pass


def build_websocket_endpoint(live_session_service):
    async def websocket_endpoint(
        websocket: WebSocket,
        session_id: str,
        is_audio: str = Query(...),
    ):
        await websocket.accept()
        live_events, live_request_queue = live_session_service.start_agent_session(session_id)
        try:
            agent_to_client_task = asyncio.create_task(agent_to_client_messaging(websocket, live_events))
            client_to_agent_task = asyncio.create_task(client_to_agent_messaging(websocket, live_request_queue))
            keepalive_task = asyncio.create_task(keepalive_ping(websocket))
            done, pending = await asyncio.wait(
                [agent_to_client_task, client_to_agent_task, keepalive_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            for task in done:
                exc = task.exception()
                if exc and not isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                    print(f"Client #{session_id} connection error: {exc}")
        finally:
            live_request_queue.close()

    return websocket_endpoint
