from __future__ import annotations

import json
import socket
import threading
import time

from websockets.sync.client import connect

from core.browser_bridge import BrowserBridge
from utils import config


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_authenticated_browser_bridge_round_trip() -> None:
    port = _free_port()
    token = "test-token-that-is-long-enough-12345"
    config.config.update(
        {
            "browser_bridge_enabled": True,
            "browser_bridge_port": port,
            "browser_bridge_token": token,
            "browser_extract_timeout_seconds": 1.5,
        }
    )
    bridge = BrowserBridge()
    assert bridge.start()

    def extension_client() -> None:
        with connect(
            f"ws://127.0.0.1:{port}/?token={token}",
            origin="chrome-extension://test-extension",
        ) as websocket:
            for raw_message in websocket:
                message = json.loads(raw_message)
                if message["type"] == "extract":
                    websocket.send(
                        json.dumps(
                            {
                                "type": "selection",
                                "request_id": message["request_id"],
                                "text": "Xin chào",
                                "tab_id": 5,
                                "frame_id": 0,
                                "editable": True,
                            }
                        )
                    )
                elif message["type"] == "apply":
                    websocket.send(
                        json.dumps(
                            {
                                "type": "applied",
                                "request_id": message["request_id"],
                                "success": True,
                            }
                        )
                    )
                    return

    client_thread = threading.Thread(target=extension_client, daemon=True)
    client_thread.start()
    deadline = time.monotonic() + 2
    while not bridge.connected and time.monotonic() < deadline:
        time.sleep(0.02)

    try:
        selection = bridge.extract_selection(timeout=1.5)
        assert selection is not None
        assert selection.text == "Xin chào"
        assert selection.editable
        assert bridge.apply_translation(selection, "Hello", timeout=1.5)
    finally:
        bridge.stop()
        client_thread.join(timeout=2)
