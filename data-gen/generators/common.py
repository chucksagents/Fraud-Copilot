"""
Shared helpers for the data-gen generators: deterministic seeding, output
paths, and small synthetic reference pools (names, cities, merchants).

No third-party dependencies on purpose — these scripts should run with a
bare `python3` and nothing else installed.
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "data-gen" / "fixtures"

DEFAULT_SEED = 1337

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Amara",
    "Priya", "Wei", "Fatima", "Diego", "Sofia", "Kwame", "Aisha", "Liam",
    "Noor",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Chen", "Kumar", "Nguyen", "Okafor", "Haddad", "Kowalski", "Andersson",
]

CITIES = [
    ("New York", "US", 40.7128, -74.0060),
    ("Chicago", "US", 41.8781, -87.6298),
    ("Austin", "US", 30.2672, -97.7431),
    ("Toronto", "CA", 43.6532, -79.3832),
    ("London", "GB", 51.5074, -0.1278),
    ("Dublin", "IE", 53.3498, -6.2603),
    ("Berlin", "DE", 52.5200, 13.4050),
    ("Lagos", "NG", 6.5244, 3.3792),
    ("Singapore", "SG", 1.3521, 103.8198),
    ("Sydney", "AU", -33.8688, 151.2093),
    ("Sao Paulo", "BR", -23.5505, -46.6333),
    ("Mumbai", "IN", 19.0760, 72.8777),
]

# Cities used only as "impossible travel" / high-risk injection points —
# geographically far from everything above.
FAR_FLUNG_CITIES = [
    ("Reykjavik", "IS", 64.1466, -21.9426),
    ("Ulaanbaatar", "MN", 47.8864, 106.9057),
    ("Nairobi", "KE", -1.2921, 36.8219),
    ("Manila", "PH", 14.5995, 120.9842),
]

MERCHANT_CATEGORIES = [
    "grocery", "restaurant", "gas_station", "electronics", "travel",
    "online_retail", "utilities", "entertainment", "pharmacy",
    "home_improvement", "clothing", "subscription",
]

MERCHANT_NAME_STEMS = [
    "Northgate", "Riverside", "Summit", "Cedar", "Harbor", "Union",
    "Pioneer", "Lakeside", "Maple", "Granite", "Meridian", "Coastal",
    "Foothill", "Wellspring", "Ironwood", "Brightline",
]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]
DEVICE_OS = {
    "mobile": ["iOS 17", "Android 14"],
    "desktop": ["Windows 11", "macOS 15"],
    "tablet": ["iPadOS 17", "Android 14"],
}


def rng(seed: int = DEFAULT_SEED) -> random.Random:
    return random.Random(seed)


def new_id(prefix: str, r: random.Random | None = None) -> str:
    """Stable-looking synthetic id. Uses uuid4 for global uniqueness."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def write_json(name: str, data: Any) -> Path:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / name
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")
    return path


def load_json(name: str) -> Any:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)
