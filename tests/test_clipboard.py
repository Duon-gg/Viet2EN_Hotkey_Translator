from __future__ import annotations

from unittest.mock import Mock

from core import clipboard


def test_smart_strip_preserves_outer_whitespace() -> None:
    assert clipboard.smart_strip("\n  hello \t") == ("\n  ", "hello", " \t")


def test_acquire_selection_restores_original_clipboard(monkeypatch) -> None:
    snapshot = Mock()
    focus = clipboard.FocusContext(10, 11, 12)
    monkeypatch.setattr(clipboard.ClipboardSnapshot, "capture", Mock(return_value=snapshot))
    monkeypatch.setattr(clipboard.FocusContext, "capture", Mock(return_value=focus))
    monkeypatch.setattr(clipboard, "safe_copy", Mock(return_value=True))
    monkeypatch.setattr(clipboard.keyboard, "send", Mock())
    monkeypatch.setattr(clipboard, "wait_for_sequence_change", Mock(return_value=True))
    monkeypatch.setattr(clipboard, "safe_paste", Mock(return_value=" selected text "))
    monkeypatch.setattr(clipboard, "clipboard_sequence_number", Mock(side_effect=[2, 3, 3]))

    result = clipboard.acquire_selected_text()
    assert result == clipboard.ClipboardSelection(" selected text ", focus)
    snapshot.restore.assert_called_once()


def test_paste_refuses_changed_focus_and_copies_result(monkeypatch) -> None:
    focus = Mock()
    focus.is_current.return_value = False
    safe_copy = Mock(return_value=True)
    monkeypatch.setattr(clipboard, "safe_copy", safe_copy)
    selection = clipboard.ClipboardSelection("source", focus)

    assert clipboard.paste_translation(selection, "translated") is False
    safe_copy.assert_called_once_with("translated")


def test_paste_restores_clipboard_only_when_unchanged(monkeypatch) -> None:
    focus = Mock()
    focus.is_current.return_value = True
    snapshot = Mock()
    monkeypatch.setattr(clipboard.ClipboardSnapshot, "capture", Mock(return_value=snapshot))
    monkeypatch.setattr(clipboard, "safe_copy", Mock(return_value=True))
    monkeypatch.setattr(clipboard, "clipboard_sequence_number", Mock(side_effect=[7, 7]))
    monkeypatch.setattr(clipboard.keyboard, "send", Mock())
    monkeypatch.setattr(clipboard.time, "sleep", Mock())

    assert clipboard.paste_translation(clipboard.ClipboardSelection("source", focus), "result")
    snapshot.restore.assert_called_once()
