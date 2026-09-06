from pathlib import Path

from app.config import ensure_writable_dir, is_serverless


def test_ensure_writable_dir_falls_back_when_mkdir_fails(tmp_path, monkeypatch):
    target = tmp_path / "blocked-data"
    orig_mkdir = Path.mkdir

    def mkdir_maybe(self, *args, **kwargs):
        if Path(self) == target:
            raise PermissionError("read-only filesystem")
        return orig_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir_maybe)
    got = ensure_writable_dir(target)
    assert got != target
    (got / "probe.txt").write_text("ok", encoding="utf-8")


def test_serverless_flag_reads_vercel_env(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("LAMBDA_TASK_ROOT", raising=False)
    assert is_serverless() is False
    monkeypatch.setenv("VERCEL", "1")
    assert is_serverless() is True


def test_health_reports_runtime(client):
    r = client.get("/health")
    assert r.status_code == 200
    runtime = r.json()["runtime"]
    assert runtime["serverless"] is False
    assert runtime["data_dir"]
