"""Human-readable labels for raw feature names, in one place.

Each feature maps to:
- ``label``: a short sentence-case description ("Short on sleep over the last 3 days").
- ``note``: a gentle two-to-four word lowercase reason for the UI ("short on sleep").
"""

from __future__ import annotations

import re

FEELING_WORDS = {
    "mood": "mood",
    "energy": "energy",
    "stress": "stress",
    "anxiety": "anxiety",
    "focus": "focus",
}

FIELD_WORDS = {
    "sleep_hours": ("Hours of sleep", "your sleep"),
    "sleep_quality": ("Sleep quality", "how you slept"),
    "exercise_minutes": ("Time spent exercising", "moving your body"),
    "outdoor_minutes": ("Time spent outdoors", "time outdoors"),
    "screen_time_hours": ("Screen time", "screen time"),
    "caffeine_servings": ("Caffeine", "caffeine"),
    "alcohol_units": ("Alcohol", "alcohol"),
    "meals_eaten": ("Meals eaten", "regular meals"),
    "social_interaction": ("Time with people", "time with friends"),
    "workload": ("Workload", "a heavy workload"),
}

EXACT: dict[str, tuple[str, str]] = {
    "sleep_debt_3d": ("Short on sleep over the last 3 days", "short on sleep"),
    "days_since_last_log": ("Days since your last check-in", "a few quiet days"),
    "target_dow_sin": ("Day of the week", "the day of the week"),
    "target_dow_cos": ("Day of the week", "the day of the week"),
    "target_is_weekend": ("Tomorrow is a weekend day", "weekend ahead"),
    "low_mood_streak": ("Several low days in a row", "a heavy stretch"),
    "exercise_streak": ("Days in a row with exercise", "staying active"),
    "recent_trend": ("Your recent trend", "your recent days"),
    "day_of_week": ("How this weekday usually goes", "the day of the week"),
}


def _feeling_label(feeling: str, rest: str) -> tuple[str, str] | None:
    w = FEELING_WORDS[feeling]
    if rest == "lag0":
        return (f"Today's {w}", f"today's {w}")
    if rest == "lag1":
        return (f"Yesterday's {w}", f"yesterday's {w}")
    if rest == "lag2":
        return (f"Your {w} two days ago", f"{w} lately")
    if rest == "delta_7d":
        return (f"Today's {w} compared with your week", f"{w} vs. your week")
    return None


def describe(feature: str, custom_names: dict[str, str] | None = None) -> tuple[str, str]:
    """Return ``(label, note)`` for a raw feature name."""
    names = custom_names or {}
    if feature in names:
        return (f"{names[feature]} today", names[feature].lower())
    if feature.startswith("missing_") and feature[8:] in names:
        return (f"No entry for {names[feature[8:]]} today", "a lighter check-in")
    if feature in EXACT:
        return EXACT[feature]

    m = re.fullmatch(r"(mood|energy|stress|anxiety|focus)_(lag\d|delta_7d)", feature)
    if m:
        res = _feeling_label(m.group(1), m.group(2))
        if res:
            return res

    m = re.fullmatch(r"(.+)_(mean|std)_(\d+)d", feature)
    if m:
        base, stat, w = m.groups()
        word = FEELING_WORDS.get(base) or FIELD_WORDS.get(base, (base, base))[1]
        nice = (
            FIELD_WORDS.get(base, (base.capitalize(), base))[0]
            if base in FIELD_WORDS
            else (word.capitalize())
        )
        if stat == "mean":
            return (f"{nice} over the last {w} days", f"{word} lately")
        return (f"How much your {word} has varied over {w} days", f"up-and-down {word}")

    m = re.fullmatch(r"missing_(.+)", feature)
    if m:
        base = m.group(1)
        word = FIELD_WORDS.get(base, (base, base))[1]
        return (f"No entry for {word} today", "a lighter check-in")

    m = re.fullmatch(r"tag_(.+?)(_3d)?", feature)
    if m:
        tag = m.group(1).replace("_", " ")
        if m.group(2):
            return (f"'{tag}' in the last 3 days", tag)
        return (f"Tagged '{tag}' today", tag)

    m = re.fullmatch(r"base_(ewma|mean|dowoff)_(mood|energy|stress)", feature)
    if m:
        kind = m.group(1)
        if kind == "dowoff":
            return EXACT["day_of_week"]
        if kind == "ewma":
            return EXACT["recent_trend"]
        return (f"Your usual {m.group(2)}", f"your usual {m.group(2)}")

    if feature in FIELD_WORDS:
        label, note = FIELD_WORDS[feature]
        return (f"{label} today", note)

    m = re.fullmatch(r"cm_(\d+)", feature)
    if m:
        return ("One of your own trackers", "your own tracker")

    return (feature.replace("_", " ").capitalize(), feature.replace("_", " "))
