"""Executable PDF/font/signature/Temporal/S3 compatibility probes, not accuracy benchmarks."""

import argparse
import io
import json
from datetime import UTC, datetime, timedelta
from importlib.metadata import version

import pdfplumber
import pypdfium2
import reportlab
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from workbench.platform.config import PROJECT_ROOT, Settings
from workbench.tools import seed_buckets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3", action="store_true")
    args = parser.parse_args()
    destination = PROJECT_ROOT / "artifacts/spikes"
    destination.mkdir(parents=True, exist_ok=True)
    output = io.BytesIO()
    font = __import__("pathlib").Path(reportlab.__file__).parent / "fonts/Vera.ttf"
    pdfmetrics.registerFont(TTFont("CompatibilityVera", str(font)))
    canvas = Canvas(output)
    canvas.setFont("CompatibilityVera", 14)
    canvas.drawString(50, 760, "SYNTHETIC COMPATIBILITY FIXTURE 420 Mbps")
    canvas.save()
    pdf = output.getvalue()
    assert "420 Mbps" in PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        assert document.pages[0].extract_words()
    rendered = pypdfium2.PdfDocument(pdf)
    rendered[0].render(scale=1).to_pil().save(destination / "render.png")
    rendered.close()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic Spike Signer")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    private_path, cert_path = destination / "temporary-key.pem", destination / "temporary-cert.pem"
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    signer = signers.SimpleSigner.load(str(private_path), str(cert_path))
    if signer is None:
        raise RuntimeError("Synthetic signer load failed")
    signed = signers.sign_pdf(
        IncrementalPdfFileWriter(io.BytesIO(pdf)),
        signature_meta=signers.PdfSignatureMetadata(field_name="CompatibilitySignature"),
        signer=signer,
    )
    reader = PdfFileReader(io.BytesIO(signed.getvalue()))
    signature = validate_pdf_signature(
        reader.embedded_signatures[0],
        signer_validation_context=ValidationContext(
            trust_roots=[signer.signing_cert],
            allow_fetching=False,
        ),
    )
    assert signature.intact and signature.valid
    private_path.unlink()  # Only this generated, explicit temporary key is removed.
    result = {
        "scope": "SYNTHETIC_COMPATIBILITY_ONLY",
        "pdf_text": "PASS",
        "geometry": "PASS",
        "font_embedding_and_render": "PASS",
        "signature_integrity": "PASS",
        "signature_trust": "SELF_SIGNED_TEST_ROOT_ONLY_NOT_ISSUER_AUTHENTICATION",
        "ocr_quality": "NOT_MEASURED",
        "regional_language_support": "NOT_CLAIMED",
        "temporal_sdk": version("temporalio"),
        "versions": {
            name: version(name)
            for name in (
                "fastapi",
                "pydantic",
                "sqlalchemy",
                "pypdf",
                "pdfplumber",
                "pypdfium2",
                "reportlab",
                "pyhanko",
                "cryptography",
            )
        },
        "s3": seed_buckets(Settings()) if args.s3 else "NOT_RUN_REQUIRES_LOCAL_PLATFORM",
    }
    (destination / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
