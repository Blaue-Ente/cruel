"""Playwright init script for a coherent hardware profile.

Applied only when `fingerprint_profiles` is on. Values match the selected
OS/UA profile. This is not canvas-noise anti-detect and not a challenge solver.
"""

from __future__ import annotations

from typing import Any

from app.browser.profiles import get_profile
from app.compliance.risk_gate import is_enabled


def fingerprint_init_script(profile_name: str = "desktop_chrome") -> str:
    profile = get_profile(profile_name)
    platform = profile.get("platform", "Linux x86_64")
    vendor = profile.get("webgl_vendor", "Google Inc. (Intel)")
    renderer = profile.get("webgl_renderer", "ANGLE (Intel, Mesa Intel, OpenGL)")
    cores = int(profile.get("hardware_concurrency") or 8)
    memory = int(profile.get("device_memory") or 8)
    sample_rate = int(profile.get("audio_sample_rate") or 44100)
    ua = profile.get("user_agent") or ""
    # Keep this small and profile-matched. No per-session canvas noise.
    return f"""
(() => {{
  const platform = {platform!r};
  const ua = {ua!r};
  const vendor = {vendor!r};
  const renderer = {renderer!r};
  try {{
    Object.defineProperty(navigator, 'platform', {{ get: () => platform }});
    Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {cores} }});
    Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {memory} }});
    Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
    if (ua) Object.defineProperty(navigator, 'userAgent', {{ get: () => ua }});
  }} catch (e) {{}}
  try {{
    const proto = WebGLRenderingContext && WebGLRenderingContext.prototype;
    if (proto && proto.getParameter) {{
      const orig = proto.getParameter;
      proto.getParameter = function (p) {{
        if (p === 37445) return vendor;
        if (p === 37446) return renderer;
        return orig.apply(this, arguments);
      }};
    }}
  }} catch (e) {{}}
  try {{
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {{
      const orig = AudioCtx;
      window.AudioContext = function () {{
        const ctx = new orig(...arguments);
        try {{ Object.defineProperty(ctx, 'sampleRate', {{ get: () => {sample_rate} }}); }} catch (e) {{}}
        return ctx;
      }};
    }}
  }} catch (e) {{}}
}})();
"""


def apply_fingerprint(context: Any, profile_name: str = "desktop_chrome") -> bool:
    if not is_enabled("fingerprint_profiles"):
        return False
    try:
        context.add_init_script(fingerprint_init_script(profile_name))
        return True
    except Exception:
        return False
