"""The Conversation — date phrases in chat ("on 15 Sep 2024", "what about July 2024?").

A chat message may carry its own as-of date. We find it, return the date and the message
with the date phrase removed (so date words never count against retrieval coverage), and
say which assumption we made for a partial date ("July 2024" -> 15 Jul 2024).
"""

from __future__ import annotations

import datetime as dt
import re

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_MON = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_PATTERNS = [
    ("iso", re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")),
    ("dmy", re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")),
    (
        "d_mon_y",
        re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MON + r",?\s+(\d{4})\b", re.I),
    ),
    ("mon_d_y", re.compile(r"\b" + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)),
    ("mon_y", re.compile(r"\b" + _MON + r",?\s+(\d{4})\b", re.I)),
    ("year", re.compile(r"\b(?:in|during|of|year)\s+((?:19|20)\d{2})\b", re.I)),
    ("today", re.compile(r"\b(today|now|currently|right now|at present)\b|आज|અત્યારે|આજે", re.I)),
]
# Filler that, with a date, makes a message a follow-up about the previous question.
FILLER = set(
    """and but ok okay so what how about if on in as of at back then the was is it date
same question there before after for again check try now today currently right present
please tell me say status law rule answer that this same situation और तब क्या अब तो उस दिन
અને હવે શું તો તે દિવસે""".split()
)


def _mon(s: str) -> int:
    return MONTHS[s.lower()[:4] if s.lower().startswith("sept") else s.lower()[:3]]


def find_date(text: str, today: dt.date | None = None) -> tuple[dt.date | None, str, str]:
    """(date, text without the date phrase, assumption note or '')."""
    today = today or dt.date.today()
    for kind, rx in _PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        g = m.groups()
        note = ""
        try:
            if kind == "iso":
                d = dt.date(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "dmy":
                d = dt.date(int(g[2]), int(g[1]), int(g[0]))
            elif kind == "d_mon_y":
                d = dt.date(int(g[2]), _mon(g[1]), int(g[0]))
            elif kind == "mon_d_y":
                d = dt.date(int(g[2]), _mon(g[0]), int(g[1]))
            elif kind == "mon_y":
                d = dt.date(int(g[1]), _mon(g[0]), 15)
                note = "mid-month"
            elif kind == "year":
                d = dt.date(int(g[0]), 6, 30)
                note = "mid-year"
            else:
                d = today
        except ValueError:
            continue
        rest = (text[: m.start()] + " " + text[m.end() :]).strip()
        rest = re.sub(
            r"\b(on|as of|as on|in|at|during|of)\s*([?.!,]*)\s*$", r"\2", rest, flags=re.I
        )
        return d, re.sub(r"\s{2,}", " ", rest).strip(), note
    return None, text, ""


def is_follow_up(rest: str) -> bool:
    """True when what is left after removing the date is only filler words."""
    words = re.findall(r"[\w\u0900-\u0aff]+", rest.lower())
    return all(w in FILLER for w in words)
