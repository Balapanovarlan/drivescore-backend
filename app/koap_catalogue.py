"""
Static catalogue of КоАП articles from формула.docx §3.
Used by seed and as the reference returned by GET /koap-articles.
"""

from typing import TypedDict


class KoapArticleDef(TypedDict):
    code: str
    name: str
    weight: int
    factor_group: str  # frontend ScoreFactor


KOAP_ARTICLES: list[KoapArticleDef] = [
    {
        "code": "Art.608 Part 1",
        "name": "Driving under influence (DUI)",
        "weight": 25,
        "factor_group": "accident",
    },
    {
        "code": "Art.613 Part 4",
        "name": "Refusal of intoxication examination",
        "weight": 30,
        "factor_group": "accident",
    },
    {
        "code": "Art.608 Part 3",
        "name": "DUI causing accident",
        "weight": 35,
        "factor_group": "accident",
    },
    {
        "code": "Art.612 Part 3",
        "name": "Driving without licence rights",
        "weight": 20,
        "factor_group": "harshAcceleration",
    },
    {
        "code": "Art.611 Part 2",
        "name": "Leaving accident scene",
        "weight": 18,
        "factor_group": "accident",
    },
    {
        "code": "Art.596 Part 3",
        "name": "Dangerous overtaking / opposite lane",
        "weight": 15,
        "factor_group": "harshBraking",
    },
    {
        "code": "Art.613 Part 1",
        "name": "Ignoring police stop request",
        "weight": 12,
        "factor_group": "harshBraking",
    },
    {
        "code": "Art.592 Part 3-1",
        "name": "Speeding over 60 km/h",
        "weight": 10,
        "factor_group": "speeding",
    },
    {"code": "Art.599", "name": "Running red light", "weight": 8, "factor_group": "redLight"},
    {
        "code": "Art.591",
        "name": "Phone usage while driving",
        "weight": 5,
        "factor_group": "phoneUsage",
    },
    {
        "code": "Art.593",
        "name": "Seatbelt violation",
        "weight": 3,
        "factor_group": "harshAcceleration",
    },
    {"code": "Art.592", "name": "Minor speeding", "weight": 2, "factor_group": "speeding"},
]

KOAP_BY_CODE = {a["code"]: a for a in KOAP_ARTICLES}
