#!/usr/bin/env python3
"""
render_website.py — Headless website renderer for agent-driven design iteration.

Usage:
    python render_website.py --url https://example.com
    python render_website.py --file index.html
    python render_website.py --html "<h1>Hello</h1>" --out snapshot.png
    python render_website.py --url https://example.com --viewport 1440x900 --wait 2000 --full-page

Output JSON (stdout):
    {
        "status": "ok" | "error",
        "image_path": "/abs/path/to/snapshot.png",
        "viewport": {"width": 1280, "height": 800},
        "url": "...",
        "timestamp": "2026-05-27T...",
        "error": null | "message"
    }

All errors are surfaced via the JSON status field, never as unhandled exceptions,
so the calling LLM agent always gets a parseable response.
"""

import argparse
import json
import sys
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def parse_viewport(vp_str: str) -> tuple[int, int]:
    """Parse 'WxH' string → (width, height)."""
    try:
        w, h = vp_str.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise ValueError(f"Invalid viewport format '{vp_str}' — expected WxH e.g. 1280x800")


def render(
    *,
    url: str | None = None,
    file: str | None = None,
    html: str | None = None,
    out: str | None = None,
    viewport: tuple[int, int] = (1280, 800),
    wait_ms: int = 1000,
    full_page: bool = False,
    selector: str | None = None,
) -> dict:
    """
    Core render function. Exactly one of url/file/html must be provided.
    Returns a result dict (always — never raises).
    """
    timestamp = datetime.now(timezone.utc).isoformat() + "Z"
    result = {
        "status": "error",
        "image_path": None,
        "viewport": {"width": viewport[0], "height": viewport[1]},
        "url": None,
        "timestamp": timestamp,
        "error": None,
    }

    # --- validate inputs ---
    sources = [url, file, html]
    if sum(s is not None for s in sources) != 1:
        result["error"] = "Exactly one of --url, --file, or --html must be provided"
        return result

    # --- resolve output path ---
    if out is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = os.path.join(os.getcwd(), f"snapshot_{ts}.png")
    out = str(Path(out).resolve())

    # --- build target URL ---
    _tmp_html_path = None
    if url:
        target_url = url
        result["url"] = url
    elif file:
        abs_file = str(Path(file).resolve())
        if not os.path.isfile(abs_file):
            result["error"] = f"File not found: {abs_file}"
            return result
        target_url = f"file://{abs_file}"
        result["url"] = target_url
    else:  # html string
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        _tmp_html_path = tmp.name
        target_url = f"file://{_tmp_html_path}"
        result["url"] = target_url

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": viewport[0], "height": viewport[1]},
                device_scale_factor=2,  # retina-quality output
            )

            try:
                page.goto(target_url, wait_until="networkidle", timeout=15_000)
            except PWTimeout:
                # fall back to domcontentloaded if networkidle times out (e.g. external resources)
                page.goto(target_url, wait_until="domcontentloaded", timeout=10_000)

            # Extra wait for JS-heavy pages / CSS animations
            if wait_ms > 0:
                page.wait_for_timeout(wait_ms)

            # Screenshot
            shot_kwargs = dict(path=out, full_page=full_page)
            if selector:
                try:
                    elem = page.locator(selector).first
                    elem.screenshot(path=out)
                except Exception as e:
                    result["error"] = f"Selector '{selector}' screenshot failed: {e}"
                    browser.close()
                    return result
            else:
                page.screenshot(**shot_kwargs)

            browser.close()

        result["status"] = "ok"
        result["image_path"] = out
        result["error"] = None
        return result

    except Exception as e:
        result["error"] = f"Render failed: {type(e).__name__}: {e}"
        return result

    finally:
        if _tmp_html_path and os.path.exists(_tmp_html_path):
            os.unlink(_tmp_html_path)


def main():
    parser = argparse.ArgumentParser(
        description="Render a webpage to a PNG screenshot for agent-driven design iteration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url",  type=str, help="URL to render (http/https/file://)")
    source.add_argument("--file", type=str, help="Path to local HTML file")
    source.add_argument("--html", type=str, help="Raw HTML string to render")

    parser.add_argument("--out",       type=str, default=None,      help="Output PNG path (default: snapshot_<timestamp>.png)")
    parser.add_argument("--viewport",  type=str, default="1280x800", help="Viewport size WxH (default: 1280x800)")
    parser.add_argument("--wait",      type=int, default=1000,       help="Extra wait after load in ms (default: 1000)")
    parser.add_argument("--full-page", action="store_true",           help="Capture full scrollable page height")
    parser.add_argument("--selector",  type=str, default=None,       help="CSS selector — screenshot only that element")
    parser.add_argument("--pretty",    action="store_true",           help="Pretty-print JSON output")

    args = parser.parse_args()

    try:
        w, h = parse_viewport(args.viewport)
    except ValueError as e:
        out = {"status": "error", "image_path": None, "viewport": None,
               "url": None, "timestamp": datetime.now(timezone.utc).isoformat() + "Z", "error": str(e)}
        print(json.dumps(out, indent=2 if args.pretty else None))
        sys.exit(1)

    result = render(
        url=args.url,
        file=args.file,
        html=args.html,
        out=args.out,
        viewport=(w, h),
        wait_ms=args.wait,
        full_page=args.full_page,
        selector=args.selector,
    )

    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()