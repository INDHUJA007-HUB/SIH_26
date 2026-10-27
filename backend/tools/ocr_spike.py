"""Single synthetic English OCR compatibility check; no general accuracy claim."""

import hashlib
import json
import os
from importlib.metadata import version
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from paddleocr import PaddleOCR  # noqa: E402

root = Path(__file__).resolve().parents[2]
image = root / "artifacts/spikes/render.png"
if not image.is_file():
    raise SystemExit("Run tools/run_spikes.py before this compatibility check")
pipeline = PaddleOCR(
    device="cpu",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="en_PP-OCRv5_mobile_rec",
    enable_mkldnn=False,
)
results = list(pipeline.predict(str(image)))
texts = [str(text) for result in results for text in result["rec_texts"]]
passed = "420" in " ".join(texts)
report = {
    "status": "PASS" if passed else "FAILED",
    "scope": "ONE_SYNTHETIC_ENGLISH_IMAGE",
    "paddleocr": version("paddleocr"),
    "paddlepaddle": version("paddlepaddle"),
    "detection_model": "PP-OCRv5_mobile_det",
    "recognition_model": "en_PP-OCRv5_mobile_rec",
    "expected_token_found": passed,
    "regional_language_quality": "NOT_MEASURED",
}
model_root = Path.home() / ".paddlex/official_models"
report["model_file_sha256"] = {
    str(path.relative_to(model_root)): hashlib.sha256(path.read_bytes()).hexdigest()
    for model in ("PP-OCRv5_mobile_det", "en_PP-OCRv5_mobile_rec")
    for path in (model_root / model).rglob("*")
    if path.is_file() and path.suffix in {".json", ".pdiparams", ".yml", ".yaml"}
}
(root / "artifacts/spikes/ocr.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
if not passed:
    raise SystemExit(1)
