from __future__ import annotations

import json

from utils import config


def test_validation_clamps_and_generates_token() -> None:
    result = config._validated(
        {
            "direction": "invalid",
            "auto_unload_minutes": -10,
            "restore_delay_seconds": -4,
            "browser_bridge_port": 99999,
            "browser_bridge_token": "short",
            "glossary": {" hotkey ": " phím tắt ", "": "ignored"},
        }
    )
    assert result["direction"] == "auto"
    assert result["auto_unload_minutes"] == 1
    assert result["restore_delay_seconds"] == 0.05
    assert result["browser_bridge_port"] == 65535
    assert len(result["browser_bridge_token"]) >= 24
    assert result["glossary"] == {"hotkey": "phím tắt"}


def test_atomic_save_and_reload(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)
    monkeypatch.setattr(config, "LEGACY_CONFIG_FILE", tmp_path / "legacy.json")
    config.config = config._validated({"hotkey": "ctrl+alt+t", "direction": "vi_en"})
    config.save_config()

    parsed = json.loads(config_file.read_text(encoding="utf-8"))
    assert parsed["hotkey"] == "ctrl+alt+t"
    config.config = {}
    assert config.load_config()["direction"] == "vi_en"
