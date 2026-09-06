from __future__ import annotations

from app.compliance.gdpr_gate import apply_gdpr_gate, scan_for_pii
from app.preferences import export_workspace, import_workspace, load_preferences, save_preferences


def test_gdpr_masks_personal_email_on_de_fortress():
    text = "Contact ivan.petrov@gmail.com for pricing"
    findings = scan_for_pii(text)
    assert any(f["type"] == "email" for f in findings)
    gated = apply_gdpr_gate(text, "de_fortress")
    assert gated["gdpr_applied"] is True
    assert "gmail.com" in str(gated["data"])
    assert "ivan.petrov@gmail.com" not in str(gated["data"])


def test_preferences_roundtrip():
    saved = save_preferences({"theme": "light", "locale": "bg", "country": "BG"})
    assert saved["theme"] == "light"
    loaded = load_preferences()
    assert loaded["locale"] == "bg"
    bundle = export_workspace()
    assert bundle["format"] == "argoscout.workspace"
    imported = import_workspace({"preferences": {"theme": "dark"}})
    assert imported["theme"] == "dark"
    assert imported["locale"] == "bg"
