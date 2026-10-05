"""Deterministic demo data for the credential-free provider.

Placeholder research data so the app runs fully end-to-end and is testable with
no external services. It is NOT real market data.

Design: states/cities/neighborhoods are enumerated compactly here. Factor scores
are derived deterministically by the provider from stable hashes so results are
reproducible. A curated OVERRIDES table makes the flagship demo read
intentionally and demonstrates withheld-total behavior when evidence is missing.

Demo "sources" are stable so citation-integrity tests are deterministic.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# --- U.S. states: abbreviation -> full name -------------------------------
US_STATES: Dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

_STATE_NAME_TO_ABBR = {name.lower(): abbr for abbr, name in US_STATES.items()}

# Recognized short-of-a-state regions/anchored metros for region validation.
KNOWN_METROS = {
    "new york": "NY", "los angeles": "CA", "chicago": "IL", "houston": "TX",
    "dallas": "TX", "austin": "TX", "seattle": "WA", "boston": "MA",
    "san francisco": "CA", "denver": "CO", "miami": "FL", "atlanta": "GA",
}


def normalize_region(raw: str) -> Optional[str]:
    """Return a canonical region key (a U.S. state abbreviation), or None.

    Recognizes full state names, two-letter abbreviations, and known metro
    names. Unrecognized text is rejected so we do not research arbitrary,
    non-U.S. locations.
    """
    text = (raw or "").strip()
    if not text:
        return None
    key = text.lower()
    if key in _STATE_NAME_TO_ABBR:
        return _STATE_NAME_TO_ABBR[key]
    if text.upper() in US_STATES:
        return text.upper()
    if key in US_STATES:
        return key
    if key in KNOWN_METROS:
        return KNOWN_METROS[key]
    cleaned = key.replace(" metro", "").replace(" metropolitan area", "").replace(
        " region", "").replace(" area", "").strip()
    if cleaned in KNOWN_METROS:
        return KNOWN_METROS[cleaned]
    return None


def state_name(abbr: str) -> str:
    return US_STATES.get(abbr, abbr)


# --- Candidate cities, ordered by demo preference per state -----------------
CITY_TIERS: Dict[str, List[str]] = {
    "IL": ["Chicago", "Evanston", "Oak Park", "Champaign", "Naperville", "Bloomington"],
    "CA": ["Los Angeles", "San Francisco", "Oakland", "Sacramento", "Long Beach"],
    "TX": ["Austin", "Houston", "Dallas", "San Antonio", "Fort Worth"],
    "WA": ["Seattle", "Bellevue", "Tacoma", "Olympia", "Spokane"],
    "NY": ["New York", "Buffalo", "Rochester", "Albany", "Syracuse"],
    "MA": ["Boston", "Cambridge", "Somerville", "Salem", "Worcester"],
    "CO": ["Denver", "Boulder", "Colorado Springs", "Fort Collins", "Aurora"],
    "GA": ["Atlanta", "Savannah", "Decatur", "Alpharetta"],
    "OR": ["Portland", "Eugene", "Bend", "Salem"],
    "TN": ["Nashville", "Memphis", "Chattanooga", "Knoxville", "Franklin"],
}

GENERIC_CITIES = [
    "Riverside", "Fairview", "Claremont", "Westbrook", "Union City",
    "Kingston", "Madison", "Lexington", "Maplewood", "Arlington",
]

# --- Neighborhood names per city (generic fallback for unlisted cities) -----
NEIGHBORHOOD_NAMES: Dict[str, List[str]] = {
    "Chicago": [
        "Wicker Park", "Logan Square", "Andersonville", "Lakeview",
        "Pilsen", "Hyde Park", "Bridgeport",
    ],
    "Evanston": ["Downtown Evanston", "West Village", "Howard Street", "South Evanston"],
    "Oak Park": ["Lake Street Corridor", "Mills Park", "Forest Park Edge"],
    "Los Angeles": ["Silver Lake", "Echo Park", "Highland Park", "Arts District"],
    "Austin": ["South Congress", "East Austin", "Mueller"],
    "Seattle": ["Capitol Hill", "Ballard", "Fremont", "Columbia City"],
}

GENERIC_NEIGHBORHOODS = [
    "Downtown", "Midtown", "Old Town", "Riverside", "West End",
    "Northside", "Southside", "Central District", "Uptown", "Harborview",
]


# --- Curated overrides: an intentional demo, incl. missing-evidence case ------
# key: (city, neighborhood) -> {"factors": ..., "summary": ...}
OVERRIDES: Dict[Tuple[str, str], Dict] = {
    ("Chicago", "Wicker Park"): {
        "factors": {"audience": 5, "competition": 3, "affordability": 4,
                    "accessibility": 5, "momentum": 5},
        "summary": "Young, creative corridor with strong foot traffic and coffee culture.",
    },
    ("Chicago", "Logan Square"): {
        "factors": {"audience": 4, "competition": 3, "affordability": 4,
                    "accessibility": 4, "momentum": 5},
        "summary": "Rising dining/coffee scene with good transit and neighborhood feel.",
    },
    ("Chicago", "Andersonville"): {
        "factors": {"audience": 4, "competition": 2, "affordability": 4,
                    "accessibility": 3, "momentum": 4},
        "summary": "Established, community-oriented corridor with a loyal local base.",
    },
    ("Chicago", "Lakeview"): {
        "factors": {"audience": 4, "competition": 4, "affordability": 3,
                    "accessibility": 5, "momentum": 4},
        "summary": "Dense, lively area but with more established competition.",
    },
    ("Chicago", "Pilsen"): {
        "factors": {"audience": 4, "competition": 2, "affordability": 4,
                    "accessibility": 3, "momentum": 4},
        "summary": "Culturally rich, arts-led neighborhood drawing interest.",
    },
    # Hyde Park demonstrates withheld-total behavior: several factors are
    # unavailable due to weak evidence in the demo dataset.
    ("Chicago", "Hyde Park"): {
        "factors": {"audience": None, "competition": 2, "affordability": None,
                    "accessibility": 3, "momentum": None},
        "summary": "University-anchored area; several factors lack reliable demo evidence.",
    },
    ("Chicago", "Bridgeport"): {
        "factors": {"audience": 3, "competition": 2, "affordability": 4,
                    "accessibility": 3, "momentum": 4},
        "summary": "Quietly growing neighborhood with light competition.",
    },
    ("Evanston", "Downtown Evanston"): {
        "factors": {"audience": 4, "competition": 3, "affordability": 3,
                    "accessibility": 4, "momentum": 3},
        "summary": "Walkable downtown near transit; moderate competition.",
    },
    ("Los Angeles", "Silver Lake"): {
        "factors": {"audience": 5, "competition": 4, "affordability": 3,
                    "accessibility": 3, "momentum": 4},
        "summary": "Creative, cafe-dense but culture-rich district.",
    },
    ("Austin", "East Austin"): {
        "factors": {"audience": 4, "competition": 3, "affordability": 3,
                    "accessibility": 3, "momentum": 5},
        "summary": "Creative growth corridor with rising local interest.",
    },
    ("Seattle", "Capitol Hill"): {
        "factors": {"audience": 5, "competition": 4, "affordability": 2,
                    "accessibility": 5, "momentum": 4},
        "summary": "Dense, creative, coffee-saturated neighborhood.",
    },
}

# Stable demo source objects used to back citations.
DEMO_SOURCES: List[Tuple[str, str]] = [
    ("Neighborhood Demographics (demo)", "https://demo.example.com/demographics"),
    ("Commercial Rent Index (demo)", "https://demo.example.com/data/rents"),
    ("Transit & Foot Traffic Report (demo)", "https://demo.example.com/mobility"),
    ("Local Business Registry (demo)", "https://demo.example.com/registry"),
    ("Development Pipeline Bulletin (demo)", "https://demo.example.com/development"),
]


def hash_between(text: str, lo: int, hi: int) -> int:
    """Deterministic pseudo-random integer in [lo, hi] derived from a string."""
    digest = sum(ord(c) * (i + 1) for i, c in enumerate(text))
    return lo + (digest % (hi - lo + 1))