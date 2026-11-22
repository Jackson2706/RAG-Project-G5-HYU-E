"""Deck v4 Task 1: usability screenshots (and one fallback screen video) of the real app, with Playwright.

Needs the app running (./start.sh: backend :8000, frontend :5173), plus for the "Ollama not running" error a second
backend on :8001 that points at a closed Ollama port:
  (cd backend && OLLAMA_BASE_URL=http://127.0.0.1:11999 python -m uvicorn app.main:app --port 8001)
Run from Sources/ (conda env RAG, `pip install playwright && python -m playwright install chromium` once):
  python scripts/deck_v4_screens.py shots   # -> Report/figures/usability/u01_…png + Report/slides/deck_v4/error_messages.csv
  python scripts/deck_v4_screens.py video   # -> .run/demo_video/ (S1–S4 with AAES; webm, kept out of git)

Every error message is produced by the real frontend and backend; Playwright only changes the request (an unknown
model or index name) or blocks it (backend down). Questions are dev or demo questions, never test-1.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "Report" / "figures" / "usability"
ERRORS = ROOT / "Report" / "slides" / "deck_v4" / "error_messages.csv"
APP, INDEX = "http://127.0.0.1:5173", "hyu_20261110_97dc1269_r5"
S1, COUNSEL = "Which insurance rules apply to me?", "How do I book the international student counseling program?"
S3, S4 = "Does my insurance change after my visa switches from D-4 to D-2?", "I'm a Seoul campus student. Can I bring my pet dog into the dormitory?"  # S4 = demo S4c
LONG = 10 * 60_000  # ms; one AAES answer can take a minute on the 16 GB Mac


def open_app(page: Page, preset: str = "A0_AAES", fresh: bool = False) -> None:
    page.goto(APP)
    if not fresh:
        page.evaluate("localStorage.setItem('hyu-compass:help-closed', 'true')")
        page.reload()
    page.wait_for_selector("#preset option[value='A0_AAES']", state="attached")
    page.select_option("#preset", preset)
    page.select_option("#index", INDEX)


def ask(page: Page, question: str) -> None:
    page.fill("#chat-input", question)
    page.keyboard.press("Enter")
    page.wait_for_selector("button[aria-label='Stop']", timeout=10_000)
    page.wait_for_selector("button[aria-label='Send']", timeout=LONG)
    page.wait_for_timeout(500)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(SHOTS / name))
    print("saved", name, flush=True)


def alert_text(page: Page) -> str:
    return " | ".join(t.strip() for t in page.locator("[role=alert]").all_inner_texts())


def shots() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = ctx.new_page()
        open_app(page, fresh=True)
        shot(page, "u01_first_screen_help.png")

        open_app(page)  # S1 with AAES: answer per case, sources open, Execution tab
        ask(page, S1)
        page.get_by_role("tab", name="Configuration").click()
        shot(page, "u03_answer_per_case.png")
        page.locator("details[id^='source-E'] summary").first.click()
        shot(page, "u02_answer_sources_open.png")
        page.get_by_role("tab", name="Execution").click()
        page.wait_for_timeout(500)
        shot(page, "u06_execution_tab.png")

        open_app(page)  # S2: clarifying question, then campus remembered from the earlier turn
        ask(page, COUNSEL)
        shot(page, "u04_clarifying_question.png")
        ask(page, "I'm a Seoul campus student.")
        ask(page, COUNSEL)
        page.get_by_role("tab", name="Execution").click()
        page.get_by_text("Query Understanding", exact=False).first.click()  # open step 1: the profile with statuses
        page.wait_for_timeout(500)
        shot(page, "u05_remembered_profile.png")
        page.get_by_role("button", name="Forget my details").click()
        page.wait_for_timeout(300)
        shot(page, "u15_forget_my_details.png")

        open_app(page)  # compare mode: standard dense, prompted conditional, AAES
        page.get_by_role("button", name="Compare mode").click()
        for label in ("B0", "R16", "A0"):
            page.locator("[data-testid=compare-picker] label", has_text=label).first.locator("input").check()
        page.fill("#chat-input", S1)
        page.keyboard.press("Enter")
        page.wait_for_selector("button[aria-label='Stop']", timeout=10_000)
        page.wait_for_selector("button[aria-label='Send']", timeout=3 * LONG)
        page.wait_for_timeout(500)
        shot(page, "u07_compare_mode.png")

        def error_case(name: str, what: str, how: str, action) -> None:
            open_app(page)
            action()
            page.wait_for_selector("[role=alert]", timeout=60_000)
            page.wait_for_timeout(300)
            shot(page, name)
            errors.append({"error": what, "input": how, "message_shown": alert_text(page), "screenshot": name})

        error_case("u08_error_empty_question.png", "empty question", "Enter pressed with an empty input box",
                   lambda: (page.focus("#chat-input"), page.keyboard.press("Enter")))  # fmt: skip
        error_case("u09_error_long_question.png", "very long question", "a 2,400-character question pasted", lambda: page.fill("#chat-input", "Can I work part time? " * 110))

        def swap(field: str, value: str):
            def handler(route):
                body = json.loads(route.request.post_data or "{}")
                if field == "model":
                    body["stages"]["generation"]["params"]["model"] = value
                else:
                    body[field] = value
                route.continue_(post_data=json.dumps(body))
            return handler

        def with_route(pattern, handler, question=S1):
            def run():
                page.route(pattern, handler)
                page.fill("#chat-input", question)
                page.keyboard.press("Enter")
            return run

        error_case("u10_error_model_missing.png", "model not pulled", "generation model set to 'qwen3.5:9b' (not installed)",
                   with_route("**/api/chat/stream", swap("model", "qwen3.5:9b")))  # fmt: skip
        page.unroute("**/api/chat/stream")
        error_case("u11_error_index_missing.png", "index missing", "index_id set to 'hyu_missing_r9'", with_route("**/api/chat/stream", swap("index_id", "hyu_missing_r9")))
        page.unroute("**/api/chat/stream")
        error_case("u12_error_ollama_down.png", "Ollama not running", "backend pointed at a closed Ollama port (:11999)",
                   with_route("**/api/**", lambda r: r.continue_(url=r.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"))))  # fmt: skip
        page.unroute("**/api/**")

        def backend_down():
            page.route("**/api/**", lambda r: r.abort())
            page.fill("#chat-input", S1)
            page.keyboard.press("Enter")
        error_case("u13_error_backend_down.png", "backend down", "every /api request fails to connect", backend_down)
        page.reload()
        page.wait_for_timeout(1500)
        errors.append({"error": "backend down (page load)", "input": "page opened while the backend is down",
                       "message_shown": page.locator("header").inner_text().strip().replace("\n", " "), "screenshot": "u14_error_backend_down_header.png"})  # fmt: skip
        shot(page, "u14_error_backend_down_header.png")
        browser.close()
    with ERRORS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["error", "input", "message_shown", "screenshot"])
        writer.writeheader()
        writer.writerows(errors)
    print(json.dumps(errors, indent=1))
    return 0


def video() -> int:
    out = ROOT / ".run" / "demo_video"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=str(out), record_video_size={"width": 1440, "height": 900})
        page = ctx.new_page()
        open_app(page)
        ask(page, S1)
        page.get_by_role("tab", name="Execution").click()
        page.wait_for_timeout(4000)
        page.get_by_role("button", name="New conversation").click()
        for q in (COUNSEL, "I'm a Seoul campus student.", COUNSEL):
            ask(page, q)
            page.wait_for_timeout(2500)
        page.get_by_role("button", name="New conversation").click()
        for q in (S3, S4):
            ask(page, q)
            page.wait_for_timeout(3000)
            page.get_by_role("button", name="New conversation").click()
        ctx.close()
        browser.close()
    print("video in", out, [f.name for f in out.glob("*.webm")])
    return 0


if __name__ == "__main__":
    raise SystemExit({"shots": shots, "video": video}[sys.argv[1]]())
