# Vitra 2.0

**English | [Tiếng Việt](README.vi.md)**

An offline-first Vietnamese ↔ English Windows translator. Select text, press a hotkey, and Vitra translates it in place when the target can be edited; otherwise it silently copies the translation to the clipboard. Version 2 adds an anti-copy browser extension, Windows UI Automation, safe clipboard transactions, and offline OCR.

## Highlights

- Extraction pipeline: **Browser DOM → UI Automation → Clipboard → OCR**.
- No placeholder/Backspace workflow; content changes only after translation succeeds.
- Foreground-window and focused-control guards prevent pasting into the wrong app; fallback results are copied to the clipboard without a result popup.
- Thread-safe Argos engine with background preload, automatic unload, CPU/CUDA and INT8 options.
- Improved accentless Vietnamese detection and optional common-word diacritic restoration.
- User glossary plus protection for URLs, email, code, and placeholders.
- Manifest V3 Chrome/Edge extension for popup windows, frames, and anti-copy pages.
- RapidOCR/ONNX Runtime screen-region translation.
- LocalAppData config, rotating logs, automated tests, linting, typing, CI, and PyInstaller packaging.

## Source installation

```bat
git clone https://github.com/Duon-gg/Vitra.git
cd Vitra
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Install both Argos VI↔EN models from the Settings window on first launch.

## Hotkeys

- `F2`: automatic direction.
- `Ctrl+F2`: force Vietnamese → English.
- `Shift+F2`: force English → Vietnamese.
- Tray → **Translate screen region (OCR)** for images, canvas, and scanned PDFs. OCR results are copied to the clipboard.

The base hotkey is configurable.

## Browser extension

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Load the `browser_extension` directory as an unpacked extension.
4. Copy the bridge token and port from Vitra Settings into the extension Options page.
5. Enable **Allow access to file URLs** to test `test_anti_copy.html`.

The extension runs at `document_start` in matching frames and connects only to an authenticated WebSocket bound to `127.0.0.1`.

## Quality checks

```bat
python -m pytest -q
python -m ruff check main.py core ui utils scripts tests
python -m mypy main.py core ui utils scripts
```

Real-browser anti-copy E2E test:

```bat
python -m playwright install chromium
python scripts\test_anti_copy_browser.py
```

## Build

```bat
build.bat
build.bat --offline
```

The default build produces `dist\Vitra\`, including the extension and runtime dependency license texts; `--offline` also copies installed translation models.

## Data and limitations

- Argos and RapidOCR run locally; translated text isn't written to logs.
- Configuration and logs live under `%LOCALAPPDATA%\Vitra`.
- Translation quality is limited by the installed Argos models.
- When in-place replacement is unsafe or unsupported, Vitra copies the translation to the clipboard instead of showing a result window.
- Browser privileged pages, separate profiles, unsupported WebViews, DRM, and canvas may require OCR or may remain inaccessible.
- The tool processes content the user is already authorized to view; it doesn't bypass authentication, encryption, or DRM.

## License

Vitra's own source is MIT. The runtime dependency set includes MiniSBD under AGPL-3.0, so review distribution obligations before publishing a bundled binary. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for details and OPUS-MT model attribution.
