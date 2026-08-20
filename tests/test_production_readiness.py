from pathlib import Path
from uuid import uuid4

from docx import Document
from fastapi.testclient import TestClient

from controlcheck.api import create_app
from controlcheck.storage_s3 import S3FileStorage


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _docx_text(path: Path) -> str:
    document = Document(path)
    blocks = [paragraph.text for paragraph in document.paragraphs]
    blocks.extend(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    return "\n".join(blocks)


def test_health_live_probe():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "live"


def test_health_ready_probe_offline_mode():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_s3_storage_initialization():
    storage = S3FileStorage(bucket="my-test-bucket", region="ap-southeast-1")
    assert storage.bucket == "my-test-bucket"
    assert storage.region == "ap-southeast-1"


def test_prd_v08_records_production_readiness():
    text = _docx_text(DOCS / "ControlCheck_AI_PRD_v0.8.docx")
    assert "Product Requirements Document v0.8" in text
    assert "Phase 7 Production Readiness Alignment" in text
    assert "Change Log v0.8" in text
    assert "Multi-stage production Dockerfile" in text
