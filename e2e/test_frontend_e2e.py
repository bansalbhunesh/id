"""Playwright end-to-end suite for the UdyamPulse frontend.

Run (from the repo root, with the backend virtualenv):

    pip install -r e2e/requirements.txt
    playwright install chromium
    python -m pytest e2e -q

The suite boots its own uvicorn on a free port, drives real Chromium against
the real backend, and asserts on live API-rendered content -- no mocks.
Kept outside backend/ so the default CI job (`pytest backend`) is unaffected.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(tmp_path_factory):
    port = _free_port()
    # Isolated audit log: the hash chain must never be shared with (or corrupt)
    # a developer server appending to backend/audit_log.jsonl concurrently.
    audit_path = tmp_path_factory.mktemp("audit") / "audit_log.jsonl"
    env = {**os.environ, "UDYAMPULSE_AUDIT_LOG_PATH": str(audit_path)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port),
         "--log-level", "warning"],
        cwd=REPO / "backend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        import urllib.request
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{url}/health", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("backend did not become ready")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture()
def page(browser, base_url):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page._console_errors = []
    page.on("console", lambda m: page._console_errors.append(m.text)
            if m.type == "error" else None)
    page.on("pageerror", lambda e: page._console_errors.append(str(e)))
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_timeout(400)
    yield page
    context.close()


def settle(page, ms=350):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


def test_landing_renders_live_decision(page):
    stage = page.inner_text("#caseSummary")
    assert "Bureau rejection reversed." in stage
    assert "27,00,000" in stage.replace(" ", "").replace("₹", "")
    assert "Rejected" in stage and "Approved" in stage
    assert "bureau history" in stage.lower()  # traditional reason surfaced
    assert not page._console_errors


def test_all_six_tabs_render_content_with_mouse_only(page):
    for tab, marker in [
        ("decision", "Five-pillar health ledger"),
        ("evidence", "Model attribution"),
        ("model", "Real-outcome benchmark"),
        ("governance", "Pilot promotion gate"),
        ("proof", "Truth boundary"),
        ("sources", "Data source register"),
    ]:
        page.click(f"#tab-{tab}")
        settle(page, 250)
        assert marker in page.inner_text("#tabContent"), tab
        assert page.get_attribute(f"#tab-{tab}", "aria-selected") == "true"
    assert not page._console_errors


def test_model_tab_serves_flagship_benchmark_evidence(page):
    page.click("#tab-model")
    settle(page)
    body = page.inner_text("#tabContent")
    assert "0.9623" in body            # true OOT AUC
    assert "0.9255" in body            # recession stress AUC
    assert "z =" in body               # DeLong-tested baselines
    assert "0.7314" in body            # proxy bootstrap CI lower bound
    assert "pass" in body.lower()      # artifact integrity
    assert "not an IDBI production calibration" in body


def test_hindi_toggle_switches_reason_codes(page):
    page.click("#tab-decision")
    settle(page, 250)
    page.click("[data-lang='hi']")
    page.wait_for_timeout(600)
    assert "मज़बूत" in page.inner_text("#tabContent")
    # The committed Devanagari face must actually activate, not a system
    # fallback: the hi rows name it first in their stack, which triggers the
    # unicode-ranged WOFF2 load.
    assert page.evaluate(
        "async () => { await document.fonts.ready; return [...document.fonts]"
        ".some(f => f.family === 'Noto Sans Devanagari' && f.status === 'loaded'); }")
    page.click("[data-lang='en']")
    page.wait_for_timeout(300)
    assert "Strong:" in page.inner_text("#tabContent")


def test_limit_basis_ledger_shows_emi_math(page):
    page.click("#tab-decision")
    settle(page, 250)
    body = page.inner_text("#tabContent")
    assert "How the limit was sized" in body
    assert "Affordable new EMI" in body
    assert "binding constraint" in body


def test_divergence_guardrail_reachable_for_stressed_case(page):
    page.select_option("#msme", "stressed_retailer")
    settle(page)
    page.click("#tab-evidence")
    settle(page, 300)
    body = page.inner_text("#tabContent")
    assert "GST-vs-bank turnover reconciliation" in body
    assert "+38%" in body


def test_case_switching_updates_verdict(page):
    page.select_option("#msme", "steady_wholesaler")
    settle(page)
    assert "Patel Wholesale Traders" in page.inner_text("#caseSummary")
    page.select_option("#msme", "ntc_hero")
    settle(page)
    assert "Shree Ganesh Textiles" in page.inner_text("#caseSummary")


def test_console_requires_key_then_scores_for_real(page, base_url):
    page.click("#tab-sources")
    settle(page, 300)
    page.click("[data-console] button[type='submit']")
    page.wait_for_timeout(300)
    assert "Bearer key required" in page.inner_text("[data-console-result]")

    page.fill("[data-console] input[name='key']", "wrong-key")
    page.click("[data-console] button[type='submit']")
    page.wait_for_timeout(1200)
    assert "401" in page.inner_text("[data-console-result]")

    page.fill("[data-console] input[name='key']", "udyampulse-demo-underwriter-key")
    page.click("[data-console] button[type='submit']")
    page.wait_for_timeout(2000)
    result = page.inner_text("[data-console-result]")
    assert "/100" in result
    assert any(word in result for word in ("Approved", "Review", "Rejected"))


def test_deep_link_restores_case_and_view(browser, base_url):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(f"{base_url}/?case=stressed_retailer&view=model",
              wait_until="networkidle")
    page.wait_for_timeout(500)
    assert page.evaluate("() => document.getElementById('msme').value") == "stressed_retailer"
    assert page.get_attribute("#tab-model", "aria-selected") == "true"
    assert "0.9623" in page.inner_text("#tabContent")
    context.close()


def test_keyboard_arrow_switches_tabs(page):
    page.focus("#tab-decision")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(250)
    assert page.get_attribute("#tab-evidence", "aria-selected") == "true"
    page.keyboard.press("End")
    page.wait_for_timeout(250)
    assert page.get_attribute("#tab-sources", "aria-selected") == "true"


def test_mobile_layout_stacks_without_overflow(browser, base_url):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_timeout(500)
    assert page.evaluate(
        "() => document.scrollingElement.scrollWidth"
        " <= document.documentElement.clientWidth + 1")
    assert page.evaluate("""() => {
      const s = document.getElementById('mainStage').getBoundingClientRect();
      const p = document.getElementById('reviewPacket').getBoundingClientRect();
      return p.top >= s.top;
    }""")
    page.click("#tab-model")
    page.wait_for_timeout(400)
    assert "0.9623" in page.inner_text("#tabContent")
    context.close()


def test_no_external_requests_and_selfhosted_fonts(browser, base_url):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    external = []
    page.on("request", lambda r: external.append(r.url)
            if "127.0.0.1" not in r.url else None)
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_timeout(600)
    assert external == []
    families = page.evaluate(
        "() => [...document.fonts].filter(f => f.status === 'loaded')"
        ".map(f => f.family)")
    assert "Libre Baskerville" in families
    assert "Source Sans 3" in families
    context.close()
