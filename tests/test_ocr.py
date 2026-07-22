from __future__ import annotations

from PIL import Image

from core.ocr import OCRService


def test_ocr_filters_low_confidence_and_orders_lines() -> None:
    class FakeEngine:
        def __call__(self, _image):
            return (
                [
                    [[[0, 30], [80, 30], [80, 45], [0, 45]], "second", 0.9],
                    [[[0, 5], [80, 5], [80, 20], [0, 20]], "first", 0.95],
                    [[[0, 50], [80, 50], [80, 60], [0, 60]], "noise", 0.1],
                ],
                0.01,
            )

    service = OCRService()
    service._engine = FakeEngine()
    result = service.extract(Image.new("RGB", (100, 70), "white"))
    assert result is not None
    assert result.text == "first\nsecond"
    assert result.line_count == 2
