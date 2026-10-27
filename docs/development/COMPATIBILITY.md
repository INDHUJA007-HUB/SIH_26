# Compatibility spikes

The executable probes use synthetic material only. Results are recorded under ignored `artifacts/spikes/`; the final verification summary records executed outcomes and selected versions.

`uv run --project backend python backend/tools/run_spikes.py --s3` verifies digital PDF text extraction, word geometry, bundled Vera font embedding/rendering, synthetic self-signed PDF signature integrity and local simulator bucket/version setup. Trust is limited to the generated test root; it is not government issuer authentication or revocation coverage.

The isolated CPU OCR probe was selected after an actual Windows/Python 3.12 run: PaddleOCR 3.7.0, PaddlePaddle 3.3.1, PP-OCRv5_mobile_det and en_PP-OCRv5_mobile_rec. The API image does not contain this heavy inference stack. Reproduce with the hash-locked platform requirements under backend/spikes/ or the exact top-level versions:

```powershell
uv run --no-project --python 3.12 --with paddleocr==3.7.0 --with paddlepaddle==3.3.1 python backend/tools/ocr_spike.py
```

Weights are downloaded from the tool's official model sources into the user's model cache; the probe records hashes of model files. Compare hashes before calling a later run the same model version. One synthetic English image containing a known number proves import/inference compatibility only; accuracy, regional-language support and representative application performance remain unmeasured.

Temporal SDK/server and worker are checked by `workflow-smoke` against the development server. S3 checks target Moto on loopback only. Real AWS signature validation, IAM, retention locks, region terms and production workflow persistence require the later cloud integration/recovery qualification.

The source research's fonts, coordinate expectations, signatures, date/identity distinctions and unknown handling remain requirements for later implementation; these small probes do not implement the full extraction/verification pipeline.
