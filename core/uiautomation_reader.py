"""Best-effort selected-text extraction through Windows UI Automation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from utils import config

LOGGER = logging.getLogger("vitra.uiautomation")


@dataclass(frozen=True)
class UIASelection:
    text: str
    control_key: tuple[Any, ...]
    control_name: str


def _control_key(control: Any) -> tuple[Any, ...]:
    try:
        runtime_id = tuple(control.GetRuntimeId() or ())
    except Exception:
        runtime_id = ()
    return (
        getattr(control, "NativeWindowHandle", 0),
        getattr(control, "ControlType", 0),
        runtime_id,
    )


def extract_selected_text(max_ancestors: int = 6) -> UIASelection | None:
    if not config.config.get("uiautomation_enabled", True):
        return None
    try:
        import uiautomation as auto

        control = auto.GetFocusedControl()
        for _ in range(max_ancestors):
            if control is None:
                break
            try:
                pattern = control.GetPattern(auto.PatternId.TextPattern)
                if pattern:
                    ranges = pattern.GetSelection()
                    for text_range in ranges:
                        text = text_range.GetText(-1)
                        if text and text.strip():
                            return UIASelection(
                                text=text,
                                control_key=_control_key(control),
                                control_name=str(getattr(control, "Name", "")),
                            )
            except Exception:
                LOGGER.debug("Focused control has no readable TextPattern", exc_info=True)
            try:
                control = control.GetParentControl()
            except Exception:
                break
    except Exception:
        LOGGER.debug("UI Automation selection extraction failed", exc_info=True)
    return None


def selection_is_still_focused(selection: UIASelection) -> bool:
    try:
        import uiautomation as auto

        focused = auto.GetFocusedControl()
        for _ in range(6):
            if focused is None:
                return False
            if _control_key(focused) == selection.control_key:
                return True
            focused = focused.GetParentControl()
    except Exception:
        LOGGER.debug("Unable to verify UI Automation focus", exc_info=True)
    return False
