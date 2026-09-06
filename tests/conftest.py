"""ArgosScout test suite — security, copilot routing, preferences, GDPR."""

import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="argoscout-test-")
os.environ["DATA_DIR"] = _TMP
os.environ["DATABASE_PATH"] = str(Path(_TMP) / "test.db")
os.environ["PREFERENCES_PATH"] = str(Path(_TMP) / "preferences.json")
os.environ["PREDICTIVE_ENABLED"] = "false"
os.environ["INBOX_ENABLED"] = "false"
os.environ["ADMIN_SECRET"] = "test-admin-secret-xyz"
os.environ["ALLOW_INSECURE_DEFAULTS"] = "true"
os.environ["SSRF_ALLOW_PRIVATE"] = "false"
os.environ["RATE_LIMIT_ANONYMOUS"] = "1000"
os.environ["RATE_LIMIT_AUTHENTICATED"] = "1000"
os.environ["LLM_PROVIDER"] = "rule"

import pytest
from fastapi.testclient import TestClient

from app.store import create_api_key, init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def api_key():
    init_db()
    return create_api_key("test")["key"]
