# Viet2EN Hotkey Translator

**🌐 English | [Tiếng Việt](README.md)**

**Translate right where you're typing — select, press F2, done.**

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)

An offline Vietnamese ↔ English translator that lives in your system tray. Select any text in any app, press `F2`, and the translation replaces it in-place. No browser tabs, no copy-pasting into Google Translate. Powered by [Argos Translate](https://github.com/argosopentech/argos-translate) — your data never leaves your machine.

---



## 📑 Table of Contents

- [Features](#-features)
- [System Requirements](#-system-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [Advanced Configuration](#-advanced-configuration)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License & Credits](#-license--credits)

---

## ✨ Features

- ⚡ **Instant hotkey translation** — select text in any app, press `F2`, and the result overwrites it on the spot. No browser needed.
- 🔌 **Fully offline** — translation models run locally. No data sent anywhere, no internet required after initial model download.
- 🧠 **Auto language detection** — Vietnamese text gets translated to English, English text gets translated to Vietnamese. No manual switching.
- 💤 **Smart RAM management** — models auto-unload from memory after 30 minutes of inactivity (configurable), reload on demand.
- 🚀 **Near-instant startup** — the app doesn't load models on launch, only on first translation (Lazy Load).
- 🔒 **Single instance guard** — launching the app twice silently exits the duplicate. No stacking.
- 📋 **Clipboard preservation** — your original clipboard content is automatically restored after translation.

---

## 💻 System Requirements

| Component | Requirement |
|---|---|
| OS | Windows 10 / 11 |
| Python | 3.10+ (if running from source) |
| Disk space | ~150 MB for both translation models (VI↔EN) |
| RAM | ~500 MB when models are loaded |

---

## 📦 Installation

### Option 1 — Pre-built `.exe`

1. Download `Viet2EN.exe` from the [Releases](<!-- TODO: add GitHub Releases link -->) page
2. Place it in its own folder (e.g. `C:\Tools\Viet2EN\`)
3. Run `Viet2EN.exe` — icon appears in the system tray
4. On first launch: the settings window opens automatically → click **Download Model** to fetch translation models (~150 MB, internet required for this step only)

### Option 2 — Run from source

```bash
git clone https://github.com/<your-username>/Viet2EN_Hotkey_Translator.git
cd Viet2EN_Hotkey_Translator

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy config.example.json config.json
python main.py
```

On first launch, the settings window opens automatically so you can download translation models. After that, no internet connection is needed.

To run silently (no console window): double-click `run.vbs`.

---

## 🎯 Usage

1. Select (highlight) the text you want to translate — in any app (browser, Word, Notepad, IDE...)
2. Press **`F2`**
3. The text briefly shows `...` while processing, then gets replaced with the translation

No tab switching, no app to open. Your original clipboard is automatically restored after pasting.

### Hotkeys & Options

| Option | Default | Change via |
|---|---|---|
| Translate key | `F2` | Settings (right-click tray icon → **Settings**) |
| Available keys | `F2` through `F8` | Dropdown in Settings window |
| Enable / disable | Enabled | Right-click tray icon → **Enable translation** |

---

## ⚙ Advanced Configuration

Edit `config.json` in the project root (or use the Settings UI):

| Field | Description | Default |
|---|---|---|
| `hotkey` | Translation hotkey. Accepts `f2` through `f8` | `"f2"` |
| `startup` | Auto-start with Windows | `false` |
| `auto_unload_minutes` | Minutes of inactivity before unloading models from RAM | `30` |
| `restore_delay_seconds` | Seconds to wait before restoring original clipboard after pasting the result | `0.8` |

> No `config.json`? The app creates one with defaults. Or copy from `config.example.json`.

---

## 🔧 Troubleshooting

**Pressing F2 does nothing:**
→ Check if the tray icon is visible. If not, the app isn't running or has crashed — open `viet2en.log` for error details.

**Translation doesn't work in certain windows (Task Manager, elevated Command Prompt...):**
→ Windows security limitation: a User-level process cannot send keystrokes to an Administrator-level process. Fix: close Viet2EN, right-click → **Run as Administrator**.

**First F2 press is slow (~2-5 seconds):**
→ Expected behavior. Translation models use Lazy Loading — they only load into RAM on the first translation. Subsequent translations are much faster until the model auto-unloads after idle timeout.

**Online model download fails:**
→ Open Settings → use **Install from file (.argosmodel)** to install manually. Download `.argosmodel` files for `vi→en` and `en→vi` from [Argos Translate packages](https://www.argosopentech.com/argospm/index/).

---

## 🤝 Contributing

Found a bug, have an idea, or want to send a pull request — open an [Issue](<!-- TODO: add Issues link -->) on GitHub. All contributions are welcome.

---

## 📄 License & Credits

Released under the [MIT License](LICENSE).

Built on top of these open-source projects:

- [Argos Translate](https://github.com/argosopentech/argos-translate) — offline translation engine
- [CTranslate2](https://github.com/OpenNMT/CTranslate2) — inference runtime for translation models
- [pystray](https://github.com/moses-palmer/pystray) — system tray icon
- [keyboard](https://github.com/boppreh/keyboard) — system-wide hotkey capture
- [pyperclip](https://github.com/asweigart/pyperclip) — clipboard interaction
