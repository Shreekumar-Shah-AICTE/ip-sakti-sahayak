"""The Glossary (hi/gu -> en): conservative translation feeding the coverage gate."""

import yaml

from api.answer import answer
from api.i18n import GLOSSARY, STOP, detect, translate
from eval.run_eval import SETS


def test_detect_scripts():
    assert detect("Is Ayurveda patentable?") == "en"
    assert detect("संहिताबद्ध पारंपरिक ज्ञान क्या है?") == "hi"
    assert detect("સંહિતાબદ્ધ પરંપરાગત જ્ઞાન શું છે?") == "gu"


def test_english_is_untouched():
    assert translate("What is codified traditional knowledge?") is None
    assert answer("What is codified traditional knowledge?", "IN", "2026-09-01").translation is None


def test_known_words_translate_and_stopwords_drop():
    t = translate("संहिताबद्ध पारंपरिक ज्ञान क्या है?")
    assert t.terms == ["codified", "traditional", "knowledge"] and not t.unknown


def test_gujarati_case_suffix_stripped_only_onto_a_headword():
    t = translate("કઈ પેટન્ટ કચેરીઓને ટીકેડીએલની ઍક્સેસ છે?")
    assert "tkdl" in t.terms and "office" in t.terms and not t.unknown


def test_unknown_words_stay_in_the_coverage_denominator():
    # GST is deliberately not in the glossary: its word must remain an unmatched term,
    # so a partial translation can only make admission harder.
    t = translate("आयुर्वेदिक सौंदर्य प्रसाधनों पर जीएसटी की दर क्या है?")
    assert "जीएसटी" in t.unknown and "जीएसटी" in t.terms
    a = answer("आयुर्वेदिक सौंदर्य प्रसाधनों पर जीएसटी की दर क्या है?", "IN", "2026-09-01")
    assert a.abstain


def test_patentable_phrase_mirrors_english_l06():
    hi = translate("क्या भारत में आयुर्वेदिक दवा का पेटेंट कराया जा सकता है?")
    assert "patentable" in hi.terms and "patent" not in hi.terms


def test_translated_answer_quotes_are_verbatim_english():
    a = answer("संहिताबद्ध पारंपरिक ज्ञान क्या है?", "IN", "2026-09-01")
    assert not a.abstain and a.translation["lang"] == "hi"
    assert any(q.chunk_id.startswith("in-bd-amendment-act-2023#") for q in a.quotes)


def test_no_glossary_word_is_a_stopword_and_no_entry_only_serves_d_items():
    for lang in GLOSSARY:
        assert not (set(GLOSSARY[lang]) & STOP[lang])
    d_text = " ".join(q["question"] for q in yaml.safe_load(
        (SETS / "multilingual.yaml").read_text(encoding="utf-8")) if q["set"] == "D")
    l_text = " ".join(q["question"] for q in yaml.safe_load(
        (SETS / "multilingual.yaml").read_text(encoding="utf-8")) if q["set"] == "L")
    for lang in GLOSSARY:
        for head in GLOSSARY[lang]:
            if head in d_text:
                assert head in l_text, f"glossary entry {head!r} motivated only by a D item"


# ---------------------------------------------------------------------------------------
# UI translation parity. The interface ships in the bundle (S6 rule 5), so a missing string
# shows up as an English word in a Hindi demo rather than as a failing build. Catch it here.
# ---------------------------------------------------------------------------------------
import re  # noqa: E402
from pathlib import Path  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "web" / "src"


def _object_after(source: str, marker: str) -> str:
    """Return the body of the first `{...}` that follows `marker`, brace-matched."""
    start = source.index(marker) + len(marker)
    start = source.index("{", start)
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : i]
    raise AssertionError(f"unbalanced braces after {marker!r}")


def _keys(body: str) -> set[str]:
    depth = 0
    keys = set()
    for line in body.split("\n"):
        if depth == 0:
            m = re.match(r'\s*"?([A-Za-z_][\w]*)"?\s*:', line)
            if m:
                keys.add(m.group(1))
        depth += line.count("{") + line.count("[") - line.count("}") - line.count("]")
    return keys


def _trilingual(path: str, marker: str) -> None:
    source = (WEB / path).read_text(encoding="utf-8")
    table = _object_after(source, marker)
    english = _keys(_object_after(table, "en:"))
    assert english, f"{marker}: no English keys found"
    for lang in ("hi:", "gu:"):
        missing = english - _keys(_object_after(table, lang))
        assert not missing, f"{marker} {lang} missing {sorted(missing)}"


def test_interface_strings_exist_in_every_language():
    _trilingual("i18n.ts", "export const STRINGS")


def test_plain_words_explanations_exist_in_every_language():
    for marker in ("export const PLAIN_STATUS_L", "export const CONFIDENCE_PLAIN_L",
                   "export const PLAIN_LINES"):
        _trilingual("explain.ts", marker)
