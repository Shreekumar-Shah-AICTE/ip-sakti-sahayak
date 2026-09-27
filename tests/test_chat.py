"""The Conversation: the chat router must not become a second, looser answer path.

Everything the chat says about the law has to come from The Library and The Status Ledger
through the same Answer Contract, and the general-knowledge side must stay free of legal
propositions. These tests hold that line.
"""

import datetime as dt
import json
import re

from fastapi.testclient import TestClient

from api import chat, ledger, main
from api.chat import llm as chat_llm
from api.chat import sentry
from api.chat.dates import find_date, is_follow_up

JUN30 = dt.date(2024, 6, 30)


# --------------------------------------------------------------------- dates
def test_find_date_formats():
    for text, want in [
        ("is rule 170 in force on 2024-08-28?", dt.date(2024, 8, 28)),
        ("what about 28/08/2024", dt.date(2024, 8, 28)),
        ("and on 15 Sep 2024?", dt.date(2024, 9, 15)),
        ("Sep 15, 2024", dt.date(2024, 9, 15)),
    ]:
        found, _rest, _note = find_date(text)
        assert found == want, text


def test_coarse_dates_are_flagged_not_guessed_silently():
    found, _rest, note = find_date("what was the position in July 2024?")
    assert found == dt.date(2024, 7, 15) and note
    found, _rest, note = find_date("what about in 2023?")
    assert found == dt.date(2023, 6, 30) and note


def test_date_phrase_is_stripped_so_a_bare_date_reads_as_a_follow_up():
    found, rest, _note = find_date("what about 1 Sep 2024?")
    assert found == dt.date(2024, 9, 1)
    assert is_follow_up(rest)
    assert not is_follow_up("can I advertise for diabetes")


# --------------------------------------------------------------------- the two switches
def test_a_date_in_the_message_moves_the_as_of_switch():
    out = chat.reply("Is Rule 170 in force on 28 Aug 2024?", as_of=JUN30)
    assert out["as_of"] == "2024-08-28"


def test_a_follow_up_re_answers_the_last_question_and_shows_the_change():
    first = chat.reply("Is Rule 170 in force?", as_of=JUN30)
    assert first["intent"] == "legal"
    second = chat.reply("what about 1 Sep 2024?", as_of=JUN30, context=first["context"])
    assert second["as_of"] == "2024-09-01"
    diff = [b for b in second["blocks"] if b["type"] == "diff"]
    assert diff and diff[0]["from"]["status"] != diff[0]["to"]["status"]


def test_rule_170_reads_the_ledger_on_every_date():
    want = {
        dt.date(2024, 6, 30): "in_force",
        dt.date(2024, 7, 2): "omitted",
        dt.date(2024, 8, 28): "in_force_stayed_omission",
    }
    for day, status in want.items():
        out = chat.reply("Is Rule 170 in force?", as_of=day)
        block = next(b for b in out["blocks"] if b["type"] == "answer")
        assert block["answer"]["status"]["status"] == status, day


# --------------------------------------------------------------------- abstention
def test_a_legal_question_is_never_answered_from_general_knowledge():
    out = chat.reply("What is the GST rate on churna?", as_of=JUN30)
    assert out["intent"] in ("legal", "abstain")
    assert not [b for b in out["blocks"] if b["type"] == "knowledge"]
    block = next(b for b in out["blocks"] if b["type"] == "answer")
    assert block["answer"]["abstain"] is True


def test_general_chat_is_labelled_as_background_and_carries_no_legal_claim():
    out = chat.reply("What are the three doshas?")
    assert out["intent"] == "general"
    know = next(b for b in out["blocks"] if b["type"] == "knowledge")
    assert know["label"]
    assert not chat.LEGAL.search(out["text"])


def test_an_unknown_question_says_so_and_offers_a_way_forward():
    out = chat.reply("qwertyuiop zxcvbnm")
    assert out["suggestions"]


# --------------------------------------------------------------------- the claim sentry
def test_sentry_quotes_are_verbatim_in_their_chunks():
    chunks = ledger.load_chunks()
    for rule in sentry._RULES:
        chunk_id, quote = rule[2], rule[3]
        assert chunk_id in chunks, chunk_id
        assert quote in chunks[chunk_id]["text"], chunk_id


def test_no_sentry_rule_is_dropped_for_failing_verification():
    rules, diseases = sentry._verified()
    assert len(rules) == len(sentry._RULES)
    assert diseases


def test_sentry_flags_absolute_and_magic_claims_with_spans_inside_the_text():
    text = "Cures diabetes 100% guaranteed, no side effects, a miracle remedy"
    s = sentry.scan(text)
    assert s["count"] >= 3
    for f in s["flags"]:
        start, end = f["span"]
        assert text[start:end] == f["match"]
    assert "indicator" in s["note"].lower()


def test_sentry_only_flags_and_never_rewrites_the_advertisers_words():
    s = sentry.scan("Supports immunity as part of a balanced routine")
    assert s["text"] == "Supports immunity as part of a balanced routine"
    assert s["count"] == 0


def test_claim_check_routes_through_the_sentry():
    out = chat.reply('check this claim: "Cures diabetes 100% guaranteed, no side effects"')
    block = next(b for b in out["blocks"] if b["type"] == "claims")
    assert block["result"]["count"] >= 2


# --------------------------------------------------------------------- knowledge hygiene
# Background entries may *point* at the legal side ("ask me about classical formulations"),
# but they must never state a legal position of their own, and never a dose.
PROPOSITION = re.compile(
    r"\bin force\b|\bprohibit|\bbanned\b|\bis (il)?legal\b|\byou (may|must|cannot|can't)\b|"
    r"\bpermitted\b|\bpunishable\b|\bomitted\b|\bpatentable\b|\brequired under\b",
    re.I,
)


def test_curated_knowledge_states_no_law():
    for entry in chat.knowledge():
        blob = f"{entry['title']} {entry['text']}"
        assert not PROPOSITION.search(blob), entry["title"]
        assert not re.search(r"\b(mg|ml|dose|dosage)\b", blob, re.I), entry["title"]


def test_every_knowledge_entry_has_keys_and_a_further_reading_link():
    for entry in chat.knowledge():
        assert entry["keys"] and entry["more"].startswith("https://")


def test_scrub_drops_legal_sentences_but_keeps_the_shape_of_a_list():
    text = "Ayurveda has three doshas.\n- Vata\n- Pitta\nRule 170 is in force and prohibits this."
    out = chat_llm.scrub(text)
    assert "- Vata" in out and "\n" in out
    assert "Rule 170" not in out


# --------------------------------------------------------------------- tools over chat
def test_abs_asks_for_turnover_then_computes_from_plain_words():
    ask = chat.reply("what is my ABS benefit share?")
    assert ask["context"]["pending"] == "abs_turnover"
    out = chat.reply("40 crore", context=ask["context"])
    result = next(b for b in out["blocks"] if b["type"] == "abs")["result"]
    assert result["slab"]["rate_pct"] == "0.2"


def test_passport_asks_for_a_category_then_compiles_it():
    ask = chat.reply("do I need a licence passport?")
    assert ask["context"]["pending"] == "passport_category"
    out = chat.reply("classical formulation", context=ask["context"])
    result = next(b for b in out["blocks"] if b["type"] == "passport")["result"]
    assert result["category"] == "classical" and result["rules"]


def test_licence_question_reaches_the_passport_compiler():
    # Autopilot beat 10 asks this exact sentence; it used to fall through to /ask and abstain.
    out = chat.reply("Do I need a licence for a classical formulation?")
    result = next(b for b in out["blocks"] if b["type"] == "passport")["result"]
    assert result["category"] == "classical" and result["rules"]


def test_the_library_can_be_listed_from_chat():
    out = chat.reply("what documents do you have?")
    docs = next(b for b in out["blocks"] if b["type"] == "library")["docs"]
    assert len(docs) >= 20


def test_compare_needs_a_question_first_then_shows_both_answers():
    empty = chat.reply("compare with an ordinary chatbot")
    assert not empty["blocks"]
    first = chat.reply("Is Rule 170 in force?", as_of=JUN30)
    out = chat.reply("compare", as_of=JUN30, context=first["context"])
    block = next(b for b in out["blocks"] if b["type"] == "compare")
    assert block["ours"]["as_of"] == "2024-06-30"


def test_hindi_and_gujarati_reach_the_same_ledger():
    for message in ("क्या नियम 170 लागू है?", "શું નિયમ 170 લાગુ છે?"):
        out = chat.reply(message, as_of=JUN30, lang="hi")
        block = next(b for b in out["blocks"] if b["type"] == "answer")
        assert block["answer"]["status"]["status"] == "in_force", message


def test_every_turn_reports_the_tools_it_used():
    out = chat.reply("Is Rule 170 in force?", as_of=JUN30)
    assert out["trace"] and all({"tool", "detail", "ms"} <= set(s) for s in out["trace"])


# --------------------------------------------------------------------- the endpoint
def test_chat_endpoint_answers_and_hides_the_audit_record():
    client = TestClient(main.app)
    r = client.post("/chat", json={"message": "Is Rule 170 in force?", "as_of": "2024-06-30"})
    assert r.status_code == 200
    body = r.json()
    assert body["as_of"] == "2024-06-30" and body["blocks"]
    assert "audit" not in body


def test_chat_endpoint_rejects_an_oversized_message():
    client = TestClient(main.app)
    assert client.post("/chat", json={"message": "x" * 1001}).status_code == 422
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_chat_endpoint_keeps_context_across_turns():
    client = TestClient(main.app)
    first = client.post(
        "/chat", json={"message": "Is Rule 170 in force?", "as_of": "2024-06-30"}
    ).json()
    second = client.post(
        "/chat",
        json={
            "message": "what about 2 Jul 2024?",
            "as_of": "2024-06-30",
            "context": first["context"],
        },
    ).json()
    assert second["as_of"] == "2024-07-02"
    assert [b for b in second["blocks"] if b["type"] == "diff"]


# --------------------------------------------------------------------- hygiene
def test_the_replay_cache_holds_no_keys_and_no_legal_claims():
    for path in sorted(chat_llm.REPLAY_DIR.glob("*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        text = body["text"] if isinstance(body, dict) else str(body)
        assert not re.search(r"(sk-|AIza|gsk_|api[_-]?key)", text, re.I), path.name
        assert not chat.LEGAL.search(text), path.name
