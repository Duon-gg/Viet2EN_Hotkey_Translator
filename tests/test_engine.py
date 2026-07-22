from __future__ import annotations

from core import engine
from utils import config


class EchoTranslator:
    def translate(self, text: str) -> str:
        return text


def test_lightweight_sentencizer_splits_and_limits_chunks() -> None:
    sentencizer = engine.LightweightSentencizer()
    assert sentencizer.split_sentences("Câu một. Câu hai! Câu ba?") == [
        "Câu một.",
        "Câu hai!",
        "Câu ba?",
    ]
    chunks = sentencizer.split_sentences("từ " * 300)
    assert len(chunks) > 1
    assert all(len(chunk) <= sentencizer.max_chunk_chars for chunk in chunks)


def test_lightweight_sentencizer_reaches_argos_cache_wrapper() -> None:
    class PackageTranslator:
        sentencizer = object()

    class CachedTranslator:
        underlying = PackageTranslator()

    wrapper = CachedTranslator()
    assert engine._replace_argos_sentencizers(wrapper)
    assert isinstance(wrapper.underlying.sentencizer, engine.LightweightSentencizer)


def test_direction_detection_handles_accentless_vietnamese() -> None:
    assert (
        engine.TranslationService.detect_direction("Xin chào, tôi đang học tiếng Anh")
        is engine.Direction.VI_EN
    )
    assert engine.TranslationService.detect_direction("toi dang hoc tieng anh") is engine.Direction.VI_EN
    assert engine.TranslationService.detect_direction("This is a translation test") is engine.Direction.EN_VI


def test_accentless_vietnamese_normalization() -> None:
    assert (
        engine.TranslationService.normalize_accentless_vietnamese("toi dang hoc tieng anh")
        == "tôi đang học tiếng anh"
    )


def test_glossary_and_urls_are_preserved(monkeypatch) -> None:
    service = engine.TranslationService()
    try:
        config.config["glossary"] = {"hotkey": "phím tắt"}
        service._translators[engine.Direction.VI_EN] = EchoTranslator()
        monkeypatch.setattr(service, "_load_direction", lambda _direction: None)
        result = service.translate("hotkey https://example.com", engine.Direction.VI_EN)
        assert result == "phím tắt https://example.com"
    finally:
        service.shutdown()


def test_embedded_english_technical_terms_are_preserved_in_vietnamese(monkeypatch) -> None:
    class ManglingTranslator:
        def translate(self, text: str) -> str:
            return text.replace("paste", "pyaste").replace("select-all", "styl-all")

    service = engine.TranslationService()
    try:
        service._translators[engine.Direction.VI_EN] = ManglingTranslator()
        monkeypatch.setattr(service, "_load_direction", lambda _direction: None)
        result = service.translate("Trang chặn copy, paste và select-all", engine.Direction.VI_EN)
        assert result == "Trang chặn copy, paste và select-all"
    finally:
        service.shutdown()


def test_active_translation_count_is_restored_on_failure(monkeypatch) -> None:
    class BrokenTranslator:
        def translate(self, _text: str) -> str:
            raise RuntimeError("boom")

    service = engine.TranslationService()
    try:
        service._translators[engine.Direction.EN_VI] = BrokenTranslator()
        monkeypatch.setattr(service, "_load_direction", lambda _direction: None)
        try:
            service.translate("hello", engine.Direction.EN_VI)
        except RuntimeError:
            pass
        assert service.status().active_translations == 0
    finally:
        service.shutdown()
