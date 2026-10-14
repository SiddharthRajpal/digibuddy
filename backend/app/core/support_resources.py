"""Region-specific support resources shown when a check-in or forecast suggests a hard time.

The product team must verify these numbers before launch and keep them current.
Add a region by adding an entry to ``RESOURCES`` and, if needed, timezone hints to
``TIMEZONE_REGION``.
"""

from __future__ import annotations

from typing import TypedDict


class SupportResource(TypedDict):
    name: str
    phone: str | None
    url: str | None
    hours: str | None


RESOURCES: dict[str, list[SupportResource]] = {
    "SG": [
        {
            "name": "Samaritans of Singapore (SOS)",
            "phone": "1767",
            "url": "https://www.sos.org.sg",
            "hours": "24 hours",
        },
        {
            "name": "IMH Mental Health Helpline",
            "phone": "6389 2222",
            "url": "https://www.imh.com.sg",
            "hours": "24 hours",
        },
    ],
    "IN": [
        {
            "name": "Tele-MANAS",
            "phone": "14416",
            "url": "https://telemanas.mohfw.gov.in",
            "hours": "24 hours",
        },
    ],
    "INTL": [
        {
            "name": "Find A Helpline (international directory)",
            "phone": None,
            "url": "https://findahelpline.com",
            "hours": None,
        },
        {
            "name": "Local emergency services, if you are in immediate danger",
            "phone": None,
            "url": None,
            "hours": "24 hours",
        },
    ],
}

TIMEZONE_REGION: dict[str, str] = {
    "Asia/Singapore": "SG",
    "Singapore": "SG",
    "Asia/Kolkata": "IN",
    "Asia/Calcutta": "IN",
}

SUPPORT_MESSAGE = (
    "Today sounds really heavy. You don't have to carry it alone. "
    "If you'd like to talk to someone, these people are there to listen."
)


def region_for_timezone(tz: str, default: str = "INTL") -> str:
    return TIMEZONE_REGION.get(tz, default)


def resources_for_region(region: str) -> list[SupportResource]:
    return RESOURCES.get(region, RESOURCES["INTL"])
