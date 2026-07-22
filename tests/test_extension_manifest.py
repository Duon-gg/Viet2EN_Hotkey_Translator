from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_extension_runs_early_in_all_frames() -> None:
    manifest = json.loads((ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8"))
    content = manifest["content_scripts"][0]
    assert manifest["manifest_version"] == 3
    assert content["run_at"] == "document_start"
    assert content["all_frames"] is True
    assert content["match_about_blank"] is True
    assert content["match_origin_as_fallback"] is True


def test_anti_copy_fixture_opens_minimal_popup() -> None:
    fixture = (ROOT / "test_anti_copy.html").read_text(encoding="utf-8")
    assert "popup=yes" in fixture
    assert "toolbar=no" in fixture
    assert '"copy", "cut", "paste", "contextmenu"' in fixture
