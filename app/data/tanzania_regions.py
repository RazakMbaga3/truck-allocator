"""
app/data/tanzania_regions.py — Tanzania region/corridor master data.

All distances are road km from Kimbiji Plant, Kigamboni, Dar es Salaam.
Sources: LCL location master (Kilometer column), road network knowledge,
and confirmed Routes template data.

CORRIDORS: CENTRAL · NORTHERN · SOUTHERN_HIGHLAND · COASTAL · LAKE · SOUTHERN
"""

from __future__ import annotations

# ── Region definitions ────────────────────────────────────────────────────────
# Each entry: region_key → { display_name, corridor, km_from_plant }
REGIONS: dict[str, dict] = {
    "KIGAMBONI":        {"display": "Kigamboni (Plant)",   "corridor": "LOCAL",             "km": 0},
    "DSM":              {"display": "Dar es Salaam",        "corridor": "LOCAL",             "km": 15},
    "CHALINZE":         {"display": "Chalinze Junction",    "corridor": "ALL",               "km": 60},
    # CENTRAL corridor
    "MOROGORO":         {"display": "Morogoro",             "corridor": "CENTRAL",           "km": 200},
    "MIKUMI":           {"display": "Mikumi",               "corridor": "CENTRAL",           "km": 290},
    "DODOMA":           {"display": "Dodoma",               "corridor": "CENTRAL",           "km": 460},
    "SINGIDA":          {"display": "Singida",              "corridor": "CENTRAL",           "km": 620},
    "TABORA":           {"display": "Tabora",               "corridor": "LAKE",              "km": 850},
    "MWANZA":           {"display": "Mwanza",               "corridor": "LAKE",              "km": 1260},
    # NORTHERN corridor
    "SEGERA":           {"display": "Segera Junction",      "corridor": "NORTHERN",          "km": 300},
    "TANGA":            {"display": "Tanga",                "corridor": "NORTHERN",          "km": 360},
    "KOROGWE":          {"display": "Korogwe",              "corridor": "NORTHERN",          "km": 350},
    "MOSHI":            {"display": "Moshi",                "corridor": "NORTHERN",          "km": 570},
    "ARUSHA":           {"display": "Arusha",               "corridor": "NORTHERN",          "km": 640},
    # SOUTHERN HIGHLAND corridor
    "IRINGA":           {"display": "Iringa",               "corridor": "SOUTHERN_HIGHLAND", "km": 510},
    "MBEYA":            {"display": "Mbeya",                "corridor": "SOUTHERN_HIGHLAND", "km": 870},
    "NJOMBE":           {"display": "Njombe",               "corridor": "SOUTHERN_HIGHLAND", "km": 720},
    "MAKAMBAKO":        {"display": "Makambako Junction",   "corridor": "SOUTHERN_HIGHLAND", "km": 680},
    # COASTAL corridor (Gypsum Route R1 — confirmed from Routes template)
    "KIBITI":           {"display": "Kibiti",               "corridor": "COASTAL",           "km": 130},
    "UTETE":            {"display": "Utete",                "corridor": "COASTAL",           "km": 155},
    "NYAMISATI":        {"display": "Nyamisati",            "corridor": "COASTAL",           "km": 175},
    "IKWIRIRI":         {"display": "Ikwiriri",             "corridor": "COASTAL",           "km": 200},
    "KIBAHA":           {"display": "Kibaha",               "corridor": "COASTAL",           "km": 40},
    # SOUTHERN corridor (Songea / Ruvuma — Coal route)
    "SONGEA":           {"display": "Songea",               "corridor": "SOUTHERN",          "km": 1050},
    "NJINJO":           {"display": "Njinjo",               "corridor": "SOUTHERN",          "km": 850},
    "LINDI":            {"display": "Lindi",                "corridor": "SOUTHERN",          "km": 570},
    "MTWARA":           {"display": "Mtwara",               "corridor": "SOUTHERN",          "km": 600},
    "KIRANJERANJE":     {"display": "Kiranjeranje",         "corridor": "COASTAL",           "km": 220},
    # Iron Ore (CENTRAL corridor — Dodoma/Asanje area)
    "ASANJE":           {"display": "Asanje (Iron Ore)",    "corridor": "CENTRAL",           "km": 480},
    # Clinker sources
    "WAZO_HILL":        {"display": "Wazo Hill",            "corridor": "LOCAL",             "km": 25},
    "MAWENI":           {"display": "Maweni (Tanga area)",  "corridor": "NORTHERN",          "km": 360},
    # Lake zone
    "KYELA":            {"display": "Kyela",                "corridor": "SOUTHERN_HIGHLAND", "km": 920},
    "GEITA":            {"display": "Geita",                "corridor": "LAKE",              "km": 1310},
}


# ── Corridor waypoint sequences ───────────────────────────────────────────────
# Ordered from Kigamboni (plant) outward.
CORRIDOR_WAYPOINTS: dict[str, list[str]] = {
    "CENTRAL":           ["KIGAMBONI", "CHALINZE", "MOROGORO", "MIKUMI", "DODOMA", "SINGIDA", "TABORA", "MWANZA"],
    "NORTHERN":          ["KIGAMBONI", "CHALINZE", "SEGERA", "KOROGWE", "TANGA", "MOSHI", "ARUSHA"],
    "SOUTHERN_HIGHLAND": ["KIGAMBONI", "CHALINZE", "MOROGORO", "MIKUMI", "IRINGA", "MAKAMBAKO", "MBEYA", "KYELA"],
    "COASTAL":           ["KIGAMBONI", "KIBAHA", "KIBITI", "UTETE", "NYAMISATI", "IKWIRIRI", "KIRANJERANJE"],
    "LAKE":              ["KIGAMBONI", "CHALINZE", "MOROGORO", "DODOMA", "TABORA", "MWANZA", "GEITA"],
    "SOUTHERN":          ["KIGAMBONI", "CHALINZE", "MOROGORO", "MIKUMI", "IRINGA", "NJINJO", "SONGEA"],
    "LOCAL":             ["KIGAMBONI", "DSM"],
}


# ── Corridor ↔ RM origin mapping ─────────────────────────────────────────────
# Maps each RM origin region to its primary return corridor.
RM_ORIGIN_TO_CORRIDOR: dict[str, str] = {
    # CLINKER sources
    "TANGA":    "NORTHERN",
    "MAWENI":   "NORTHERN",
    # COAL sources
    "MBEYA":    "SOUTHERN_HIGHLAND",
    "KYELA":    "SOUTHERN_HIGHLAND",
    "SONGEA":   "SOUTHERN",
    # GYPSUM sources
    "LINDI":    "COASTAL",
    "KIRANJERANJE": "COASTAL",
    "MWANZA":   "LAKE",
    "DSM":      "LOCAL",
    # IRON ORE sources
    "DODOMA":   "CENTRAL",
    "ASANJE":   "CENTRAL",
    # General
    "MOROGORO": "CENTRAL",
    "IRINGA":   "SOUTHERN_HIGHLAND",
    "ARUSHA":   "NORTHERN",
    "MOSHI":    "NORTHERN",
    "TABORA":   "LAKE",
    "MTWARA":   "SOUTHERN",
}


# ── Road distance matrix (km) ─────────────────────────────────────────────────
# Confirmed road distances between key nodes.
# Key format: "FROM_TO" (alphabetical where A < B, but directional is OK here).
# The route_calculator will fill in missing pairs via Floyd-Warshall.
DISTANCE_MATRIX: dict[tuple[str, str], float] = {
    # From Kigamboni
    ("KIGAMBONI", "DSM"):           15,
    ("KIGAMBONI", "KIBAHA"):        40,
    ("KIGAMBONI", "CHALINZE"):      60,
    ("KIGAMBONI", "KIBITI"):        130,
    ("KIGAMBONI", "UTETE"):         155,
    ("KIGAMBONI", "NYAMISATI"):     175,
    ("KIGAMBONI", "IKWIRIRI"):      200,
    ("KIGAMBONI", "KIRANJERANJE"):  220,
    ("KIGAMBONI", "MOROGORO"):      200,
    ("KIGAMBONI", "SEGERA"):        300,
    ("KIGAMBONI", "TANGA"):         360,
    ("KIGAMBONI", "DODOMA"):        460,
    ("KIGAMBONI", "IRINGA"):        510,
    ("KIGAMBONI", "LINDI"):         570,
    ("KIGAMBONI", "MOSHI"):         570,
    ("KIGAMBONI", "MTWARA"):        600,
    ("KIGAMBONI", "ARUSHA"):        640,
    ("KIGAMBONI", "NJOMBE"):        720,
    ("KIGAMBONI", "IRINGA"):        510,
    ("KIGAMBONI", "MAKAMBAKO"):     680,
    ("KIGAMBONI", "TABORA"):        850,
    ("KIGAMBONI", "MBEYA"):         870,
    ("KIGAMBONI", "KYELA"):         920,
    ("KIGAMBONI", "SONGEA"):        1050,
    ("KIGAMBONI", "MWANZA"):        1260,
    ("KIGAMBONI", "GEITA"):         1310,
    # CENTRAL corridor legs
    ("CHALINZE",  "MOROGORO"):      140,
    ("MOROGORO",  "MIKUMI"):         90,
    ("MOROGORO",  "DODOMA"):        260,
    ("MIKUMI",    "DODOMA"):        170,
    ("DODOMA",    "SINGIDA"):       160,
    ("SINGIDA",   "TABORA"):        235,
    ("TABORA",    "MWANZA"):        410,
    ("MWANZA",    "GEITA"):          50,
    # NORTHERN corridor legs
    ("CHALINZE",  "SEGERA"):        240,
    ("SEGERA",    "TANGA"):          60,
    ("SEGERA",    "KOROGWE"):        50,
    ("KOROGWE",   "TANGA"):          60,
    ("KOROGWE",   "MOSHI"):         150,
    ("MOSHI",     "ARUSHA"):         80,
    ("TANGA",     "MOSHI"):         210,
    # SOUTHERN HIGHLAND legs
    ("MOROGORO",  "IRINGA"):        310,
    ("MIKUMI",    "IRINGA"):        220,
    ("IRINGA",    "MAKAMBAKO"):     170,
    ("IRINGA",    "MBEYA"):         360,
    ("MAKAMBAKO", "MBEYA"):         190,
    ("MBEYA",     "KYELA"):          50,
    ("IRINGA",    "NJOMBE"):        210,
    ("NJOMBE",    "SONGEA"):        330,
    # SOUTHERN legs
    ("IRINGA",    "NJINJO"):        340,
    ("NJINJO",    "SONGEA"):        200,
    # COASTAL legs (Route R1 — Gypsum)
    ("KIGAMBONI", "KIBAHA"):         40,
    ("KIBAHA",    "KIBITI"):         90,
    ("KIBITI",    "UTETE"):          25,
    ("UTETE",     "NYAMISATI"):      20,
    ("NYAMISATI", "IKWIRIRI"):       25,
    ("IKWIRIRI",  "KIRANJERANJE"):   20,
    # Cross-corridor
    ("DODOMA",    "IRINGA"):        260,
    ("DODOMA",    "TABORA"):        395,
    ("MOROGORO",  "IRINGA"):        310,
}


# ── Customer zone → corridor mapping ─────────────────────────────────────────
# Zone names are from Customer master / Location master data.
ZONE_TO_CORRIDOR: dict[str, str] = {
    # Project zones
    "Project 1":             "LOCAL",
    "Project 2":             "LOCAL",
    "Project 3":             "LOCAL",
    "Project 4":             "LOCAL",
    "Project 5":             "LOCAL",
    # Central zones
    "Central 1":             "CENTRAL",
    "Central 2":             "CENTRAL",
    # DSM zones
    "DAR ES SALAAM 1":       "LOCAL",
    "DAR ES SALAAM 2":       "LOCAL",
    "DAR ES SALAAM 3":       "LOCAL",
    "DAR ES SALAAM 4":       "LOCAL",
    "DAR ES SALAAM 5":       "LOCAL",
    # Southern Highland
    "Southern highland 1":   "SOUTHERN_HIGHLAND",
    "Southern highland 2":   "SOUTHERN_HIGHLAND",
    # Lake zone
    "Lake 1":                "LAKE",
    # Northern
    "Northern 1":            "NORTHERN",
    # Southern
    "Southern 1":            "SOUTHERN",
    "Coastal 1":             "COASTAL",
}


# ── City → Region normaliser ──────────────────────────────────────────────────
# Maps free-text city names from Odoo res.partner to canonical REGION keys.
# LCL location master has 859+ entries — these are the most frequent.
CITY_TO_REGION: dict[str, str] = {
    # DAR ES SALAAM variations
    "dar es salaam":        "DSM",
    "dar":                  "DSM",
    "dsm":                  "DSM",
    "ilala":                "DSM",
    "kinondoni":            "DSM",
    "temeke":               "DSM",
    "ubungo":               "DSM",
    "kigamboni":            "KIGAMBONI",
    "mbagala":              "DSM",
    "kurasini":             "DSM",
    "pugu":                 "DSM",
    "gongo la mboto":       "DSM",
    # MOROGORO
    "morogoro":             "MOROGORO",
    "morogoro urban":       "MOROGORO",
    "morogoro municipal":   "MOROGORO",
    "kilosa":               "MOROGORO",
    "mvomero":              "MOROGORO",
    "gairo":                "MOROGORO",
    "ifakara":              "MOROGORO",
    "mikumi":               "MIKUMI",
    # DODOMA
    "dodoma":               "DODOMA",
    "dodoma urban":         "DODOMA",
    "dodoma municipal":     "DODOMA",
    "bahi":                 "DODOMA",
    "kondoa":               "DODOMA",
    "mpwapwa":              "DODOMA",
    "chamwino":             "DODOMA",
    "chemba":               "DODOMA",
    "asanje":               "ASANJE",
    # IRINGA
    "iringa":               "IRINGA",
    "iringa urban":         "IRINGA",
    "iringa municipal":     "IRINGA",
    "mufindi":              "IRINGA",
    "kilolo":               "IRINGA",
    "mtera":                "IRINGA",
    # MBEYA
    "mbeya":                "MBEYA",
    "mbeya urban":          "MBEYA",
    "mbeya city":           "MBEYA",
    "chunya":               "MBEYA",
    "rungwe":               "MBEYA",
    "kyela":                "KYELA",
    "tukuyu":               "MBEYA",
    "busokelo":             "MBEYA",
    "makambako":            "MAKAMBAKO",
    # TANGA
    "tanga":                "TANGA",
    "tanga city":           "TANGA",
    "korogwe":              "KOROGWE",
    "muheza":               "TANGA",
    "handeni":              "TANGA",
    "pangani":              "TANGA",
    "lushoto":              "TANGA",
    "maweni":               "MAWENI",
    # MOSHI / ARUSHA / KILIMANJARO
    "moshi":                "MOSHI",
    "moshi urban":          "MOSHI",
    "moshi municipal":      "MOSHI",
    "arusha":               "ARUSHA",
    "arusha city":          "ARUSHA",
    "arumeru":              "ARUSHA",
    "meru":                 "ARUSHA",
    "monduli":              "ARUSHA",
    "longido":              "ARUSHA",
    "hai":                  "MOSHI",
    "kilimanjaro":          "MOSHI",
    "same":                 "MOSHI",
    "mwanga":               "MOSHI",
    "rombo":                "MOSHI",
    # TABORA
    "tabora":               "TABORA",
    "tabora urban":         "TABORA",
    "uyui":                 "TABORA",
    "urambo":               "TABORA",
    "sikonge":              "TABORA",
    "nzega":                "TABORA",
    "igunga":               "TABORA",
    # MWANZA
    "mwanza":               "MWANZA",
    "mwanza city":          "MWANZA",
    "ilemela":              "MWANZA",
    "nyamagana":            "MWANZA",
    "sengerema":            "MWANZA",
    "kwimba":               "MWANZA",
    "magu":                 "MWANZA",
    "misungwi":             "MWANZA",
    "ukerewe":              "MWANZA",
    "geita":                "GEITA",
    # SINGIDA
    "singida":              "SINGIDA",
    "singida urban":        "SINGIDA",
    "singida municipal":    "SINGIDA",
    "manyoni":              "SINGIDA",
    "ikungi":               "SINGIDA",
    # NJOMBE / SONGEA
    "njombe":               "NJOMBE",
    "wanging'ombe":         "NJOMBE",
    "makete":               "NJOMBE",
    "songea":               "SONGEA",
    "songea urban":         "SONGEA",
    "ruvuma":               "SONGEA",
    "mbinga":               "SONGEA",
    "tunduru":              "SONGEA",
    # LINDI / MTWARA (Gypsum coastal)
    "lindi":                "LINDI",
    "lindi urban":          "LINDI",
    "kilwa":                "LINDI",
    "liwale":               "LINDI",
    "mtwara":               "MTWARA",
    "mtwara urban":         "MTWARA",
    "masasi":               "MTWARA",
    "nanyumbu":             "MTWARA",
    "newala":               "MTWARA",
    "tandahimba":           "MTWARA",
    "kiranjeranje":         "KIRANJERANJE",
    "kibiti":               "KIBITI",
    "ikwiriri":             "IKWIRIRI",
    "utete":                "UTETE",
    "nyamisati":            "NYAMISATI",
    # CHALINZE
    "chalinze":             "CHALINZE",
    "bagamoyo":             "CHALINZE",
    "kibaha":               "KIBAHA",
    # COAST REGION
    "mafia":                "COASTAL",
    "rufiji":               "KIBITI",
    "mkuranga":             "DSM",
}


def normalise_city(city: str) -> str | None:
    """
    Map a free-text city string to a canonical REGION key.
    Returns None if the city is not in the normalisation map.
    """
    if not city:
        return None
    return CITY_TO_REGION.get(city.strip().lower())


def get_corridor_for_region(region: str) -> str | None:
    """Return the corridor name for a given region key."""
    entry = REGIONS.get(region.upper())
    return entry["corridor"] if entry else None


def get_distance_from_plant(region: str) -> float | None:
    """Return the km from Kimbiji Plant for a region (None if unknown)."""
    entry = REGIONS.get(region.upper())
    return float(entry["km"]) if entry else None
