# Third-party component inventory

The generated CycloneDX SBOM is the complete selected Python-environment inventory, including transitives. The repository does not assign a new open-source license to the user's project or change third-party licenses. Competitor snapshots remain research evidence only; no competitor implementation was incorporated into the backend.

Installed-package metadata observed during this delivery: FastAPI MIT; SQLAlchemy MIT; Temporal Python SDK MIT; pyHanko MIT; pypdf BSD-3-Clause; ReportLab's BSD license; pypdfium2 BSD-3-Clause/Apache-2.0 plus dependency notices. ReportLab's bundled Vera font includes its own font license; preserve it when distributing embedded font assets or package copies. These metadata observations do not replace review of all dependency/binary/weight notices for distribution.

OCR code and weight candidates must retain the upstream PaddleOCR/PaddlePaddle/model notices. The compatibility probe records engine versions and model hashes; it does not grant rights or claim a completed production license approval. Keycloak, Grafana, PostgreSQL, Temporal CLI, Moto, Mailpit, collector, Prometheus, Jaeger, Python and distroless images each retain their upstream terms. Image references and source package SBOMs are part of release evidence.

Before real deployment/distribution, the designated owner reviews code, inference weights, fonts, system-library copies, container notices and any managed-service terms for the intended use. Do not infer that a government project is categorically incompatible with a particular license or that using an image automatically satisfies all notice obligations.
# Phase 4 additions

Runtime PDF/image inspection adds pypdf (BSD), pypdfium2/PDFium (their bundled BSD/Apache third-party notices), and Pillow (HPND and bundled third-party notices). Exact artifacts and hashes are pinned in `backend/uv.lock`; retain each installed distribution's license notices when distributing images.

The parser image copies ffprobe 9.0.2 from `mwader/static-ffmpeg` at digest `sha256:35a513d9b673367ef50bd4e880ac6b701d3fa2964b58bb0b2064d8d99892b9d9`. Its own `-L` output identifies **GPL-3.0-or-later**, built with `--enable-gpl --enable-version3`. ClamAV runs as a separate GPL-licensed service from its pinned upstream image. Public image distribution must include the applicable notices and corresponding-source provision for the exact builds; the gated release must not assume an LGPL-only FFmpeg build. Source/build recipe: https://github.com/wader/static-ffmpeg. Upstream FFmpeg license: https://ffmpeg.org/legal.html. No external image release has been performed by this implementation.

`backend/fixtures/synthetic-video.base64` is a generated one-second blue 32×32 test clip (no external footage), produced with the pinned FFmpeg build. It supports container inspection acceptance and makes no video-inference claim.

