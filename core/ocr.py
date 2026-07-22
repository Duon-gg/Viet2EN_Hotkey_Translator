"""Lazy offline OCR powered by RapidOCR/ONNX Runtime."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from utils import config

LOGGER = logging.getLogger("vitra.ocr")


@dataclass(frozen=True)
class OCRResult:
    text: str
    average_confidence: float
    line_count: int


class OCRService:
    def __init__(self) -> None:
        self._engine: Any = None
        self._lock = threading.RLock()

    @property
    def available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401

            return True
        except ImportError:
            return False

    def _get_engine(self) -> Any:
        with self._lock:
            if self._engine is None:
                from rapidocr_onnxruntime import RapidOCR

                self._engine = RapidOCR()
            return self._engine

    def extract(self, image: Any) -> OCRResult | None:
        if not config.config.get("ocr_enabled", True):
            return None
        if self._engine is None and not self.available:
            return None
        try:
            import numpy as np

            engine = self._get_engine()
            result, _elapsed = engine(np.asarray(image.convert("RGB")))
            if not result:
                return None

            lines: list[tuple[float, float, str, float]] = []
            minimum = float(config.config.get("ocr_min_confidence", 0.45))
            for item in result:
                if len(item) < 3:
                    continue
                box, text, confidence = item[0], str(item[1]).strip(), float(item[2])
                if not text or confidence < minimum:
                    continue
                try:
                    y = min(float(point[1]) for point in box)
                    x = min(float(point[0]) for point in box)
                except Exception:
                    y, x = float(len(lines)), 0.0
                lines.append((y, x, text, confidence))

            if not lines:
                return None
            lines.sort(key=lambda item: (round(item[0] / 12), item[1]))
            return OCRResult(
                text="\n".join(item[2] for item in lines),
                average_confidence=sum(item[3] for item in lines) / len(lines),
                line_count=len(lines),
            )
        except Exception:
            LOGGER.exception("OCR extraction failed")
            return None

    def unload(self) -> None:
        with self._lock:
            self._engine = None


SERVICE = OCRService()
