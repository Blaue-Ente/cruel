"""Provocative scraping — active state interrogation via error messages."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.probe.ghost_cursor import human_click, human_type
from app.probe.pheromones import deposit
from app.providers import chat_complete

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

STOCK_PATTERNS = [
    r"(?:only|just|have|left|remaining|available|наличн|останал|имаме)\s*[:\s]*(\d+)",
    r"(\d+)\s*(?:in stock|available|left|remaining|бр\.|броя|налични)",
    r"(?:max|maximum|limit)\s*[:\s]*(\d+)",
    r"(\d+)\s*(?:items?|units?|pieces?|бр)",
]


def provocative_stock_probe(
    url: str,
    qty_selector: str = "input[name*='qty'], input[name*='quantity'], #quantity, .qty-input, input[type='number']",
    add_btn_selector: str = "button[name*='add'], .add-to-cart, [data-action='add-to-cart'], button:has-text('Add')",
    submit_selector: str = "button[type='submit'], .checkout-btn, button:has-text('Cart')",
    probe_qty: int = 9999,
) -> dict[str, Any]:
    """
    Add extreme quantity to cart, capture validation/error messages revealing real stock.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return _http_fallback_probe(url)

    messages = []
    extracted = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(1500)

            qty_el = page.query_selector(qty_selector)
            if qty_el:
                human_type(page, qty_selector, str(probe_qty))
                messages.append(f"Set quantity to {probe_qty}")
                if human_click(page, add_btn_selector):
                    messages.append("Clicked add-to-cart")
                    page.wait_for_timeout(2000)

            alerts = page.query_selector_all(".alert, .error, .warning, [role='alert'], .toast, .notification")
            for alert in alerts:
                text = alert.inner_text().strip()
                if text:
                    messages.append(f"Alert: {text}")
                    nums = _extract_numbers_from_text(text)
                    if nums:
                        extracted["stock_from_alert"] = nums

            body_text = page.inner_text("body")
            for pat in STOCK_PATTERNS:
                for m in re.finditer(pat, body_text, re.I):
                    extracted.setdefault("stock_hints", []).append(int(m.group(1)))

            browser.close()

        if extracted:
            deposit(url, "sweet", f"Stock data extracted: {extracted}", strength=2.0)

        return {
            "url": url,
            "success": bool(extracted),
            "method": "provocative_stock",
            "probe_qty": probe_qty,
            "messages": messages,
            "extracted": extracted,
        }
    except Exception as e:
        deposit(url, "poison", f"Provocative probe failed: {e}", strength=1.0)
        return {"url": url, "success": False, "method": "provocative_stock", "error": str(e)}


def _extract_numbers_from_text(text: str) -> list[int]:
    nums = []
    for pat in STOCK_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            try:
                nums.append(int(m.group(1)))
            except ValueError:
                pass
    return list(set(nums))


def _http_fallback_probe(url: str) -> dict[str, Any]:
    """Without Playwright, analyze page text for stock hints."""
    import requests
    from app.semantic import semantic_extract
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "ArgosScout-Probe/1.0"})
        sem = semantic_extract(r.text, url)
        nums = _extract_numbers_from_text(sem["content"])
        return {
            "url": url,
            "success": bool(nums),
            "method": "provocative_passive",
            "extracted": {"stock_hints": nums} if nums else {},
            "note": "Playwright required for active cart probing",
        }
    except Exception as e:
        return {"url": url, "success": False, "error": str(e)}


def provocative_form_probe(url: str, field_overrides: Optional[dict] = None) -> dict[str, Any]:
    """Submit forms with extreme values to trigger validation errors revealing limits."""
    if not PLAYWRIGHT_AVAILABLE:
        return {"url": url, "success": False, "error": "Playwright required"}

    overrides = field_overrides or {"email": "probe@test.argoscout.local", "quantity": "99999", "amount": "999999"}
    errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=25000)

            for name, value in overrides.items():
                sel = f"input[name*='{name}'], textarea[name*='{name}'], select[name*='{name}']"
                if page.query_selector(sel):
                    human_type(page, sel, str(value))

            submit = page.query_selector("button[type='submit'], input[type='submit']")
            if submit:
                human_click(page, "button[type='submit'], input[type='submit']")
                page.wait_for_timeout(2000)

            for el in page.query_selector_all(".error, .invalid, [role='alert'], .field-error"):
                t = el.inner_text().strip()
                if t:
                    errors.append(t)

            browser.close()

        extracted = {"validation_errors": errors, "numbers": []}
        for e in errors:
            extracted["numbers"].extend(_extract_numbers_from_text(e))

        return {"url": url, "success": bool(errors), "method": "provocative_form", "extracted": extracted}
    except Exception as e:
        return {"url": url, "success": False, "error": str(e)}
