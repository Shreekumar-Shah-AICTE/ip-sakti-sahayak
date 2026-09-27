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
