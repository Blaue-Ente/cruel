"""Ghost cursor — human-like mouse movement with biometric jitter."""

from __future__ import annotations

import math
import random
from typing import Optional

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    Page = None  # type: ignore


def _bezier(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )


def human_move(page: "Page", x: float, y: float, steps: int = 25) -> None:
    """Move mouse along bezier curve with micro-tremor."""
    if not PLAYWRIGHT_AVAILABLE:
        return
    try:
        box = page.viewport_size or {"width": 1280, "height": 900}
        start_x = random.uniform(box["width"] * 0.2, box["width"] * 0.8)
        start_y = random.uniform(box["height"] * 0.2, box["height"] * 0.8)
        cp1x = start_x + random.uniform(-80, 80)
        cp1y = start_y + random.uniform(-60, 60)
        cp2x = x + random.uniform(-40, 40)
        cp2y = y + random.uniform(-40, 40)

        for i in range(steps + 1):
            t = i / steps
            t = t * t * (3 - 2 * t)  # ease in-out
            mx = _bezier(t, start_x, cp1x, cp2x, x)
            my = _bezier(t, start_y, cp1y, cp2y, y)
            mx += random.gauss(0, 0.8)
            my += random.gauss(0, 0.8)
            page.mouse.move(mx, my)
            page.wait_for_timeout(random.randint(8, 25))
    except Exception:
        pass


def human_click(page: "Page", selector: str) -> bool:
    if not PLAYWRIGHT_AVAILABLE:
        return False
    try:
        el = page.query_selector(selector)
        if not el:
            return False
        box = el.bounding_box()
        if not box:
            return False
        tx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        human_move(page, tx, ty)
        page.wait_for_timeout(random.randint(50, 180))
        page.mouse.click(tx, ty)
        return True
    except Exception:
        return False


def human_type(page: "Page", selector: str, text: str, typo_rate: float = 0.04) -> bool:
    if not PLAYWRIGHT_AVAILABLE:
        return False
    try:
        human_click(page, selector)
        page.wait_for_timeout(random.randint(100, 300))
        for ch in text:
            if random.random() < typo_rate:
                wrong = chr(ord(ch) + random.choice([-1, 1]))
                page.keyboard.type(wrong)
                page.wait_for_timeout(random.randint(40, 120))
                page.keyboard.press("Backspace")
            page.keyboard.type(ch)
            page.wait_for_timeout(random.randint(30, 110))
        return True
    except Exception:
        return False
