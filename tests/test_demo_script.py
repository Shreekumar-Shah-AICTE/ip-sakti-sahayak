"""The demo script, as a test (M12).

docs/demo-script.md is the thing we perform on stage, so every scripted question and every
scripted outcome is asserted here against the keyless core. If the product's answer changes,
this fails and the script has to be rewritten — never the other way round.
"""

from pathlib import Path

import pytest

from api.answer import answer
from api.baseline import retrieve as static_retrieve

SCRIPT = Path(__file__).resolve().parent.parent / "docs" / "demo-script.md"

AD_QUESTION = "Can I advertise this classical formulation as a treatment for diabetes?"
HI_AD_QUESTION = "क्या मैं इस आयुर्वेदिक दवा का मधुमेह के इलाज के रूप में विज्ञापन कर सकता हूँ?"
ABSTAIN_QUESTION = "What is the GST rate on ayurvedic churna?"

# The four beats of PITCH_DEFENCE §3: date -> (status, sub judice, a phrase from the evidence).
BEATS = [
    ("2024-06-30", "in_force", False, "170"),
    ("2024-07-02", "omitted", False, "360(E)"),
    ("2024-08-28", "in_force_stayed_omission", True, "27-08-2024"),  # interim order
    ("2025-08-12", "omitted_stay_vacated", False, "11-08-2025"),
]


@pytest.mark.parametrize("as_of,status,sub_judice,evidence", BEATS)
def test_each_scripted_date_gives_the_scripted_status(as_of, status, sub_judice, evidence):
    a = answer(AD_QUESTION, "IN", as_of).to_dict()
    assert not a["abstain"]
    assert a["confidence"] == "high"
    assert a["status"]["status"] == status
    assert a["status"]["sub_judice"] is sub_judice
    blob = a["status"]["summary"] + " ".join(
        q["text"] + q["doc_title"] + q["section"] for q in a["quotes"]
    )
    assert evidence in blob


@pytest.mark.parametrize("as_of,_s,_j,_e", BEATS)
def test_the_dmr_overlay_closes_every_date(as_of, _s, _j, _e):
    """The closing beat: "no" on all four dates, for four different reasons."""
    a = answer(AD_QUESTION, "IN", as_of).to_dict()
    overlay = [q for q in a["quotes"] if q["role"] == "overlay"]
    assert overlay, f"no DMR overlay at {as_of}"
    assert any("Diabetes" in q["text"] for q in overlay)


def test_the_timeline_strip_has_one_segment_per_beat():
    a = answer(AD_QUESTION, "IN", "2024-08-28").to_dict()
    tl = a["status"]["timeline"]
    assert [s["status"] for s in tl] == [b[1] for b in BEATS]


def test_the_hindi_beat_reaches_the_same_ledger_entry():
    en = answer(AD_QUESTION, "IN", "2024-08-28").to_dict()
    hi = answer(HI_AD_QUESTION, "IN", "2024-08-28").to_dict()
    assert hi["status"]["instrument"] == en["status"]["instrument"]
    assert hi["status"]["status"] == en["status"]["status"]
    assert hi["confidence"] == "high"


def test_the_abstention_beat_abstains_on_every_scripted_date():
    for as_of, *_ in BEATS:
        a = answer(ABSTAIN_QUESTION, "IN", as_of).to_dict()
        assert a["abstain"], as_of
        assert a["quotes"] == []


def test_the_static_rag_beat_cannot_tell_the_dates_apart():
    """The baseline's answer is identical on all four dates, because it never sees one."""
    runs = {tuple(c["chunk_id"] for c in static_retrieve(AD_QUESTION, "IN")) for _ in BEATS}
    assert len(runs) == 1
    assert runs.pop(), "the baseline must still return something — it never abstains"


def test_the_script_names_every_question_and_date_it_claims():
    text = SCRIPT.read_text(encoding="utf-8")
    for needle in [AD_QUESTION, ABSTAIN_QUESTION, "Compare with static RAG", "Abstention"]:
        assert needle in text
    for as_of, *_ in BEATS:
        assert as_of in text
