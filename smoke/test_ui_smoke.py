"""Playwright smoke test: flip the as-of switch and watch Rule 170's status change.

This is the demo (S6 rule 2) as a test: same question, two dates, two sourced answers,
the previous one still on screen. Runs keyless against a real uvicorn process.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    assert (ROOT / "web" / "dist" / "index.html").exists(), "run `make web` first"
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}  # keyless
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def _browser(p):
    exe = os.environ.get("CHROMIUM_PATH") or shutil.which("chromium")
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


def test_as_of_switch_reanswers_rule_170(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(base_url)
        page.get_by_test_id("as-of").fill("2024-08-28")
        page.get_by_test_id("question").fill("Is Rule 170 in force?")
        page.get_by_test_id("ask").click()
        answer = page.get_by_test_id("answer")
        expect(answer.get_by_test_id("status-line")).to_contain_text("omission stayed")
        expect(answer.get_by_test_id("status-line")).to_contain_text("sub judice")
        expect(answer.locator("a", has_text="Open source").first).to_have_attribute(
            "href", "https://api.sci.gov.in/supremecourt/2022/24832/24832_2022_5_42_63155_Order_11-Aug-2025.pdf"
        )

        page.get_by_test_id("as-of").fill("2025-08-12")
        expect(answer.get_by_test_id("status-line")).to_contain_text("stay vacated")
        expect(page.get_by_test_id("previous-answer")).to_contain_text("sub judice")
        browser.close()


def test_abstention_has_a_designed_state(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(base_url)
        page.get_by_test_id("question").fill("Who won the FIFA World Cup football final?")
        page.get_by_test_id("ask").click()
        expect(page.get_by_test_id("abstain")).to_contain_text("No sourced answer")
        browser.close()


def test_abs_panel_shows_slab_and_abstains_before_commencement(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(base_url)
        page.get_by_test_id("as-of").fill("2026-09-27")
        page.get_by_test_id("abs-turnover").fill("60")
        page.get_by_test_id("abs-sales").fill("100")
        page.get_by_test_id("abs-compute").click()
        result = page.get_by_test_id("abs-result")
        expect(result).to_contain_text("0.4%")
        expect(result).to_contain_text("4000000.00")
        expect(result).to_contain_text("3. Above 50 crore to 250 crore 0.4%")

        page.get_by_test_id("as-of").fill("2025-04-29")
        page.get_by_test_id("abs-compute").click()
        expect(page.get_by_test_id("abs-abstain")).to_contain_text("2025-04-30")
        browser.close()


def test_passport_compiles_and_follows_the_date(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(base_url)
        page.get_by_test_id("as-of").fill("2024-08-28")
        page.get_by_test_id("passport-category").select_option("classical")
        page.get_by_test_id("passport-compile").click()
        expect(page.get_by_test_id("passport")).to_contain_text("First Schedule")
        expect(page.get_by_test_id("passport-rule-ADV-RULE-170")).to_contain_text("sub judice")
        expect(page.get_by_test_id("passport-print")).to_be_visible()

        page.get_by_test_id("passport-category").select_option("phytopharma")
        page.get_by_test_id("passport-compile").click()
        expect(page.get_by_test_id("passport-gaps")).to_be_visible()

        page.get_by_test_id("as-of").fill("2022-01-01")
        page.get_by_test_id("passport-compile").click()
        expect(page.get_by_test_id("passport-abstain")).to_contain_text("2022-11-17")
        browser.close()
