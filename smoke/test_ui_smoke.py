"""Playwright smoke test: flip the as-of switch and watch Rule 170's status change.

This is the demo (S6 rule 2) as a test: same question, two dates, two sourced answers,
the previous one still on screen. Runs keyless against a real uvicorn process.
"""

import os
import re
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
    env["SAHAYAK_MODE"] = "offline"  # and .env on this machine must not re-add them
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
        page.goto(f"{base_url}?view=classic")
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
        page.goto(f"{base_url}?view=classic")
        page.get_by_test_id("question").fill("Who won the FIFA World Cup football final?")
        page.get_by_test_id("ask").click()
        expect(page.get_by_test_id("abstain")).to_contain_text("No sourced answer")
        browser.close()


def test_abs_panel_shows_slab_and_abstains_before_commencement(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(f"{base_url}?view=classic")
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
        page.goto(f"{base_url}?view=classic")
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
    page.goto(f"{base}?view=classic")
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
            # The recorded Groq synthesis leans on a quoted Amicus submission ("still in
            # force"); The Status Ledger says omitted, so the contract withholds it (D-020).
            withheld = answer.get_by_test_id("synthesis-withheld")
            expect(withheld).to_contain_text("Status Ledger")
            expect(answer.get_by_test_id("synthesis")).to_have_count(0)
            expect(answer.get_by_test_id("status-line")).to_contain_text("stay vacated")
            seen.append(answer.locator("blockquote").all_inner_texts())
        assert seen[0] and seen[0] == seen[1]
        browser.close()
    health = json.load(urllib.request.urlopen(hybrid_replay_url + "/health", timeout=5))
    assert health["ready"] is True
    assert health["retrieval"]["mode"] == "hybrid", health["retrieval"]


# ---- M4: voice input + accessibility (S6 rules 5-6) ----

NO_SPEECH = "delete window.SpeechRecognition; delete window.webkitSpeechRecognition;"
FAKE_SPEECH = """
window.__recs = [];
class FakeRec {
  constructor() { window.__recs.push(this); }
  start() {
    setTimeout(() => {
      this.onresult && this.onresult({ results: [[{ transcript: "Is Rule 170 in force?" }]] });
      this.onend && this.onend();
    }, 50);
  }
  stop() { this.onend && this.onend(); }
}
window.SpeechRecognition = FakeRec;
"""


def test_mic_is_disabled_without_speech_recognition_and_typing_still_works(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.add_init_script(NO_SPEECH)
        page.goto(f"{base_url}?view=classic")
        mic = page.get_by_test_id("mic")
        expect(mic).to_be_disabled()
        expect(mic).to_have_attribute("aria-label", re.compile("not available"))
        expect(page.get_by_test_id("question")).to_be_editable()
        browser.close()


def test_mic_fills_the_question_in_the_selected_language(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.add_init_script(FAKE_SPEECH)
        page.goto(f"{base_url}?view=classic")
        page.get_by_test_id("language").select_option("hi")
        page.get_by_test_id("mic").click()
        expect(page.get_by_test_id("question")).to_have_value("Is Rule 170 in force?")
        assert page.evaluate("window.__recs[0].lang") == "hi-IN"
        browser.close()


def test_tab_reaches_switch_question_ask_and_first_source(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.add_init_script(NO_SPEECH)
        _ask(page, base_url, "Is Rule 170 in force?")
        expect(page.get_by_test_id("answer").locator("blockquote").first).to_be_visible()
        page.locator("h1").click()  # sets the sequential-focus start point to the top
        order = []
        for _ in range(60):  # run 13: glossary "?" buttons add tab stops
            page.keyboard.press("Tab")
            tag = page.evaluate(
                "(() => { const e = document.activeElement;"
                " if (e.dataset.testid) return e.dataset.testid;"
                " if (e.tagName === 'A' && e.closest('[data-testid=answer] ol'))"
                " return 'source-link';"
                " return e.tagName; })()")
            order.append(tag)
            if tag == "source-link":
                break
        want = ["jurisdiction", "question", "ask", "source-link"]
        pos = [order.index(w) for w in want]  # ValueError = element not keyboard-reachable
        assert pos == sorted(pos), order
        # Visible focus: the focused link draws an outline.
        width = page.evaluate("getComputedStyle(document.activeElement).outlineWidth")
        assert width not in ("0px", ""), width
        browser.close()


CONTRAST_JS = """
(el) => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const rgba = (c) => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
                        return Array.from(cx.getImageData(0, 0, 1, 1).data); };
  let bg = null;
  for (let n = el; n; n = n.parentElement) {
    const c = rgba(getComputedStyle(n).backgroundColor);
    if (c[3] > 0) { bg = c; break; }
  }
  bg = bg || [255, 255, 255, 255];
  const fg = rgba(getComputedStyle(el).color);
  const a = parseFloat(getComputedStyle(el).opacity);
  const lum = (c) => { const v = c.slice(0, 3).map((x) => { x /= 255;
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const [l1, l2] = [lum(fg), lum(bg)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}
"""


def _contrast(locator) -> float:
    return locator.evaluate(CONTRAST_JS)


def test_synthesis_card_and_escalation_meet_wcag_aa_contrast(replay_url, base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        answer = _ask(page, replay_url, "Is Rule 170 in force?")
        card = answer.get_by_test_id("synthesis")
        expect(card).to_be_visible()
        for el in card.locator("p, a").all():
            assert _contrast(el) >= 4.5, el.inner_text()[:60]
        answer = _ask(page, base_url, "What is the GST rate on Ayurvedic cosmetics?")
        esc = answer.get_by_test_id("escalation")
        expect(esc).to_be_visible()
        assert _contrast(esc) >= 4.5
        for el in answer.get_by_test_id("abstain").locator("p").all():
            assert _contrast(el) >= 4.5, el.inner_text()[:60]
        browser.close()


# The demo, as a test (M12): the chips ask the scripted questions, the timeline strip marks the
# segment the as-of date falls in, and the static-RAG card shows what is missing without it.
def test_demo_chips_walk_rule_170_through_every_ledger_segment(base_url):
    expected = [
        ("2024-06-30", "In force"),
        ("2024-07-02", "Omitted"),
        ("2024-08-28", "In force (stayed)"),
        ("2025-08-12", "Omitted (stay vacated)"),
    ]
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(f"{base_url}?view=classic")
        page.get_by_test_id("demo-question").first.click()  # the diabetes advertisement
        answer = page.get_by_test_id("answer")
        expect(answer.get_by_test_id("status-line")).to_be_visible()
        for date, short in expected:
            page.get_by_test_id("demo-date").filter(has_text=date).click()
            expect(answer.get_by_test_id("timeline-active")).to_contain_text(short)
            expect(answer.get_by_test_id("timeline-active")).to_contain_text(date[:4])
            # The DMR Act overlay applies whatever the rule's status is, so it is on every date.
            expect(answer).to_contain_text("applies whatever the rule’s status")
            expect(answer).to_contain_text("Diabetes")
        browser.close()


def test_compare_toggle_shows_a_static_rag_card_with_no_date(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(f"{base_url}?view=classic")
        page.get_by_test_id("demo-date").filter(has_text="2024-06-30").click()
        page.get_by_test_id("demo-question").filter(has_text="Rule 170 status").click()
        status = page.get_by_test_id("answer").get_by_test_id("status-line")
        expect(status).to_contain_text("In force")
        expect(page.get_by_test_id("baseline")).to_have_count(0)
        page.get_by_test_id("compare").check()
        baseline = page.get_by_test_id("baseline")
        expect(baseline).to_contain_text("no as-of date, no Status Ledger")
        expect(baseline).not_to_contain_text("Status as of")
        browser.close()


def test_hindi_advertisement_question_reaches_the_ledger(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(f"{base_url}?view=classic")
        page.get_by_test_id("language").select_option("hi")
        page.get_by_test_id("demo-date").filter(has_text="2024-08-28").click()
        page.get_by_test_id("demo-question").filter(has_text="हिन्दी").click()
        answer = page.get_by_test_id("answer")
        expect(answer.get_by_test_id("status-line")).to_contain_text("न्यायालय में विचाराधीन")
        expect(answer.get_by_test_id("timeline-active")).to_be_visible()
        browser.close()


def test_guided_demo_walks_a_newcomer_through_the_script(base_url):
    """Run 13: the guided demo performs each scripted beat for a lay presenter."""
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(f"{base_url}?view=classic")
        page.get_by_test_id("tour-open").click()
        tour = page.get_by_test_id("tour")
        expect(tour).to_contain_text("step 1 of 10")
        page.get_by_test_id("tour-do").click()
        answer = page.get_by_test_id("answer")
        expect(answer.get_by_test_id("status-line")).to_contain_text("In force")
        expect(answer.get_by_test_id("plain")).to_contain_text("applied")
        page.get_by_test_id("tour-next").click()
        page.get_by_test_id("tour-do").click()
        expect(answer.get_by_test_id("status-line")).to_contain_text("Omitted")
        expect(page.get_by_test_id("changed")).to_contain_text("Omitted")
        for _ in range(3):
            page.get_by_test_id("tour-next").click()
        page.get_by_test_id("tour-do").click()  # step 5: compare with static RAG
        expect(page.get_by_test_id("compare")).to_be_checked()
        expect(page.get_by_test_id("baseline")).to_be_visible()
        page.get_by_test_id("tour-next").click()
        page.get_by_test_id("tour-next").click()
        page.get_by_test_id("tour-do").click()  # step 7: deliberate abstention
        expect(answer.get_by_test_id("abstain")).to_be_visible()
        expect(answer.get_by_test_id("plain")).to_contain_text("refuses to guess")
        browser.close()


def test_glossary_explains_terms_in_plain_words(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.goto(f"{base_url}?view=classic")
        page.get_by_test_id("term-asOf").click()
        expect(page.get_by_role("note")).to_contain_text("The date your question is about")
        page.keyboard.press("Escape")
        expect(page.get_by_role("note")).to_have_count(0)
        page.get_by_test_id("glossary-open").click()
        g = page.get_by_test_id("glossary")
        expect(g).to_contain_text("Sub judice")
        page.get_by_label("Search the glossary").fill("abstain")
        expect(g.locator("dt")).to_have_count(1)
        browser.close()


# --------------------------------------------------------------------------------------
# The Conversation (run 14): the chat is now the default view. These hold the demo path
# end to end in a real browser, keyless.
# --------------------------------------------------------------------------------------
def _chat(page, base):
    page.goto(base)
    expect(page.get_by_test_id("chat-input")).to_be_visible()
    return page


def _say(page, message):
    page.get_by_test_id("chat-input").fill(message)
    page.get_by_test_id("chat-send").click()


def test_chat_is_the_default_view(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        expect(page.get_by_test_id("chat-log")).to_contain_text("Sahayak")
        expect(page.get_by_test_id("chat-starter").first).to_be_visible()
        # the law clock is on screen before anything is asked
        expect(page.get_by_test_id("law-clock")).to_contain_text("Rule 170")
        browser.close()


def test_chat_answers_rule_170_and_a_date_follow_up_shows_the_change(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        page.get_by_test_id("chat-as-of").fill("2024-06-30")
        _say(page, "Is Rule 170 in force?")
        answer = page.get_by_test_id("chat-msg-assistant").last
        expect(answer.get_by_test_id("status-line")).to_contain_text("in force", ignore_case=True)
        # a bare date is understood as a follow-up to the same question
        _say(page, "what about 2 Jul 2024?")
        follow = page.get_by_test_id("chat-msg-assistant").last
        expect(follow).to_contain_text("The law changed")
        expect(page.get_by_test_id("chat-as-of")).to_have_value("2024-07-02")
        browser.close()


def test_chat_abstains_out_loud_when_the_sources_do_not_say(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        _say(page, "What is the GST rate on churna?")
        answer = page.get_by_test_id("chat-msg-assistant").last
        expect(answer.get_by_test_id("abstain")).to_be_visible()
        browser.close()


def test_chat_asks_for_turnover_then_computes_the_abs_share(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        _say(page, "Calculate my ABS benefit share")
        last = page.get_by_test_id("chat-msg-assistant").last
        expect(last).to_contain_text("turnover", ignore_case=True)
        _say(page, "40 crore")
        result = page.get_by_test_id("chat-abs-result")
        expect(result).to_contain_text("0.2%")
        browser.close()


def test_chat_highlights_risky_words_inside_the_advertisers_own_copy(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        _say(page, 'check this claim: "Cures diabetes 100% guaranteed, no side effects"')
        flags = page.get_by_test_id("claim-flags")
        expect(flags).to_be_visible()
        expect(page.get_by_test_id("chat-msg-assistant").last.locator("mark").first).to_be_visible()
        browser.close()


def test_chat_reaches_the_same_ledger_in_hindi(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        page.get_by_test_id("chat-lang").select_option("hi")
        page.get_by_test_id("chat-as-of").fill("2024-06-30")
        _say(page, "क्या नियम 170 लागू है?")
        answer = page.get_by_test_id("chat-msg-assistant").last
        expect(answer.get_by_test_id("status-line")).to_be_visible()
        browser.close()


def test_chat_general_ayurveda_answer_is_labelled_as_background(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        _say(page, "What are the three doshas?")
        answer = page.get_by_test_id("chat-msg-assistant").last
        expect(answer.get_by_test_id("chat-knowledge")).to_contain_text("not from The Library")
        browser.close()


def test_autopilot_walks_the_presenter_through_the_demo(base_url):
    with sync_playwright() as p:
        browser = _browser(p)
        page = _chat(browser.new_page(), base_url)
        page.get_by_test_id("chat-autopilot").click()
        bar = page.get_by_test_id("autopilot-bar")
        expect(bar).to_contain_text("1/")
        expect(page.get_by_test_id("chat-msg-assistant").last.get_by_test_id("status-line")).to_be_visible()
        page.get_by_test_id("autopilot-next").click()
        expect(bar).to_contain_text("2/")
        expect(page.get_by_test_id("chat-msg-assistant").last).to_contain_text("The law changed")
        browser.close()
