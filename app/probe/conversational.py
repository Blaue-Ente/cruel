"""Conversational scraping — LLM-generated inquiries for forms and chat widgets."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.probe.ghost_cursor import human_click, human_type
from app.providers import chat_complete

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

try:
    from app.inbox import register_submission
    from app.config import IMAP_USER
except ImportError:
    register_submission = None  # type: ignore
    IMAP_USER = ""


def generate_inquiry(goal: str, language: str = "auto", provider: Optional[str] = None) -> str:
    lang_hint = language if language != "auto" else ("Bulgarian" if any(c in goal for c in "абвгдежзийклмнопрстуфхцчшщъьюя") else "English")
    prompt = f"""Generate a realistic customer inquiry message for a contact form or chatbot.
Language: {lang_hint}
Goal (what info to extract): {goal}
Be polite, specific, sound like a real potential customer. 2-4 sentences. No placeholders."""

    return chat_complete([{"role": "user", "content": prompt}], provider=provider, max_tokens=250) or f"Hello, I would like information about: {goal}"


def conversational_scrape(
    url: str,
    goal: str = "pricing and conditions",
    language: str = "auto",
    dry_run: bool = True,
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """
    Detect contact forms/chat widgets, generate LLM inquiry, fill fields.
    dry_run=True: fill only, don't submit (default safe mode).
    """
    inquiry = generate_inquiry(goal, language, provider)

    if not PLAYWRIGHT_AVAILABLE:
        return {
            "url": url,
            "success": True,
            "method": "conversational_text_only",
            "generated_inquiry": inquiry,
            "note": "Playwright required to interact with forms",
        }

    forms_found = []
    chat_found = []
    responses = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(1500)

            for form in page.query_selector_all("form"):
                action = form.get_attribute("action") or ""
                forms_found.append({"action": action, "fields": len(form.query_selector_all("input, textarea"))})

            chat_selectors = [
                "[class*='chat']", "[id*='chat']", "[class*='intercom']",
                "[class*='crisp']", "[class*='tawk']", "iframe[title*='chat']",
            ]
            for sel in chat_selectors:
                if page.query_selector(sel):
                    chat_found.append(sel)

            message_fields = (
                "textarea, input[name*='message'], input[name*='comment'], "
                "[contenteditable='true'], input[placeholder*='message' i]"
            )
            msg_el = page.query_selector(message_fields)
            if msg_el:
                tag = msg_el.evaluate("el => el.tagName")
                if tag == "TEXTAREA" or msg_el.get_attribute("name"):
                    sel = message_fields.split(",")[0]
                    human_type(page, "textarea", inquiry)

            email_sel = "input[type='email'], input[name*='email']"
            if page.query_selector(email_sel):
                human_type(page, email_sel, "research@argoscout.local")

            name_sel = "input[name*='name']"
            if page.query_selector(name_sel):
                human_type(page, name_sel, "Nikolay Research")

            if not dry_run:
                submit = page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Send')")
                if submit:
                    human_click(page, "button[type='submit'], input[type='submit']")
                    page.wait_for_timeout(3000)
                    for el in page.query_selector_all(".response, .reply, .bot-message, [class*='assistant']"):
                        t = el.inner_text().strip()
                        if t:
                            responses.append(t)
            else:
                responses.append("[DRY RUN] Form filled but not submitted")

            browser.close()

        submission_id = None
        if not dry_run and register_submission:
            probe_email = IMAP_USER or "research@argoscout.local"
            submission_id = register_submission(url, inquiry, probe_email)

        result = {
            "url": url,
            "success": True,
            "method": "conversational",
            "dry_run": dry_run,
            "generated_inquiry": inquiry,
            "forms_detected": forms_found,
            "chat_widgets": chat_found,
            "responses": responses,
        }
        if submission_id:
            result["submission_id"] = submission_id
            result["inbox_tracking"] = True
        return result
    except Exception as e:
        return {"url": url, "success": False, "method": "conversational", "error": str(e), "generated_inquiry": inquiry}
