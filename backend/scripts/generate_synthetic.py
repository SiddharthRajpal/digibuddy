"""Generate realistic synthetic DigiBuddy users.

Next-day mood (and energy, stress) depends on today's sleep, sleep debt, exercise,
workload and social time, plus a weekly cycle and an AR(1) noise process, so the
models have something real to learn. Profiles:

- ``strong``: clear signal, little noise.
- ``weak``: some signal, more noise.
- ``noise``: almost pure noise. Inputs have no effect; feelings are noise around a
  slowly drifting level (a local-level process, for which exponential smoothing is
  close to optimal). No model should beat the baseline.

About 20% of optional fields are missing and about 10% of days are skipped.

Usage::

    python -m scripts.generate_synthetic --profile strong --days 120 --out data.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np

OPTIONAL_FIELDS = (
    "sleep_hours",
    "sleep_quality",
    "exercise_minutes",
    "outdoor_minutes",
    "screen_time_hours",
    "caffeine_servings",
    "alcohol_units",
    "meals_eaten",
    "social_interaction",
    "workload",
)


@dataclass(frozen=True)
class Profile:
    name: str
    signal: float
    noise_sd: float
    ar_phi: float
    weekly_amp: float


PROFILES: dict[str, Profile] = {
    "strong": Profile("strong", signal=1.5, noise_sd=0.5, ar_phi=0.3, weekly_amp=1.0),
    "weak": Profile("weak", signal=0.5, noise_sd=1.0, ar_phi=0.4, weekly_amp=0.5),
    "noise": Profile("noise", signal=0.0, noise_sd=1.2, ar_phi=0.0, weekly_amp=0.0),
}


def _clip_int(v: float, lo: int = 1, hi: int = 10) -> int:
    return int(min(hi, max(lo, round(v))))


def generate_user(
    profile: str | Profile = "strong",
    days: int = 120,
    start: date | None = None,
    seed: int = 0,
    missing_rate: float = 0.2,
    skip_rate: float = 0.1,
) -> list[dict[str, Any]]:
    p = PROFILES[profile] if isinstance(profile, str) else profile
    rng = np.random.default_rng(seed)
    start = start or (date.today() - timedelta(days=days))
    b = p.signal

    inputs: list[dict[str, Any]] = []
    for d in range(days):
        day = start + timedelta(days=d)
        weekend = day.weekday() >= 5
        short_night = rng.random() < 0.15
        sleep = float(np.clip(rng.normal(5.0, 0.7) if short_night else rng.normal(7.3, 0.9), 3, 11))
        exercised = rng.random() < (0.35 if weekend else 0.45)
        exercise = int(max(10, rng.normal(40, 15))) if exercised else 0
        workload = _clip_int(rng.normal(2.0, 0.8) if weekend else rng.normal(3.6, 0.9), 1, 5)
        social = _clip_int(rng.normal(3.8, 0.9) if weekend else rng.normal(2.6, 1.0), 1, 5)
        tags: list[str] = []
        if exercised:
            tags.append("gym")
        if not weekend and rng.random() < 0.12:
            tags.append("deadline")
        if rng.random() < 0.06:
            tags.append("sick")
        if weekend and rng.random() < 0.25:
            tags.append("date")
        if rng.random() < 0.05:
            tags.append("travel")
        if 40 <= d % 60 <= 46 and not weekend:
            tags.append("exam")
        inputs.append(
            {
                "date": day,
                "sleep_hours": round(sleep, 1),
                "sleep_quality": _clip_int(1 + (sleep - 4) * 0.7 + rng.normal(0, 0.5), 1, 5),
                "exercise_minutes": exercise,
                "outdoor_minutes": int(max(0, rng.normal(60 if weekend else 25, 20))),
                "screen_time_hours": round(float(np.clip(rng.normal(5.5, 1.5), 0.5, 14)), 1),
                "caffeine_servings": int(rng.poisson(1.6)),
                "alcohol_units": int(rng.poisson(1.5 if weekend else 0.2)),
                "meals_eaten": _clip_int(rng.normal(3, 0.6), 0, 5),
                "social_interaction": social,
                "workload": workload,
                "tags": tags,
            }
        )

    e_mood = e_energy = e_stress = 0.0
    lv = {"mood": 0.0, "energy": 0.0, "stress": 0.0}
    records: list[dict[str, Any]] = []
    for d in range(days):
        day = inputs[d]["date"]
        dow = day.weekday()
        weekly = p.weekly_amp * (0.6 if dow >= 5 else (-0.5 if dow == 0 else 0.0))
        e_mood = p.ar_phi * e_mood + rng.normal(0, p.noise_sd)
        e_energy = p.ar_phi * e_energy + rng.normal(0, p.noise_sd)
        e_stress = p.ar_phi * e_stress + rng.normal(0, p.noise_sd)
        if p.signal == 0.0:
            for k in lv:
                lv[k] = 0.97 * lv[k] + rng.normal(0, 0.3)
            mood = 6.0 + lv["mood"] + rng.normal(0, p.noise_sd)
            energy = 6.0 + lv["energy"] + rng.normal(0, p.noise_sd)
            stress = 5.0 + lv["stress"] + rng.normal(0, p.noise_sd)
        elif d == 0:
            mood, energy, stress = 6.0 + e_mood, 6.0 + e_energy, 5.0 + e_stress
        else:
            prev = inputs[d - 1]
            debt = sum(7.0 - inputs[k]["sleep_hours"] for k in range(max(0, d - 3), d))
            ex = 1.0 if prev["exercise_minutes"] > 0 else 0.0
            tag_effect = (-1.5 if "sick" in prev["tags"] else 0.0) + (
                0.8 if "date" in prev["tags"] else 0.0
            )
            pressure = 1.2 if ("exam" in prev["tags"] or "deadline" in prev["tags"]) else 0.0
            mood = (
                6.0
                + b
                * (
                    0.6 * (prev["sleep_hours"] - 7)
                    - 0.35 * debt
                    + 0.8 * ex
                    - 0.5 * (prev["workload"] - 3)
                    + 0.5 * (prev["social_interaction"] - 3)
                    + tag_effect
                )
                + weekly
                + e_mood
            )
            energy = (
                6.0
                + b * (0.7 * (prev["sleep_hours"] - 7) + 0.6 * ex - 0.3 * debt)
                + 0.5 * weekly
                + e_energy
            )
            stress = (
                5.0
                + b * (0.9 * (prev["workload"] - 3) - 0.3 * (prev["sleep_hours"] - 7) + pressure)
                - 0.5 * weekly
                + e_stress
            )
        rec: dict[str, Any] = {
            "date": day,
            "mood": _clip_int(mood),
            "energy": _clip_int(energy),
            "stress": _clip_int(stress),
            "anxiety": _clip_int(0.6 * stress + 1.5 + rng.normal(0, 0.8)),
            "focus": _clip_int(0.5 * energy + 2.5 + rng.normal(0, 0.8)),
            **{k: v for k, v in inputs[d].items() if k != "date"},
            "notes": None,
        }
        for f in OPTIONAL_FIELDS:
            if rng.random() < missing_rate:
                rec[f] = None
        records.append(rec)

    keep = [r for i, r in enumerate(records) if i < 3 or rng.random() >= skip_rate]
    return keep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="strong")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()
    data = generate_user(args.profile, args.days, seed=args.seed)
    text = json.dumps(data, default=str, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
