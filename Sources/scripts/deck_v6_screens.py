"""Deck v6 Task 2: the follow-up screenshot u17 and the D1-D3 fallback video, from the real app, with Playwright.

Needs the app running (./start.sh: backend :8000 with follow-up resolution on, frontend :5173). Run from Sources/:
  python scripts/deck_v6_screens.py u17     # -> Report/figures/usability/u17_followup_answer.png
  python scripts/deck_v6_screens.py video   # -> .run/demo_video_v6/*.webm (compare mode B0, R16, AAES+; D1-D3)
Questions are dev or demo questions, never a held-out one.
"""

from __future__ import annotations

import sys

from deck_v4_screens import COUNSEL, LONG, ROOT, S1, S4, SHOTS, open_app, sync_playwright

REPLY = "I'm a Seoul campus student."
COLUMNS = ("B0 — Basic Dense RAG", "R16 — Prompted conditional answering", "AAES+ (RRRL)")


def send(page, question: str, compare: bool = False) -> None:
    page.fill("#chat-input", question)
    page.keyboard.press("Enter")
    page.wait_for_selector("button[aria-label='Stop']", timeout=10_000)
    page.wait_for_selector("button[aria-label='Send']", timeout=(3 if compare else 1) * LONG)
    page.wait_for_timeout(800)


def u17() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        open_app(page, "AP_RRRL")
        send(page, COUNSEL)  # AAES+ asks the campus
        send(page, REPLY)  # the reply answers the earlier question
        page.get_by_role("tab", name="Execution").click()
        page.get_by_text("Answering your earlier question").wait_for(timeout=10_000)
        page.screenshot(path=str(SHOTS / "u17_followup_answer.png"))
        print("saved u17_followup_answer.png", flush=True)
        browser.close()
    return 0


def video() -> int:
    out = ROOT / ".run" / "demo_video_v6"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=str(out), record_video_size={"width": 1440, "height": 900})
        page = ctx.new_page()
        open_app(page, "AP_RRRL")
        page.get_by_role("button", name="Compare mode").click()
        for label in COLUMNS:
            page.locator("[data-testid=compare-picker] label", has_text=label).first.locator("input").check()
        send(page, S1, compare=True)  # D1
        page.get_by_role("tab", name="Execution").click()
        page.wait_for_timeout(4000)
        page.get_by_role("button", name="New conversation").click()
        for q in (COUNSEL, REPLY):  # D2
            send(page, q, compare=True)
            page.wait_for_timeout(2500)
        page.get_by_role("button", name="New conversation").click()
        send(page, S4, compare=True)  # D3
        page.wait_for_timeout(3000)
        ctx.close()
        browser.close()
    print("video in", out, [f.name for f in out.glob("*.webm")])
    return 0


if __name__ == "__main__":
    raise SystemExit({"u17": u17, "video": video}[sys.argv[1]]())
