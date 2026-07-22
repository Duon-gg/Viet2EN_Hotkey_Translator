from __future__ import annotations

import logging

from utils.logging_setup import RuntimePrivacyFilter


def record(name: str, level: int) -> logging.LogRecord:
    return logging.LogRecord(name, level, __file__, 1, "message", (), None)


def test_runtime_privacy_filter_blocks_verbose_translation_logs() -> None:
    privacy_filter = RuntimePrivacyFilter()
    assert not privacy_filter.filter(record("argostranslate.utils", logging.INFO))
    assert not privacy_filter.filter(record("ctranslate2", logging.DEBUG))
    assert privacy_filter.filter(record("argostranslate.utils", logging.WARNING))
    assert privacy_filter.filter(record("vitra.engine", logging.INFO))
