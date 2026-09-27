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


def _serve(extra_env: dict):
    assert (ROOT / "web" / "dist" / "index.html").exists(), "run `make web` first"
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}  # keyless
    env.update(extra_env)
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
    return proc, url


@pytest.fixture(scope="module")
def base_url():
    proc, url = _serve({"SAHAYAK_LLM": "none"})
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def replay_url():
    # The committed Gemini recording, replayed with no key and no network (D-016).
    # Pinned to the BM25 core: replay keys hash the quotes, and the dense warm-up races the
    # first request, so hybrid would change the quotes mid-test (DECISIONS D-017).
    proc, url = _serve({"SAHAYAK_LLM": "gemini", "SAHAYAK_LLM_REPLAY": "replay",
                        "SAHAYAK_DENSE": "0"})
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def hybrid_replay_url():
    # D-017 closed: /ask holds until the dense warm-up settles, so a hybrid server answers
    # in one mode for its whole life and the Groq hybrid recordings replay deterministically.
    proc, url = _serve({"SAHAYAK_LLM": "groq", "SAHAYAK_LLM_REPLAY": "replay"})
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


def _ask(page, base, question, as_of="2026-09-01"):
    page.goto(base)
    page.get_by_test_id("jurisdiction").select_option("IN")
    page.get_by_test_id("as-of").fill(as_of)
    page.get_by_test_id("question").fill(question)
    page.get_by_test_id("ask").click()
    return page.get_by_test_id("answer")


def test_synthesis_card_from_committed_recording(replay_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        answer = _ask(page, replay_url, "Is Rule 170 in force?")
        card = answer.get_by_test_id("synthesis")
        expect(card).to_contain_text("AI-organised from the quotes below")
        expect(card).to_contain_text("stands vacated")
        expect(card).to_contain_text("replay")
        link = card.locator('a[href="#answer-q1"]')
        expect(link).to_have_text("[1]")
        expect(answer.locator("#answer-q1 blockquote")).to_be_visible()
        expect(answer.get_by_test_id("status-line")).to_contain_text("stay vacated")
        # The card sits above the quotes it organises.
        box_card, box_q = card.bounding_box(), answer.locator("#answer-q1").bounding_box()
        assert box_card["y"] < box_q["y"]
        browser.close()


def test_rejected_synthesis_is_withheld_quietly(replay_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        answer = _ask(page, replay_url, "What is codified traditional knowledge?")
        expect(answer.get_by_test_id("synthesis-withheld")).to_contain_text("insufficient")
        expect(answer.get_by_test_id("synthesis")).to_have_count(0)
        expect(answer.locator("blockquote").first).to_be_visible()
        browser.close()


def test_keyless_shows_no_synthesis_and_escalates_on_abstain(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        answer = _ask(page, base_url, "Is Rule 170 in force?")
        expect(answer.get_by_test_id("status-line")).to_contain_text("stay vacated")
        expect(answer.get_by_test_id("synthesis")).to_have_count(0)
        expect(answer.get_by_test_id("synthesis-withheld")).to_have_count(0)
        answer = _ask(page, base_url, "What is the GST rate on Ayurvedic cosmetics?")
        expect(answer.get_by_test_id("abstain")).to_be_visible()
        expect(answer.get_by_test_id("escalation")).to_contain_text("registered patent agent")
        expect(answer.get_by_test_id("escalation")).not_to_contain_text("lawyer")
        browser.close()


def test_hybrid_replay_is_stable_from_the_first_ask(hybrid_replay_url):
    import json

    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        seen = []
        for _ in range(2):
            answer = _ask(page, hybrid_replay_url, "Is Rule 170 in force?")
            card = answer.get_by_test_id("synthesis")
            expect(card).to_contain_text("replay")
            expect(answer.get_by_test_id("status-line")).to_contain_text("stay vacated")
            seen.append(answer.locator("blockquote").all_inner_texts())
        assert seen[0] and seen[0] == seen[1]
        browser.close()
    health = json.load(urllib.request.urlopen(hybrid_replay_url + "/health", timeout=5))
    assert health["ready"] is True
    assert health["retrieval"]["mode"] == "hybrid", health["retrieval"]
