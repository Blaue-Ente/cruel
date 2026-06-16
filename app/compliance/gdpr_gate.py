"""GDPR Privacy Gate — PII classification, masking, and storage filtering."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from app.compliance.layers import PrivacyLayer, get_layer_profile

PIIType = Literal["email", "phone", "address", "personal_name", "iban"]

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")

PERSONAL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "gmx.de", "gmx.net", "web.de", "t-online.de", "icloud.com", "proton.me",
    "protonmail.com", "mail.ru", "abv.bg", "mail.bg",
}

BUSINESS_PREFIXES = {"info", "contact", "sales", "support", "office", "hello", "team", "admin", "service"}


def scan_for_pii(text: str) -> list[dict[str, Any]]:
    findings = []
    for m in EMAIL_RE.finditer(text):
        email = m.group()
        findings.append({
            "type": "email",
            "value": email,
            "classification": _classify_email(email),
            "position": m.start(),
        })
    for m in PHONE_RE.finditer(text):
        phone = m.group()
        if len(re.sub(r"\D", "", phone)) >= 8:
            findings.append({
                "type": "phone",
                "value": phone,
                "classification": "unknown",
                "position": m.start(),
            })
    for m in IBAN_RE.finditer(text):
        findings.append({
            "type": "iban",
            "value": m.group(),
            "classification": "personal_private",
            "position": m.start(),
        })
    return findings


def _classify_email(email: str) -> str:
    local, _, domain = email.lower().partition("@")
    if domain in PERSONAL_DOMAINS:
        return "personal_private"
    prefix = local.split("+")[0].split(".")[0]
    if prefix in BUSINESS_PREFIXES:
        return "business_public"
    if domain.endswith((".gov", ".edu", ".bg", ".de")) and prefix in BUSINESS_PREFIXES:
        return "business_public"
    if "." in local and len(local) > 20:
        return "business_public"
    return "unknown"


def _mask_value(value: str, pii_type: str) -> str:
    if pii_type == "email":
        local, _, domain = value.partition("@")
        return f"{local[0]}***@{domain}" if local else "***"
    if pii_type == "phone":
        digits = re.sub(r"\D", "", value)
        return f"***{digits[-4:]}" if len(digits) >= 4 else "***"
    if pii_type == "iban":
        return value[:4] + "***" + value[-4:]
    return "***"


def apply_gdpr_gate(
    data: Any,
    layer: PrivacyLayer | str,
    context: str = "",
) -> dict[str, Any]:
    """
    Filter/mask PII in data based on Privacy Layer profile.
    Returns sanitized data + audit report.
    """
    profile = get_layer_profile(layer)
    if not profile.get("gdpr_strict") and not profile.get("gdpr_mask_personal"):
        return {
            "data": data,
            "gdpr_applied": False,
            "layer": profile["layer"],
            "summary": "GDPR gate skipped — layer does not require filtering.",
            "findings": [],
            "masked_count": 0,
            "dropped_count": 0,
            "kept_count": 0,
        }

    text = _to_text(data)
    findings = scan_for_pii(text)
    masked_count = 0
    dropped_count = 0
    kept_count = 0
    actions: list[dict] = []

    sanitized = text
    for f in sorted(findings, key=lambda x: x["position"], reverse=True):
        classification = f["classification"]
        action = "keep"

        if profile.get("require_business_email_only") and f["type"] == "email":
            if classification == "personal_private":
                action = "mask"
            elif classification == "unknown":
                action = "mask"
            else:
                action = "keep"
        elif profile.get("gdpr_strict"):
            if classification == "personal_private" or f["type"] in ("iban", "phone"):
                action = "mask" if profile.get("gdpr_mask_personal") else "drop"
            elif classification == "business_public":
                action = "keep"
            else:
                action = "mask"
        elif profile.get("gdpr_mask_personal") and classification == "personal_private":
            action = "mask"

        if action == "mask":
            masked = _mask_value(f["value"], f["type"])
            sanitized = sanitized.replace(f["value"], masked)
            masked_count += 1
        elif action == "drop":
            sanitized = sanitized.replace(f["value"], "[REDACTED]")
            dropped_count += 1
        else:
            kept_count += 1

        actions.append({**f, "action": action})

    if not profile.get("store_pii") and isinstance(data, dict):
        result_data = _sanitize_dict(data, actions)
    elif isinstance(data, str):
        result_data = sanitized
    else:
        result_data = _rebuild_data(data, sanitized)

    summary = _build_summary(findings, actions, masked_count, dropped_count, kept_count, profile)

    return {
        "data": result_data,
        "gdpr_applied": True,
        "layer": profile["layer"],
        "summary": summary,
        "findings": actions,
        "masked_count": masked_count,
        "dropped_count": dropped_count,
        "kept_count": kept_count,
    }


def _build_summary(
    findings: list,
    actions: list,
    masked: int,
    dropped: int,
    kept: int,
    profile: dict,
) -> str:
    total = len(findings)
    if total == 0:
        return "Не открих лични данни (PII) в извлечения текст."
    parts = [f"Намерих {total} PII елемента."]
    if kept:
        parts.append(f"{kept} запазени (публични бизнес контакти).")
    if masked:
        parts.append(f"{masked} маскирани според {profile['name_bg']}.")
    if dropped:
        parts.append(f"{dropped} премахнати — не са запазени в базата.")
    if profile.get("require_business_email_only"):
        parts.append("Само официални бизнес имейли са разрешени за съхранение.")
    return " ".join(parts)


def _to_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        import json
        return json.dumps(data, ensure_ascii=False)
    return str(data)


def _rebuild_data(original: Any, sanitized_text: str) -> Any:
    if isinstance(original, str):
        return sanitized_text
    return original


def _sanitize_dict(data: dict, actions: list) -> dict:
    import copy
    result = copy.deepcopy(data)
    for action in actions:
        if action["action"] in ("mask", "drop") and "value" in action:
            _deep_replace(result, action["value"], "[REDACTED]" if action["action"] == "drop" else _mask_value(action["value"], action["type"]))
    return result


def _deep_replace(obj: Any, old: str, new: str) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and old in v:
                obj[k] = v.replace(old, new)
            else:
                _deep_replace(v, old, new)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and old in item:
                obj[i] = item.replace(old, new)
            else:
                _deep_replace(item, old, new)
