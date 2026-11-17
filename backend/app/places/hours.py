"""Turn opening-hours text into OpenStreetMap's standard format.

Sources write hours as free text ("Daily 6AM-11PM", "Tue-Sun 10:00-17:00 (closed Mon)").
We convert what we fully understand into the OSM `opening_hours` format
("Mo-Su 06:00-23:00"), which the `opening-hours-py` library can then answer
"is it open at this time?" for (used by the verifier, Feature #12).

The rule is: **never guess**. A wrong "open" answer is worse than no answer, so if any
part of the text is unfamiliar (seasons, "happy hour", "until 19:00 on Fridays",
"last order" is the one exception, see below) the result is `None` and the original
text stays available for people to read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from opening_hours import OpeningHours

_DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_OSM_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_DAY_WORDS: dict[str, int] = {}
for _i, _name in enumerate(_DAY_NAMES):
    _full = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][_i]
    for _w in (_name, _full, _name[:2]):
        _DAY_WORDS[_w] = _i
_DAY_WORDS.update({"tues": 1, "weds": 2, "thur": 3, "thurs": 3})

ALL_DAYS = frozenset(range(7))
_FILLER = {"and", "on", "open", "from", "every", "each"}
_MAX_OVERNIGHT_MINUTES = 17 * 60  # longer than this is probably a typo like 17:30-12:00

# Notes that don't change the hours at all.
_HARMLESS = re.compile(r"\(\s*last (?:order|entry|admission)[^)]*\)")

_TIME = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
_TOKEN = re.compile(
    rf"""
    (?P<time>{_TIME}\s*-\s*{_TIME})
  | (?P<h24>24\s*hours?)
  | (?P<word>[a-z]+)(?:\s*-\s*(?P<word2>[a-z]+))?
  | (?P<punct>[,;()&/:.])
  | (?P<space>\s+)
    """,
    re.VERBOSE,
)


class _Fail(Exception):
    """The text has something we don't fully understand."""


class _Reject(_Fail):
    """The text is clearly wrong or ambiguous (e.g. '10-5', '10:00-10:00'). No fallback."""


@dataclass
class _Group:
    days: set[int] = field(default_factory=set)
    explicit_days: bool = False
    ranges: list[tuple[int, int]] = field(default_factory=list)  # minutes from midnight
    closed: bool = False
    all_day: bool = False


def parse_hours(text: str | None) -> str | None:
    """Return OSM-format hours, or None when the text isn't fully understood."""
    if not text:
        return None
    try:
        spec = _from_text(text)
    except _Reject:
        return None
    except _Fail:
        spec = None
    if spec is None:
        spec = _as_osm(text)  # text that is already valid OSM format, e.g. from OpenStreetMap
    return spec


_PUBLIC_HOLIDAY_RULE = re.compile(r";?\s*PH\s+(?:off|closed)\s*$", re.IGNORECASE)


def _as_osm(text: str) -> str | None:
    candidate = _PUBLIC_HOLIDAY_RULE.sub("", text.strip()).strip(" ;")
    return candidate if candidate and _valid(candidate) else None


def _valid(spec: str) -> bool:
    try:
        OpeningHours(spec)
    except Exception:
        return False
    return True


# ---- reading the text --------------------------------------------------------------


def _from_text(raw: str) -> str | None:
    text = _HARMLESS.sub(" ", raw.lower())
    text = text.replace("–", "-").replace("—", "-").replace("‒", "-").replace("~", "-")
    text = re.sub(r"\severy ?day\b", " daily", text)
    text = re.sub(r"\beveryday\b", "daily", text)
    text = re.sub(rf"({_TIME})\s+to\s+(?={_TIME})", r"\1-", text)
    tokens = _tokenize(text)
    groups, _ = _group(tokens)
    return _render(groups)


def _tokenize(text: str) -> list[tuple[str, re.Match[str]]]:
    tokens: list[tuple[str, re.Match[str]]] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:
            raise _Fail(f"unreadable text at {text[pos : pos + 10]!r}")
        pos = match.end()
        if match.group("space"):
            continue
        tokens.append((_kind(match), match))
    return tokens


def _kind(match: re.Match[str]) -> str:
    if match.group("time"):
        return "time"
    if match.group("h24"):
        return "h24"
    if match.group("word"):
        return "dayrange" if match.group("word2") else "word"
    return "punct"


def _group(tokens: list[tuple[str, re.Match[str]]]) -> tuple[list[_Group], bool]:
    groups: list[_Group] = []
    current: _Group | None = None
    holidays_off = False

    def time_ahead(index: int) -> bool:
        for kind, m in tokens[index + 1 :]:
            if kind == "time" or kind == "h24":
                return True
            if kind == "punct" and m.group("punct") in ";)":
                return False
        return False

    for index, (kind, match) in enumerate(tokens):
        if kind == "punct":
            if match.group("punct") in ";)" and current is not None and current.closed:
                current = None
            continue

        if kind in ("time", "h24"):
            if current is None:
                current = _Group(days=set(ALL_DAYS))
                groups.append(current)
            if current.closed:
                raise _Reject("times after 'closed'")
            if kind == "h24":
                current.all_day = True
            else:
                current.ranges.append(_range(match))
            continue

        words = _day_set(kind, match)
        if words is not None:
            if current is not None and current.closed:
                current.days |= words
            elif current is None or (current.ranges or current.all_day):
                if current is not None and not time_ahead(index):
                    # Days written after the times: "17:00-21:00 on Fri, Sat".
                    current.days = (current.days if current.explicit_days else set()) | words
                    current.explicit_days = True
                else:
                    current = _Group(days=set(words), explicit_days=True)
                    groups.append(current)
            else:
                current.days |= words
            continue

        word = match.group("word")
        if word == "closed":
            current = _Group(closed=True)
            groups.append(current)
        elif word in ("holiday", "holidays"):
            if current is None or not current.closed:
                raise _Reject("holiday hours")
            holidays_off = True
        elif word in _FILLER:
            continue
        else:
            raise _Fail(f"unknown word {word!r}")
    return groups, holidays_off


def _day_set(kind: str, match: re.Match[str]) -> set[int] | None:
    word = match.group("word") if kind != "time" else None
    if word is None:
        return None
    if kind == "dayrange":
        start, end = _day(word), _day(match.group("word2"))
        if start is None or end is None:
            raise _Fail("bad day range")
        count = (end - start) % 7 + 1
        return {(start + i) % 7 for i in range(count)}
    if word in ("daily", "everyday"):
        return set(ALL_DAYS)
    if word == "weekdays":
        return set(range(5))
    if word == "weekends":
        return {5, 6}
    day = _day(word)
    return {day} if day is not None else None


def _day(word: str | None) -> int | None:
    if word is None:
        return None
    if word in _DAY_WORDS:
        return _DAY_WORDS[word]
    if word.endswith("s") and word[:-1] in _DAY_WORDS and len(word) > 4:
        return _DAY_WORDS[word[:-1]]  # "sundays"
    return None


def _range(match: re.Match[str]) -> tuple[int, int]:
    """Minutes-from-midnight (start, end) for a matched 'time-time' token."""
    h1, m1, s1, h2, m2, s2 = match.group(2, 3, 4, 5, 6, 7)
    # "3-6PM": one am/pm at the end applies to both sides; "9am-5": the start's applies to both.
    if s1 is None and s2 == "pm" and int(h1) <= int(h2):
        s1 = s2
    if s2 is None and s1 is not None:
        s2 = s1
    if s1 is None and s2 is None and m1 is None and m2 is None:
        raise _Reject("ambiguous hours like '10-5'")
    start = _minutes(int(h1), int(m1 or 0), s1)
    end = _minutes(int(h2), int(m2 or 0), s2)
    if end == 0 and start > 0:
        end = 24 * 60
    if end == start:
        raise _Reject("zero-length hours")
    if end < start and (end + 24 * 60 - start) > _MAX_OVERNIGHT_MINUTES:
        raise _Reject("overnight range too long to be right")
    return start, end


def _minutes(hour: int, minute: int, suffix: str | None) -> int:
    if suffix is not None:
        if not 1 <= hour <= 12:
            raise _Reject("bad 12-hour time")
        hour = hour % 12 + (12 if suffix == "pm" else 0)
    if hour > 24 or minute > 59 or (hour == 24 and minute != 0):
        raise _Reject("bad time")
    return hour * 60 + minute


# ---- writing OSM format -------------------------------------------------------------


def _render(groups: list[_Group]) -> str | None:
    open_by_day: dict[int, tuple[tuple[int, int], ...]] = {}
    closed_days: set[int] = set()
    saw_open_group = False
    for group in groups:
        if group.closed:
            closed_days |= group.days
            continue
        saw_open_group = True
        ranges = [(0, 24 * 60)] if group.all_day and not group.ranges else sorted(group.ranges)
        if not ranges:
            raise _Reject("days without times")
        for day in group.days:
            if day in open_by_day:
                raise _Reject("a day is described twice")
            open_by_day[day] = tuple(ranges)
    if not saw_open_group:
        return None
    for day in closed_days:
        open_by_day.pop(day, None)
    if not open_by_day:
        return None

    if len(set(open_by_day.values())) == 1 and len(open_by_day) == 7:
        only = next(iter(open_by_day.values()))
        spec = "24/7" if only == ((0, 24 * 60),) else f"Mo-Su {_ranges_text(only)}"
    else:
        by_ranges: dict[tuple[tuple[int, int], ...], list[int]] = {}
        for day in sorted(open_by_day):
            by_ranges.setdefault(open_by_day[day], []).append(day)
        first_day = {ranges: days[0] for ranges, days in by_ranges.items()}
        parts = [
            f"{_days_text(days)} {_ranges_text(ranges)}"
            for ranges, days in sorted(by_ranges.items(), key=lambda kv: first_day[kv[0]])
        ]
        spec = "; ".join(parts)
    # "closed on holidays" is dropped from the structured hours: we have no holiday calendar,
    # and the planner's hours parser rejects a whole string that contains "PH". The original
    # text ("closed weekends and holidays") is still kept in `opening_hours`.
    return spec if _valid(spec) else None


def _ranges_text(ranges: tuple[tuple[int, int], ...]) -> str:
    return ",".join(f"{_hhmm(a)}-{_hhmm(b)}" for a, b in ranges)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _days_text(days: list[int]) -> str:
    runs: list[list[int]] = []
    for day in days:
        if runs and day == runs[-1][-1] + 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    return ",".join(
        _OSM_DAYS[run[0]]
        if len(run) == 1
        else (
            f"{_OSM_DAYS[run[0]]},{_OSM_DAYS[run[1]]}"
            if len(run) == 2
            else f"{_OSM_DAYS[run[0]]}-{_OSM_DAYS[run[-1]]}"
        )
        for run in runs
    )
