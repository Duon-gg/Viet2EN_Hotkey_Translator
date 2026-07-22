"""Thread-safe Argos translation engine with lazy loading and direction detection."""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
import threading
import time
import types
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from utils import config

LOGGER = logging.getLogger("vitra.engine")


class EngineState(StrEnum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    TRANSLATING = "translating"
    INSTALLING = "installing"
    ERROR = "error"


class Direction(StrEnum):
    VI_EN = "vi_en"
    EN_VI = "en_vi"

    @property
    def codes(self) -> tuple[str, str]:
        return ("vi", "en") if self is Direction.VI_EN else ("en", "vi")


class TranslatorProtocol(Protocol):
    def translate(self, text: str) -> str: ...


@dataclass(frozen=True)
class EngineStatus:
    state: EngineState
    vi2en_installed: bool
    en2vi_installed: bool
    loaded_directions: tuple[str, ...]
    active_translations: int
    error: str = ""


_VI_DIACRITICS = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
    r"ùúủũụưừứửữựỳýỷỹỵđ]",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-zÀ-ỹĐđ]+", re.UNICODE)
_VI_COMMON_WORDS = {
    "anh",
    "ban",
    "biet",
    "cach",
    "can",
    "cho",
    "chung",
    "co",
    "cua",
    "dang",
    "day",
    "de",
    "den",
    "dich",
    "duoc",
    "gi",
    "hoc",
    "khong",
    "khi",
    "la",
    "lam",
    "mot",
    "nay",
    "nguoi",
    "nhung",
    "noi",
    "phai",
    "sao",
    "tai",
    "the",
    "thi",
    "toi",
    "trang",
    "tren",
    "tu",
    "va",
    "van",
    "viet",
    "voi",
    "xin",
}
_ACCENTLESS_VI_MAP = {
    "anh": "anh",
    "ban": "bạn",
    "biet": "biết",
    "cach": "cách",
    "can": "cần",
    "cho": "cho",
    "chung": "chúng",
    "co": "có",
    "cong": "công",
    "cua": "của",
    "dang": "đang",
    "day": "đây",
    "de": "để",
    "den": "đến",
    "dich": "dịch",
    "duoc": "được",
    "gi": "gì",
    "gio": "giờ",
    "hoc": "học",
    "khong": "không",
    "khi": "khi",
    "la": "là",
    "lam": "làm",
    "mot": "một",
    "muon": "muốn",
    "nay": "này",
    "nguoi": "người",
    "nhung": "nhưng",
    "noi": "nội",
    "ngoai": "ngoại",
    "phai": "phải",
    "sao": "sao",
    "tai": "tại",
    "the": "thế",
    "thi": "thì",
    "thu": "thử",
    "toi": "tôi",
    "trang": "trang",
    "tren": "trên",
    "tieng": "tiếng",
    "tu": "từ",
    "va": "và",
    "van": "vẫn",
    "viet": "Việt",
    "voi": "với",
    "xin": "xin",
}
_PROTECTED_RE = re.compile(
    r"https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|"
    r"\{\{[^{}]+\}\}|\{[^{}]+\}|%\([^)]+\)[a-zA-Z]|%[sdif]|`[^`]+`"
)
_EMBEDDED_ENGLISH_TECH_RE = re.compile(
    r"(?<![\w-])(?:select-all|right-click|hotkey|clipboard|browser|copy|paste|cut|OCR|URL)(?![\w-])",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r".+?(?:[.!?。！？]+(?=\s+|$)|(?=\n+)|$)", re.DOTALL)


class LightweightSentencizer:
    """Small sentence splitter for short hotkey selections without Torch/Stanza."""

    max_chunk_chars = 420

    @classmethod
    def _split_long_chunk(cls, text: str) -> list[str]:
        if len(text) <= cls.max_chunk_chars:
            return [text]
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0
        for word in words:
            added = len(word) + (1 if current else 0)
            if current and current_length + added > cls.max_chunk_chars:
                chunks.append(" ".join(current))
                current = [word]
                current_length = len(word)
            else:
                current.append(word)
                current_length += added
        if current:
            chunks.append(" ".join(current))
        return chunks or [text]

    def split_sentences(self, text: str) -> list[str]:
        sentences: list[str] = []
        for match in _SENTENCE_RE.finditer(text.strip()):
            sentence = match.group(0).strip()
            if sentence:
                sentences.extend(self._split_long_chunk(sentence))
        return sentences or ([text] if text else [])


def _prepare_lightweight_argos_imports() -> None:
    """Avoid importing large optional SBD stacks that Vitra doesn't execute."""
    if "stanza" not in sys.modules:
        stanza_stub = types.ModuleType("stanza")

        class UnsupportedPipeline:
            def __init__(self, *_args, **_kwargs) -> None:
                raise RuntimeError("Vitra uses its lightweight sentence splitter")

        stanza_stub.Pipeline = UnsupportedPipeline  # type: ignore[attr-defined]
        sys.modules["stanza"] = stanza_stub
    # Argos treats a failed SpaCy import as an optional dependency. None is the
    # documented import-system sentinel for a deliberately unavailable module.
    sys.modules.setdefault("spacy", None)  # type: ignore[arg-type]


def _replace_argos_sentencizers(translator: Any) -> bool:
    """Replace sentencizers inside Argos cache/composite translation wrappers."""
    pending = [translator]
    visited: set[int] = set()
    replaced = False
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in visited:
            continue
        visited.add(identity)
        if hasattr(current, "sentencizer"):
            current.sentencizer = LightweightSentencizer()
            replaced = True
        for attribute in ("underlying", "t1", "t2"):
            nested = getattr(current, attribute, None)
            if nested is not None:
                pending.append(nested)
    return replaced


class TranslationService:
    def __init__(self) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._translators: dict[Direction, TranslatorProtocol] = {}
        self._state = EngineState.UNLOADED
        self._active_translations = 0
        self._last_used = time.monotonic()
        self._last_error = ""
        self._installed_cache: tuple[bool, bool] | None = None
        self._status_callback: Callable[[], None] | None = None
        self._shutdown_event = threading.Event()
        self._unload_thread = threading.Thread(
            target=self._auto_unload_loop,
            name="vitra-model-unloader",
            daemon=True,
        )
        self._unload_thread.start()

    def set_status_callback(self, callback: Callable[[], None] | None) -> None:
        with self._condition:
            self._status_callback = callback

    def _notify_status(self) -> None:
        callback = self._status_callback
        if callback:
            try:
                callback()
            except Exception:
                LOGGER.exception("Status callback failed")

    def check_installed_packages(self, refresh: bool = False) -> tuple[bool, bool]:
        with self._condition:
            if self._installed_cache is not None and not refresh:
                return self._installed_cache
        try:
            import argostranslate.package

            packages = argostranslate.package.get_installed_packages()
            result = (
                any(pkg.from_code == "vi" and pkg.to_code == "en" for pkg in packages),
                any(pkg.from_code == "en" and pkg.to_code == "vi" for pkg in packages),
            )
        except Exception:
            LOGGER.exception("Unable to inspect installed Argos packages")
            result = (False, False)
        with self._condition:
            self._installed_cache = result
        return result

    def status(self, refresh_disk: bool = False) -> EngineStatus:
        vi2en, en2vi = self.check_installed_packages(refresh=refresh_disk)
        with self._condition:
            return EngineStatus(
                state=self._state,
                vi2en_installed=vi2en,
                en2vi_installed=en2vi,
                loaded_directions=tuple(direction.value for direction in self._translators),
                active_translations=self._active_translations,
                error=self._last_error,
            )

    def _load_direction(self, direction: Direction) -> None:
        with self._condition:
            if direction in self._translators:
                self._last_used = time.monotonic()
                return
            if self._state is EngineState.INSTALLING:
                raise RuntimeError("Mô hình đang được cài đặt")
            while self._state is EngineState.LOADING:
                self._condition.wait(timeout=30)
                if direction in self._translators:
                    return
            self._state = EngineState.LOADING
            self._last_error = ""
        self._notify_status()

        try:
            _prepare_lightweight_argos_imports()
            import argostranslate.translate

            source_code, target_code = direction.codes
            installed = argostranslate.translate.get_installed_languages()
            source = next((language for language in installed if language.code == source_code), None)
            target = next((language for language in installed if language.code == target_code), None)
            if source is None or target is None:
                raise RuntimeError(f"Thiếu model {source_code.upper()}→{target_code.upper()}")
            translator = source.get_translation(target)
            if translator is None:
                raise RuntimeError(f"Không thể nạp model {source_code.upper()}→{target_code.upper()}")
            # PackageTranslation constructs a Stanza sentencizer from legacy model
            # metadata. Replace it before first inference with the small splitter.
            if not _replace_argos_sentencizers(translator):
                raise RuntimeError("Không thể cấu hình bộ tách câu cho model Argos")

            with self._condition:
                self._translators[direction] = translator
                self._state = EngineState.READY
                self._last_used = time.monotonic()
                self._condition.notify_all()
            LOGGER.info("Loaded translation direction %s", direction.value)
        except Exception as exc:
            with self._condition:
                self._state = EngineState.ERROR
                self._last_error = str(exc)
                self._condition.notify_all()
            LOGGER.exception("Unable to load translation direction %s", direction.value)
            raise
        finally:
            self._notify_status()

    def preload_async(self) -> None:
        mode = config.config.get("performance_mode", "balanced")
        if mode == "low_memory":
            return

        def preload() -> None:
            preferred = config.config.get("direction", "auto")
            directions = (
                [Direction(preferred)]
                if preferred in {Direction.VI_EN.value, Direction.EN_VI.value}
                else [Direction.VI_EN, Direction.EN_VI]
            )
            for direction in directions:
                try:
                    self._load_direction(direction)
                except Exception:
                    break

        threading.Thread(target=preload, name="vitra-model-preloader", daemon=True).start()

    @staticmethod
    def detect_direction(text: str) -> Direction:
        if _VI_DIACRITICS.search(text):
            return Direction.VI_EN
        words = [word.lower() for word in _WORD_RE.findall(text)]
        if not words:
            return Direction.EN_VI
        vi_hits = sum(word in _VI_COMMON_WORDS for word in words)
        if vi_hits >= 2 or (vi_hits == 1 and len(words) <= 4):
            return Direction.VI_EN
        return Direction.EN_VI

    @staticmethod
    def normalize_accentless_vietnamese(text: str) -> str:
        if _VI_DIACRITICS.search(text):
            return text

        def replace_word(match: re.Match[str]) -> str:
            original = match.group(0)
            replacement = _ACCENTLESS_VI_MAP.get(original.lower(), original)
            if original.isupper():
                return replacement.upper()
            if original[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        return _WORD_RE.sub(replace_word, text)

    @staticmethod
    def _protect_segments(
        text: str,
        preserve_embedded_english: bool = False,
    ) -> tuple[str, dict[str, str]]:
        replacements: dict[str, str] = {}

        def reserve(value: str) -> str:
            token = f"VZXQ{len(replacements)}QXZV"
            replacements[token] = value
            return token

        glossary = config.config.get("glossary", {})
        protected = text
        if isinstance(glossary, dict):
            for source in sorted(glossary, key=len, reverse=True):
                target = str(glossary[source])
                pattern = re.compile(re.escape(str(source)), re.IGNORECASE)

                def replace_glossary(_match: re.Match[str], value: str = target) -> str:
                    return reserve(value)

                protected = pattern.sub(replace_glossary, protected)

        if preserve_embedded_english:
            protected = _EMBEDDED_ENGLISH_TECH_RE.sub(lambda match: reserve(match.group(0)), protected)

        def replace_protected(match: re.Match[str]) -> str:
            return reserve(match.group(0))

        protected = _PROTECTED_RE.sub(replace_protected, protected)
        return protected, replacements

    @staticmethod
    def _restore_segments(text: str, replacements: dict[str, str]) -> str:
        restored = text
        for token, value in replacements.items():

            def restore_value(_match: re.Match[str], item: str = value) -> str:
                return item

            restored = re.sub(re.escape(token), restore_value, restored, flags=re.I)
        return restored

    def translate(self, text: str, direction: str | Direction | None = None) -> str:
        if not text or not text.strip():
            return text

        if direction is None or direction == "auto":
            configured = config.config.get("direction", "auto")
            resolved = (
                Direction(configured)
                if configured in {Direction.VI_EN.value, Direction.EN_VI.value}
                else self.detect_direction(text)
            )
        else:
            resolved = direction if isinstance(direction, Direction) else Direction(direction)

        self._load_direction(resolved)
        with self._condition:
            translator = self._translators[resolved]
            self._active_translations += 1
            self._state = EngineState.TRANSLATING
            self._last_used = time.monotonic()
        self._notify_status()

        source_text = text
        if resolved is Direction.VI_EN and config.config.get("normalize_accentless_vietnamese", True):
            source_text = self.normalize_accentless_vietnamese(source_text)
        protected, replacements = self._protect_segments(
            source_text,
            preserve_embedded_english=resolved is Direction.VI_EN,
        )
        try:
            translated = translator.translate(protected)
            return self._restore_segments(str(translated), replacements)
        finally:
            with self._condition:
                self._active_translations -= 1
                self._last_used = time.monotonic()
                self._state = EngineState.READY if self._translators else EngineState.UNLOADED
                self._condition.notify_all()
            self._notify_status()

    def unload(self, force: bool = False) -> bool:
        with self._condition:
            if self._active_translations and not force:
                return False
            self._translators.clear()
            self._state = EngineState.UNLOADED
            self._last_error = ""
            self._condition.notify_all()
        LOGGER.info("Translation models unloaded")
        self._notify_status()
        return True

    def _auto_unload_loop(self) -> None:
        while not self._shutdown_event.wait(30):
            mode = config.config.get("performance_mode", "balanced")
            if mode == "performance":
                continue
            idle_limit = max(1, int(config.config.get("auto_unload_minutes", 30))) * 60
            with self._condition:
                should_unload = (
                    bool(self._translators)
                    and self._active_translations == 0
                    and time.monotonic() - self._last_used >= idle_limit
                )
            if should_unload:
                self.unload()

    def _set_installing(self, installing: bool, error: str = "") -> None:
        with self._condition:
            self._state = EngineState.INSTALLING if installing else EngineState.UNLOADED
            self._last_error = error
            self._installed_cache = None
            self._condition.notify_all()
        self._notify_status()

    def download_models(
        self,
        on_status: Callable[[str], None],
        on_progress: Callable[[float], None],
        on_complete: Callable[[bool, str], None],
    ) -> None:
        def worker() -> None:
            self._set_installing(True)
            paths: list[str] = []
            try:
                import argostranslate.package

                on_status("Đang tải danh mục model…")
                argostranslate.package.update_package_index()
                available = argostranslate.package.get_available_packages()
                packages = [
                    next((p for p in available if p.from_code == "vi" and p.to_code == "en"), None),
                    next((p for p in available if p.from_code == "en" and p.to_code == "vi"), None),
                ]
                if any(package is None for package in packages):
                    raise RuntimeError("Không tìm thấy đủ model VI↔EN")

                for index, package in enumerate(packages):
                    assert package is not None
                    start, end = index * 50.0, (index + 1) * 50.0
                    on_status(f"Đang tải {package.from_code.upper()}→{package.to_code.upper()}…")
                    fd, path = tempfile.mkstemp(suffix=".argosmodel")
                    os.close(fd)
                    paths.append(path)

                    def report(
                        count: int,
                        block_size: int,
                        total_size: int,
                        range_start: float = start,
                        range_end: float = end,
                    ) -> None:
                        fraction = min(1.0, count * block_size / total_size) if total_size > 0 else 0
                        on_progress(range_start + (range_end - range_start) * fraction)

                    urllib.request.urlretrieve(package.links[0], path, report)
                    argostranslate.package.install_from_path(path)

                self.unload(force=True)
                self.check_installed_packages(refresh=True)
                on_progress(100)
                on_status("Đã cài đầy đủ model VI↔EN")
                on_complete(True, "Thành công")
            except Exception as exc:
                LOGGER.exception("Model download/install failed")
                on_status(f"Lỗi: {str(exc)[:100]}")
                on_complete(False, str(exc))
            finally:
                for path in paths:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                self._set_installing(False)
                if config.config.get("performance_mode") != "low_memory":
                    self.preload_async()

        threading.Thread(target=worker, name="vitra-model-download", daemon=True).start()

    def install_local(
        self,
        file_path: str,
        on_status: Callable[[str], None],
        on_complete: Callable[[bool, str], None],
    ) -> None:
        def worker() -> None:
            self._set_installing(True)
            try:
                import argostranslate.package

                on_status("Đang kiểm tra và cài model…")
                argostranslate.package.install_from_path(file_path)
                self.unload(force=True)
                vi2en, en2vi = self.check_installed_packages(refresh=True)
                message = (
                    f"Đã cài model. VI→EN: {'có' if vi2en else 'thiếu'}, EN→VI: {'có' if en2vi else 'thiếu'}"
                )
                on_status(message)
                on_complete(True, message)
            except Exception as exc:
                LOGGER.exception("Local model install failed")
                on_status(f"Lỗi: {str(exc)[:100]}")
                on_complete(False, str(exc))
            finally:
                self._set_installing(False)

        threading.Thread(target=worker, name="vitra-model-install", daemon=True).start()

    def shutdown(self) -> None:
        self._shutdown_event.set()
        self.unload(force=True)


SERVICE = TranslationService()


def set_status_callback(callback: Callable[[], None] | None) -> None:
    SERVICE.set_status_callback(callback)


def check_installed_packages_on_disk() -> tuple[bool, bool]:
    return SERVICE.check_installed_packages(refresh=True)


def check_models_installed_on_disk() -> bool:
    return all(check_installed_packages_on_disk())


def get_status() -> dict[str, object]:
    status = SERVICE.status()
    return {
        "vi2en": status.vi2en_installed,
        "en2vi": status.en2vi_installed,
        "state": status.state.value,
        "is_loading": status.state in {EngineState.LOADING, EngineState.INSTALLING},
        "loaded_directions": status.loaded_directions,
        "active_translations": status.active_translations,
        "error": status.error,
    }


def load_translation_model() -> bool:
    try:
        SERVICE._load_direction(Direction.VI_EN)
        SERVICE._load_direction(Direction.EN_VI)
        return True
    except Exception:
        return False


def download_model(on_status_update, on_progress_update, on_complete) -> None:
    SERVICE.download_models(on_status_update, on_progress_update, on_complete)


def install_from_local_file(file_path, on_status_update, on_complete) -> None:
    SERVICE.install_local(file_path, on_status_update, on_complete)


def is_vietnamese(text: str) -> bool:
    return SERVICE.detect_direction(text) is Direction.VI_EN


def translate_text(text: str, direction: str | None = None) -> str:
    return SERVICE.translate(text, direction)


def preload_async() -> None:
    SERVICE.preload_async()


def shutdown() -> None:
    SERVICE.shutdown()
