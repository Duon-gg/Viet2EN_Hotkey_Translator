"""Authenticated localhost WebSocket bridge for the Chrome/Edge extension."""

from __future__ import annotations

import json
import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

from utils import config

LOGGER = logging.getLogger("viet2en.browser_bridge")


@dataclass
class BrowserSelection:
    text: str
    request_id: str
    source: str = "dom"
    tab_id: int | None = None
    frame_id: int | None = None
    editable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    _connection: Any = field(default=None, repr=False, compare=False)


class BrowserBridge:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connections: set[Any] = set()
        self._pending: dict[tuple[str, str], queue.Queue[dict[str, Any]]] = {}
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._last_error = ""

    @property
    def connected(self) -> bool:
        with self._lock:
            return bool(self._connections)

    @property
    def connection_count(self) -> int:
        with self._lock:
            return len(self._connections)

    @property
    def last_error(self) -> str:
        return self._last_error

    def start(self) -> bool:
        if not config.config.get("browser_bridge_enabled", True):
            return False
        with self._lock:
            if self._thread and self._thread.is_alive():
                return True
            self._started.clear()
            self._thread = threading.Thread(
                target=self._serve,
                name="viet2en-browser-bridge",
                daemon=True,
            )
            self._thread.start()
        self._started.wait(timeout=2)
        return not bool(self._last_error)

    def _serve(self) -> None:
        try:
            from websockets.sync.server import serve

            port = int(config.config.get("browser_bridge_port", 8765))
            with serve(
                self._handle_connection,
                "127.0.0.1",
                port,
                compression=None,
                max_size=256 * 1024,
                ping_interval=20,
                ping_timeout=20,
            ) as server:
                self._server = server
                self._last_error = ""
                self._started.set()
                LOGGER.info("Browser bridge listening on 127.0.0.1:%s", port)
                server.serve_forever()
        except Exception as exc:
            self._last_error = str(exc)
            self._started.set()
            LOGGER.exception("Browser bridge failed")
        finally:
            self._server = None
            with self._lock:
                self._connections.clear()

    def _authorized(self, websocket: Any) -> bool:
        request = getattr(websocket, "request", None)
        path = getattr(request, "path", "")
        query = parse_qs(urlparse(path).query)
        supplied_token = query.get("token", [""])[0]
        expected_token = str(config.config.get("browser_bridge_token", ""))
        if not supplied_token or supplied_token != expected_token:
            return False

        headers = getattr(request, "headers", {})
        origin = headers.get("Origin", "") if headers else ""
        return not origin or origin.startswith("chrome-extension://") or origin.startswith("moz-extension://")

    def _handle_connection(self, websocket: Any) -> None:
        if not self._authorized(websocket):
            websocket.close(code=1008, reason="Unauthorized Viet2EN bridge client")
            return

        with self._lock:
            self._connections.add(websocket)
        LOGGER.info("Browser extension connected")
        try:
            websocket.send(json.dumps({"type": "hello", "app": "Viet2EN", "version": 1}))
            for raw_message in websocket:
                self._handle_message(websocket, raw_message)
        except Exception:
            LOGGER.info("Browser extension disconnected", exc_info=True)
        finally:
            with self._lock:
                self._connections.discard(websocket)

    def _handle_message(self, websocket: Any, raw_message: str | bytes) -> None:
        try:
            if isinstance(raw_message, bytes):
                raw_message = raw_message.decode("utf-8")
            message = json.loads(raw_message)
            message_type = str(message.get("type", ""))
            request_id = str(message.get("request_id", ""))
            if message_type == "ping":
                websocket.send(json.dumps({"type": "pong"}))
                return
            if message_type not in {"selection", "applied"} or not request_id:
                return
            key = (message_type, request_id)
            with self._lock:
                target_queue = self._pending.get(key)
            if target_queue:
                message["_connection"] = websocket
                target_queue.put_nowait(message)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            LOGGER.warning("Ignored invalid browser bridge message")

    def _send(self, websocket: Any, message: dict[str, Any]) -> bool:
        try:
            websocket.send(json.dumps(message, ensure_ascii=False))
            return True
        except Exception:
            with self._lock:
                self._connections.discard(websocket)
            return False

    def extract_selection(self, timeout: float | None = None) -> BrowserSelection | None:
        if not self.connected:
            return None
        request_id = uuid.uuid4().hex
        response_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        key = ("selection", request_id)
        with self._lock:
            self._pending[key] = response_queue
            connections = tuple(self._connections)

        request = {"type": "extract", "request_id": request_id}
        sent = any(self._send(connection, request) for connection in connections)
        if not sent:
            with self._lock:
                self._pending.pop(key, None)
            return None

        if timeout is None:
            timeout = float(config.config.get("browser_extract_timeout_seconds", 0.45))
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty:
            return None
        finally:
            with self._lock:
                self._pending.pop(key, None)

        text = str(response.get("text", ""))
        if not text.strip():
            return None
        return BrowserSelection(
            text=text,
            request_id=request_id,
            source=str(response.get("source", "dom")),
            tab_id=response.get("tab_id"),
            frame_id=response.get("frame_id"),
            editable=bool(response.get("editable", False)),
            metadata=dict(response.get("metadata", {})),
            _connection=response.get("_connection"),
        )

    def apply_translation(
        self,
        selection: BrowserSelection,
        translated: str,
        timeout: float = 0.7,
    ) -> bool:
        if selection._connection is None:
            return False
        response_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        key = ("applied", selection.request_id)
        with self._lock:
            self._pending[key] = response_queue
        message = {
            "type": "apply",
            "request_id": selection.request_id,
            "text": translated,
            "tab_id": selection.tab_id,
            "frame_id": selection.frame_id,
        }
        try:
            if not self._send(selection._connection, message):
                return False
            response = response_queue.get(timeout=timeout)
            return bool(response.get("success", False))
        except queue.Empty:
            return False
        finally:
            with self._lock:
                self._pending.pop(key, None)

    def stop(self) -> None:
        server = self._server
        if server:
            try:
                server.shutdown()
            except Exception:
                LOGGER.exception("Unable to stop browser bridge")
        with self._lock:
            connections = tuple(self._connections)
            self._connections.clear()
        for connection in connections:
            try:
                connection.close(code=1001, reason="Viet2EN is shutting down")
            except Exception:
                pass


BRIDGE = BrowserBridge()
