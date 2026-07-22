"""Real-browser E2E test for the anti-copy page, extension, bridge, and model."""

from __future__ import annotations

import json
import secrets
import socket
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from playwright.sync_api import BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.browser_bridge import BrowserBridge  # noqa: E402
from utils import config  # noqa: E402

EXTENSION_DIR = ROOT / "browser_extension"
RESULTS_DIR = ROOT / "test-results"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: Any) -> None:
        return


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until(predicate, timeout: float, description: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {description}")


def open_protected_popup(context: BrowserContext, launcher_url: str) -> Page:
    launcher = context.new_page()
    launcher.goto(launcher_url, wait_until="domcontentloaded")
    with context.expect_page() as popup_info:
        launcher.locator("#launch").click()
    popup = popup_info.value
    popup.wait_for_url("**/*popup=1*", timeout=10000)
    popup.wait_for_load_state("domcontentloaded")
    popup.bring_to_front()
    assert "popup=1" in popup.url
    assert popup.title() == "Viet2EN — Protected Popup"
    return popup


def event_allowed(page: Page, selector: str, event_name: str) -> bool:
    return bool(
        page.locator(selector).first.evaluate(
            """(element, name) => element.dispatchEvent(
                new MouseEvent(name, { bubbles: true, cancelable: true })
            )""",
            event_name,
        )
    )


def baseline_checks(context: BrowserContext, launcher_url: str) -> dict[str, Any]:
    popup = open_protected_popup(context, launcher_url)
    paragraph = popup.locator(".sample p").filter(has_text="This protected page")
    paragraph.select_text()
    popup.wait_for_timeout(150)
    selection = popup.evaluate("window.getSelection().toString()")
    user_select = paragraph.evaluate("element => getComputedStyle(element).userSelect")
    context_menu_allowed = event_allowed(popup, ".sample p", "contextmenu")

    assert selection == "", "The baseline page unexpectedly allowed text selection"
    assert user_select == "none", f"Expected user-select:none, got {user_select!r}"
    assert not context_menu_allowed, "The baseline page unexpectedly allowed contextmenu"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    popup.screenshot(path=RESULTS_DIR / "anti-copy-baseline.png", full_page=True)
    return {
        "selection_blocked": selection == "",
        "computed_user_select": user_select,
        "context_menu_blocked": not context_menu_allowed,
    }


def extension_id(context: BrowserContext) -> str:
    workers = context.service_workers
    worker = workers[0] if workers else context.wait_for_event("serviceworker", timeout=15000)
    return worker.url.split("/")[2]


def configure_extension(context: BrowserContext, extension: str, port: int, token: str) -> None:
    page = context.new_page()
    page.goto(f"chrome-extension://{extension}/options.html", wait_until="domcontentloaded")
    page.evaluate(
        """async settings => {
            await chrome.storage.sync.set(settings);
        }""",
        {
            "enabled": True,
            "port": port,
            "token": token,
            "unlockAntiCopy": True,
            "hoverFallback": True,
            "replaceReadonly": False,
        },
    )
    page.close()


def extension_checks(
    context: BrowserContext,
    launcher_url: str,
    bridge: BrowserBridge,
) -> dict[str, Any]:
    popup = open_protected_popup(context, launcher_url)
    popup.wait_for_function("document.documentElement.classList.contains('viet2en-unlock')")
    paragraph = popup.locator(".sample p").filter(has_text="This protected page")
    paragraph.select_text()
    popup.wait_for_timeout(150)
    selection_text = str(popup.evaluate("window.getSelection().toString()"))
    user_select = str(paragraph.evaluate("element => getComputedStyle(element).userSelect"))
    context_menu_allowed = event_allowed(popup, ".sample p", "contextmenu")

    assert "This protected page" in selection_text
    assert user_select == "text", f"Extension did not override user-select: {user_select!r}"
    assert context_menu_allowed, "Extension did not neutralize the contextmenu blocker"

    readonly = bridge.extract_selection(timeout=3)
    assert readonly is not None and readonly.text.strip() == selection_text.strip()
    assert not readonly.editable
    assert not bridge.apply_translation(readonly, "READONLY-SAFETY-CHECK", timeout=3)
    assert "READONLY-SAFETY-CHECK" not in popup.locator("body").inner_text()

    textarea = popup.locator("textarea")
    original = textarea.input_value()
    textarea.click()
    textarea.press("Control+A")
    bounds = textarea.evaluate("element => [element.selectionStart, element.selectionEnd]")
    assert bounds == [0, len(original)], f"Ctrl+A remained blocked: {bounds!r}"

    editable = bridge.extract_selection(timeout=3)
    assert editable is not None and editable.text == original and editable.editable

    from core import engine

    translated = engine.translate_text(editable.text, "vi_en")
    assert translated.strip() and translated.strip() != original.strip()
    assert bridge.apply_translation(editable, translated, timeout=3)
    popup.wait_for_function(
        "([selector, expected]) => document.querySelector(selector).value === expected",
        arg=["textarea", translated],
    )
    assert textarea.input_value() == translated

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    popup.screenshot(path=RESULTS_DIR / "anti-copy-extension-pass.png", full_page=True)
    return {
        "popup_opened": True,
        "selection_unlocked": True,
        "computed_user_select": user_select,
        "context_menu_unlocked": context_menu_allowed,
        "readonly_not_replaced": True,
        "textarea_ctrl_a_unlocked": True,
        "bridge_source": editable.source,
        "bridge_editable": editable.editable,
        "original": original,
        "translated": translated,
        "translation_applied": textarea.input_value() == translated,
    }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs),
    )
    http_thread = threading.Thread(target=httpd.serve_forever, name="anti-copy-http", daemon=True)
    http_thread.start()
    launcher_url = f"http://127.0.0.1:{httpd.server_port}/test_anti_copy.html"

    original_config = config.config
    config.config = config._validated(config.DEFAULT_CONFIG)
    config.config.update(
        {
            "browser_bridge_enabled": True,
            "browser_bridge_port": free_port(),
            "browser_bridge_token": secrets.token_urlsafe(32),
            "browser_extract_timeout_seconds": 3.0,
        }
    )
    config.configure_runtime_environment()
    bridge = BrowserBridge()
    assert bridge.start(), bridge.last_error

    report: dict[str, Any] = {"url": launcher_url}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                report["baseline"] = baseline_checks(browser.new_context(), launcher_url)
            finally:
                browser.close()

            with TemporaryDirectory(prefix="viet2en-playwright-") as profile:
                context = playwright.chromium.launch_persistent_context(
                    profile,
                    headless=False,
                    args=[
                        f"--disable-extensions-except={EXTENSION_DIR}",
                        f"--load-extension={EXTENSION_DIR}",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                )
                try:
                    ext_id = extension_id(context)
                    configure_extension(
                        context,
                        ext_id,
                        int(config.config["browser_bridge_port"]),
                        str(config.config["browser_bridge_token"]),
                    )
                    wait_until(lambda: bridge.connected, 15, "authenticated extension bridge")
                    report["extension_id"] = ext_id
                    report["bridge_connected"] = bridge.connected
                    report["extension"] = extension_checks(context, launcher_url, bridge)
                finally:
                    context.close()
    finally:
        bridge.stop()
        try:
            from core import engine

            engine.shutdown()
        except ImportError:
            pass
        config.config = original_config
        httpd.shutdown()
        httpd.server_close()

    report_path = RESULTS_DIR / "anti-copy-e2e-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"PASS: report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
