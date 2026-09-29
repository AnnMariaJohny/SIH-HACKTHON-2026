from flask import Flask, request, jsonify, send_from_directory
import requests
import os
import math
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def load_local_env():

    env_path = Path(__file__).with_name(".env")

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():

        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


load_local_env()

app = Flask(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@app.after_request
def add_cors_headers(response):

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"

    return response

# ==========================================================
# GEOAPIFY API KEY
# ==========================================================
# Set your API key as an environment variable.
#
# Windows CMD:
# set GEOAPIFY_API_KEY=YOUR_API_KEY
#
# PowerShell:
# $env:GEOAPIFY_API_KEY="YOUR_API_KEY"

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()

if not GEOAPIFY_API_KEY:
    raise RuntimeError("GEOAPIFY_API_KEY is missing from .env")


def safe_geoapify_error(error):

    message = str(error)
    if GEOAPIFY_API_KEY:
        message = message.replace(GEOAPIFY_API_KEY, "[redacted]")
    message = re.sub(r"(?i)(apiKey=)[^&\s\"']+", r"\1[redacted]", message)

    lowered = message.lower()
    if "winerror 10013" in lowered or "access permissions" in lowered:
        return "The backend host blocked its outbound connection to Geoapify (Windows error 10013)."

    return message[:500]

# Geoapify APIs
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OIL_RELATED_CATEGORIES = [
    "oil refinery",
    "petroleum refinery",
    "oil processing plant",
    "petroleum processing plant",
    "oil factory",
    "petroleum plant",
    "petrochemical plant",
    "petrochemical complex",
    "oil terminal",
    "petroleum terminal",
    "oil storage facility",
    "petroleum storage facility",
    "oil storage tank",
    "oil depot",
    "petroleum depot",
    "fuel storage terminal",
    "oil distribution center",
    "fuel distribution center",
    "oil port",
    "petroleum port",
    "oil harbour",
    "petroleum harbour",
    "oil terminal port",
    "cargo port",
    "commercial port",
    "industrial port",
    "harbour",
    "port",
    "oil loading terminal",
    "oil unloading terminal",
    "crude oil terminal",
    "crude oil loading terminal",
    "crude oil unloading terminal",
    "lng terminal",
    "lpg terminal",
    "fuel terminal",
    "marine fuel terminal",
    "bunkering facility",
    "oil pipeline terminal",
    "petroleum pipeline terminal",
    "crude oil pipeline",
    "oil pumping station",
    "petroleum pumping station",
    "tank farm",
    "oil tank farm",
    "petroleum tank farm",
    "refinery storage",
    "petrochemical storage",
    "fuel depot",
    "oil tanker terminal",
    "tanker terminal",
    "tanker port",
    "tanker harbour",
    "oil ship terminal"
]

OIL_SOURCE_KEYWORDS = [
    "petroleum refinery", "oil refinery", "refinery", "petroleum", "crude oil",
    "crude_oil", "fuel-oil", "fuel oil", "fuel", "diesel", "gasoline",
    "kerosene", "bitumen", "hydrocarbon", "petrochemical", "petro-chemical",
    "oil terminal", "petroleum terminal", "fuel terminal", "terminal fuel",
    "tank farm", "oil storage", "fuel storage", "petroleum storage", "depot",
    "tanker", "bunkering", "marine fuel", "pipeline", "pumping station",
    "oil-fired", "oil fired", "oilfield", "oil field", "wellhead", "pumpjack",
    "drilling rig", "lng", "lpg", "plant:source=oil", "plant:source=diesel",
    "power.generator.oil", "power.plant.oil", "industrial.oil", "oil_terminal",
    "oil_storage", "oil_well"
]

# Broad Geoapify candidate categories. These describe map feature types, not
# conclusions that every feature is an oil source; Python filters the results.
GEOAPIFY_CANDIDATE_CATEGORIES = [
    "building.industrial",
    "production",
    "production.factory",
    "power.plant",
    "power.plant.oil",
    "power.plant.gas",
    "power.generator.oil",
    "man_made.pier",
    "maritime",
    "maritime.marina",
    "commercial"
]

# The Places API's `name` parameter is a supported secondary filter. Run these
# focused name searches over the same valid broad categories to find oil sites
# whose map category is generic (such as production.factory or maritime.port).
GEOAPIFY_OIL_SEARCH_TERMS = [
    "refinery", "petroleum", "oil", "fuel", "tank farm", "petrochemical",
    "bunkering", "tanker", "diesel", "crude"
]

# OSM uses these values to identify oil and chemical processing sites, even
# when the facility name itself contains no oil-related word.
OIL_SOURCE_TAGS = {
    "industrial": {"refinery", "oil", "petrochemical", "chemical", "fuel", "port"},
    "product": {"oil", "petroleum", "fuel", "diesel", "gasoline", "crude_oil"},
    "substance": {"oil", "petroleum", "fuel", "diesel", "crude_oil"},
    "man_made": {"storage_tank", "pipeline", "pumping_station"},
    "plant:source": {"oil", "diesel", "fuel_oil", "gas"},
    "amenity": {"fuel"},
}


# ==========================================================
# FRONTEND
# ==========================================================

@app.route("/", methods=["GET"])
@app.route("/app", methods=["GET"])
def frontend():

    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>", methods=["GET"])
def frontend_asset(filename):

    if filename in {"style.css", "script.js"}:
        return send_from_directory(FRONTEND_DIR, filename)

    return jsonify({
        "success": False,
        "error": "Not found."
    }), 404


# ==========================================================
# GEOCODING
# ==========================================================

@app.route("/geocode", methods=["GET"])
def geocode():

    if not GEOAPIFY_API_KEY:
        return jsonify({
            "success": False,
            "error": "Geoapify API key is not configured."
        }), 500

    address = request.args.get("text", "").strip()

    if not address:
        return jsonify({
            "success": False,
            "error": "Address text is required."
        }), 400

    try:

        response = requests.get(
            GEOAPIFY_GEOCODE_URL,
            params={
                "text": address,
                "apiKey": GEOAPIFY_API_KEY
            },
            headers={
                "Accept": "application/json"
            },
            timeout=15
        )

        response.raise_for_status()

        features = response.json().get("features", [])

        if not features:
            return jsonify({
                "success": False,
                "error": "No location found for that address."
            }), 404

        properties = features[0].get("properties", {})

        return jsonify({
            "success": True,
            "address": properties.get("formatted", address),
            "latitude": properties.get("lat"),
            "longitude": properties.get("lon")
        })

    except requests.exceptions.Timeout:

        return jsonify({
            "success": False,
            "error": "Geoapify request timed out."
        }), 504

    except requests.exceptions.RequestException as error:

        return jsonify({
            "success": False,
            "error": "Unable to connect to Geoapify.",
            "details": str(error)
        }), 502


# ==========================================================
# HAVERSINE DISTANCE
# ==========================================================

def calculate_distance(lat1, lon1, lat2, lon2):

    # Earth radius in metres
    earth_radius = 6371000

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    difference_lat = math.radians(lat2 - lat1)
    difference_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(difference_lat / 2) ** 2
        +
        math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(difference_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# ==========================================================
# RISK CALCULATION
# ==========================================================

def _facility_evidence_text(properties):

    datasource = properties.get("datasource", {})
    raw = datasource.get("raw", {}) if isinstance(datasource, dict) else {}
    tags = raw.get("tags", {}) if isinstance(raw, dict) else {}
    if not tags and isinstance(raw, dict):
        tags = raw

    searchable_parts = []
    ignored_keys = {"lat", "lon", "latitude", "longitude", "rank", "place_id", "datasource"}

    def collect(value, parent_key=""):
        if isinstance(value, dict):
            for key, nested_value in value.items():
                key_text = str(key).lower()
                if key_text in ignored_keys:
                    # Still inspect datasource.raw tags below; skip nonsemantic
                    # IDs and coordinate fields to avoid accidental matches.
                    continue
                searchable_parts.append(key_text.replace("_", " "))
                collect(nested_value, key_text)
        elif isinstance(value, (list, tuple, set)):
            for nested_value in value:
                collect(nested_value, parent_key)
        elif value is not None and isinstance(value, (str, int, float, bool)):
            searchable_parts.append(str(value).replace("_", " ").replace("-", " "))

    # Geoapify properties can contain category hierarchy, address components,
    # facility-specific fields, and datasource metadata beyond the usual keys.
    collect(properties)
    if isinstance(datasource, dict):
        collect({key: value for key, value in datasource.items() if key != "raw"})
    collect(tags)
    return " ".join(searchable_parts).lower(), tags


def _oil_relevance(properties):

    text, tags = _facility_evidence_text(properties)
    tags = {str(key).lower(): str(value).lower() for key, value in tags.items()}
    evidence = []

    # Specific facility types receive stronger relevance than generic evidence.
    specific_patterns = [
        # Exact facility descriptions and oil-specific map tags are the
        # strongest evidence. Generic ports, pipelines, plants, and factories
        # are deliberately not treated as oil sources on their own.
        ("power.plant.oil", 100, "Oil-fired power plant"),
        ("power.generator.oil", 100, "Oil-fired power generator"),
        ("diesel power plant", 100, "Diesel power plant"),
        ("fuel power plant", 100, "Fuel power plant"),
        ("oil-fired power plant", 100, "Oil-fired power plant"),
        ("oil fired power plant", 100, "Oil-fired power plant"),
        ("oil harbour", 100, "Oil harbour"),
        ("petroleum harbour", 100, "Petroleum harbour"),
        ("oil port", 100, "Oil port"),
        ("petroleum port", 100, "Petroleum port"),
        ("oil refinery", 100, "Oil refinery"),
        ("petroleum refinery", 100, "Petroleum refinery"),
        ("fuel terminal", 100, "Fuel terminal"),
        ("oil terminal", 100, "Oil terminal"),
        ("petroleum terminal", 100, "Petroleum terminal"),
        ("tank farm", 100, "Tank farm"),
        ("oil storage", 100, "Oil storage"),
        ("fuel storage", 100, "Fuel storage"),
        ("petroleum storage", 100, "Petroleum storage"),
        ("diesel", 100, "Diesel-related facility"),
        ("bunkering", 100, "Bunkering facility"),
        ("marine fuel", 100, "Marine fuel facility"),
        ("oil pipeline", 100, "Oil pipeline"),
        ("petroleum pipeline", 100, "Petroleum pipeline"),
        ("oil pumping station", 100, "Oil pumping station"),
        ("petroleum pumping station", 100, "Petroleum pumping station"),
        ("oil processing plant", 100, "Oil processing plant"),
        ("petroleum processing plant", 100, "Petroleum processing plant"),
        ("petrochemical", 100, "Petrochemical facility"),
        ("power.plant.gas", 75, "Gas-fired power plant"),
        ("refinery", 100, "Refinery"),
        ("refining", 95, "Oil refining facility"),
        ("terminal fuel", 100, "Fuel terminal"),
        ("tanker terminal", 100, "Tanker terminal"),
        ("fuel depot", 95, "Fuel depot"),
        ("oil depot", 95, "Oil depot"),
        ("petroleum depot", 95, "Petroleum depot"),
        ("tanker", 95, "Tanker facility"),
        ("oil factory", 100, "Oil-related factory"),
        ("oil processing", 95, "Oil processing facility"),
        ("petroleum plant", 95, "Petroleum plant"),
        ("oil loading", 95, "Oil loading facility"),
        ("oil unloading", 95, "Oil unloading facility"),
        ("petroleum products", 90, "Petroleum products facility"),
        ("gasoline", 95, "Gasoline-related facility"),
        ("fuel-oil", 100, "Fuel-oil-related facility"),
        ("fuel oil", 100, "Fuel-oil-related facility"),
        ("oil-fired", 100, "Oil-fired facility"),
        ("oil fired", 100, "Oil-fired facility"),
        ("gas-fired", 75, "Gas-fired facility"),
        ("gas fired", 75, "Gas-fired facility"),
        ("natural gas", 70, "Natural-gas facility"),
        ("crude oil", 100, "Crude-oil-related facility"),
        ("petroleum", 90, "Petroleum-related facility"),
        ("hydrocarbon", 85, "Hydrocarbon-related facility"),
        ("oil", 80, "Oil-related facility"),
        ("fuel", 80, "Fuel-related facility"),
        ("lng", 85, "LNG-related facility"),
        ("lpg", 85, "LPG-related facility"),
    ]

    def contains_term(haystack, term):
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        return re.search(pattern, haystack.lower()) is not None

    for pattern, score, label in specific_patterns:
        if contains_term(text, pattern):
            evidence.append((score, label))

    # Structured OSM tags count as direct evidence even if name/address is plain.
    for key, value in tags.items():
        normalized = value.replace("_", " ").replace("-", " ")
        if key in {"product", "substance", "fuel", "plant:source", "industrial"}:
            for term, score, label in [
                ("diesel", 100, "Diesel-related facility"),
                ("fuel oil", 100, "Fuel-oil-related facility"),
                ("crude oil", 100, "Crude-oil-related facility"),
                ("petroleum", 95, "Petroleum-related facility"),
                ("oil", 90, "Oil-related facility"),
                ("fuel", 90, "Fuel-related facility"),
                ("gasoline", 95, "Gasoline-related facility"),
                ("natural gas", 70, "Natural-gas facility"),
                ("gas", 65, "Gas-related facility"),
            ]:
                if contains_term(normalized, term):
                    evidence.append((score, label))
        # Generic pipeline/storage tags do not establish what is transported
        # or stored; oil-specific product/substance tags above do.

    if not evidence:
        return 0, []

    score = max(item[0] for item in evidence)
    labels = list(dict.fromkeys(label for _, label in evidence))
    return score, labels


def calculate_risk(industry_type, distance_meters, properties=None):

    # Generic industrial categories do not establish an oil-spill connection.
    properties = properties or {"name": industry_type}
    oil_score, _ = _oil_relevance(properties)
    connectivity_score, pathway_reason = _connectivity_assessment(properties)

    distance_km = distance_meters / 1000
    if distance_km <= 1:
        proximity_score = 30
    elif distance_km <= 5:
        proximity_score = 20
    elif distance_km <= 15:
        proximity_score = 10
    else:
        proximity_score = 0

    # Oil evidence determines the source risk tier. Connectivity and distance
    # can increase the score only after oil-related evidence is present.
    if oil_score == 0:
        score = 0
        risk = "LOW"
    else:
        normalized_proximity = (proximity_score / 30) * 100
        score = round(
            oil_score * 0.90
            + connectivity_score * 0.07
            + normalized_proximity * 0.03
        )

        # Strong, specific oil evidence is itself enough for VERY HIGH source
        # priority. Connectivity and proximity refine the score without being
        # prerequisites that could demote a confirmed oil-related facility.
        if oil_score >= 90:
            risk = "VERY HIGH"
        elif oil_score >= 65 and score >= 55:
            risk = "HIGH"
        elif score >= 25:
            risk = "POSSIBLE"
        else:
            risk = "LOW"

    components = {
        "oil_source_relevance_score": oil_score,
        "connectivity_score": connectivity_score,
        "proximity_score": proximity_score,
        "potential_source_score": score,
        "pathway_reason": pathway_reason
    }
    return risk, score, components


def get_risk_factors(properties, distance_meters, oil_score, connectivity_score, proximity_score):

    _, evidence = _oil_relevance(properties)
    factors = evidence or ["No direct oil-related evidence in mapped data."]
    _, pathway_reason = _connectivity_assessment(properties)
    factors.append(pathway_reason)
    distance_km = distance_meters / 1000

    if distance_km <= 1:
        factors.append("Within 1 km")
    elif distance_km <= 5:
        factors.append("Within 5 km")
    elif distance_km <= 15:
        factors.append("Within 15 km")
    else:
        factors.append("Beyond 15 km")

    factors.append(f"Oil-source relevance score: {oil_score}/100")
    factors.append(f"Connectivity score: {connectivity_score}/100")
    factors.append(f"Proximity score: {proximity_score}/30")
    return factors


def _connectivity_assessment(properties):

    _, tags = _facility_evidence_text(properties)
    categories = properties.get("categories", [])
    if isinstance(categories, str):
        category_text = categories
    elif isinstance(categories, dict):
        category_text = " ".join(str(value) for value in categories.values())
    else:
        category_text = " ".join(str(value) for value in categories)

    # Address strings alone do not prove a mapped pathway. Use named feature
    # fields, category hierarchy, and structured raw OSM tags instead.
    pathway_text = " ".join([
        str(properties.get("name", "")),
        str(properties.get("facility", "")),
        str(properties.get("facility_type", "")),
        category_text,
        " ".join(f"{key}={value}" for key, value in tags.items())
    ]).lower()

    def has(term):
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        return re.search(pattern, pathway_text) is not None

    # Direct mapped water/sea interfaces rank above generic pipelines.
    water_pathways = (
        "port", "harbour", "harbor", "maritime", "marina", "waterway",
        "river", "canal", "coastal", "coastline", "shoreline", "seamark",
        "dock", "pier", "quay", "marine terminal", "sea terminal"
    )
    pipeline_terms = ("pipeline", "pumping station")

    matched_water = [term for term in water_pathways if has(term)]
    matched_pipeline = [term for term in pipeline_terms if has(term)]
    if matched_water:
        return 100, "Mapped sea or waterway connection: " + matched_water[0]
    if matched_pipeline:
        return 70, "Mapped pipeline pathway: " + matched_pipeline[0]
    return 0, "No mapped pathway identified."


def is_oil_source(properties):

    relevance_score, _ = _oil_relevance(properties)
    return relevance_score > 0


def _is_excluded_non_oil_factory(properties):

    categories = properties.get("categories", [])
    if isinstance(categories, dict):
        categories = " ".join(str(value) for value in categories.values())
    elif isinstance(categories, (list, tuple, set)):
        categories = " ".join(str(value) for value in categories)

    factory_description = " ".join([
        str(properties.get("name", "")),
        str(properties.get("facility_type", "")),
        str(properties.get("facility", "")),
        str(categories)
    ]).lower().replace("-", " ").replace("_", " ")

    excluded_industries = (
        "tile factory", "tile works", "tile manufacturing", "tile manufacturer",
        "textile", "textiles",
        "food processing", "food factory", "food manufacturing",
        "electronics", "electronic",
        "furniture",
        "paper",
    )
    return any(term in factory_description for term in excluded_industries)


def is_relevant_industrial_candidate(properties):

    # Exclude the requested non-oil factory types from both result lists.
    if _is_excluded_non_oil_factory(properties):
        return False

    if is_oil_source(properties):
        return True

    categories = properties.get("categories", [])
    if isinstance(categories, dict):
        category_text = " ".join(str(value) for value in categories.values())
    elif isinstance(categories, (list, tuple, set)):
        category_text = " ".join(str(value) for value in categories)
    else:
        category_text = str(categories)

    candidate_text = " ".join([
        category_text,
        str(properties.get("facility_type", "")),
        str(properties.get("facility", "")),
        str(properties.get("name", ""))
    ]).lower()

    candidate_terms = (
        "power.plant", "power plant", "power.generator", "production",
        "industrial", "manufacturing", "manufacturer", "factory",
        "waste", "maritime", "marina", "port", "harbour", "harbor",
        "man_made.pier"
    )
    return any(term in candidate_text for term in candidate_terms)


# ==========================================================
# GET INDUSTRY TYPE
# ==========================================================

def get_industry_type(properties):

    explicit_type = properties.get("facility_type") or properties.get("facility")
    if explicit_type:
        return str(explicit_type)

    categories = properties.get("categories", [])

    if isinstance(categories, str):
        categories = [categories]
    elif isinstance(categories, dict):
        flattened = []

        def collect_category(value):
            if isinstance(value, dict):
                for nested_value in value.values():
                    collect_category(nested_value)
            elif isinstance(value, (list, tuple, set)):
                for nested_value in value:
                    collect_category(nested_value)
            elif value is not None:
                flattened.append(str(value))

        collect_category(categories)
        categories = flattened

    if len(categories) > 0:

        return categories[-1]

    return "industrial"


# ==========================================================
# SEARCH NEARBY FACTORIES
# ==========================================================

def search_nearby_industries(latitude, longitude, radius, name_query=None):
    features = []
    category_groups = (
        [GEOAPIFY_CANDIDATE_CATEGORIES]
        if name_query
        else [[category] for category in GEOAPIFY_CANDIDATE_CATEGORIES]
    )

    for categories in category_groups:
        base_params = {
            "categories": ",".join(categories),
            "filter": f"circle:{longitude},{latitude},{radius}",
            "bias": f"proximity:{longitude},{latitude}",
            "limit": 500,
            "apiKey": GEOAPIFY_API_KEY,
        }
        if name_query:
            base_params["name"] = name_query

        offset = 0
        while True:
            params = {**base_params, "offset": offset}
            response = requests.get(
                GEOAPIFY_PLACES_URL,
                params=params,
                headers={
                    "Accept": "application/json"
                },
                timeout=15
            )

            if response.status_code != 200:
                raise Exception(
                    "Geoapify API Error: "
                    + str(response.status_code)
                    + " "
                    + response.text
                )

            page_features = response.json().get("features", [])
            features.extend(page_features)
            if len(page_features) < base_params["limit"]:
                break
            offset += len(page_features)

    return {"features": features}


def search_nearby_oil_facilities(latitude, longitude, radius):

    features = []
    errors = []

    def search_term(term):
        try:
            return term, search_nearby_industries(
                latitude, longitude, radius, name_query=term
            ), None
        except Exception as error:
            return term, None, safe_geoapify_error(error)

    # Focused searches run concurrently so the user does not wait through
    # sequential network timeouts. A failed term does not discard other results.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(search_term, term) for term in GEOAPIFY_OIL_SEARCH_TERMS]
        for future in as_completed(futures):
            term, result, error = future.result()
            if error is not None:
                errors.append(f"{term}: {error}")
            elif result is not None:
                features.extend(result.get("features", []))

    return {"features": features, "errors": errors}


def merge_geoapify_features(features):

    merged = {}
    unlocated = []

    def merge_value(existing, incoming):
        if isinstance(existing, dict) and isinstance(incoming, dict):
            for key, value in incoming.items():
                if key in existing:
                    existing[key] = merge_value(existing[key], value)
                else:
                    existing[key] = value
            return existing
        if isinstance(existing, list) and isinstance(incoming, list):
            return existing + [value for value in incoming if value not in existing]
        return existing if existing not in (None, "", [], {}) else incoming

    for feature in features:
        properties = feature.get("properties", {})
        try:
            key = (round(float(properties["lat"]), 5), round(float(properties["lon"]), 5))
        except (KeyError, TypeError, ValueError):
            unlocated.append(feature)
            continue

        if key not in merged:
            merged[key] = feature
        else:
            merge_value(merged[key].setdefault("properties", {}), properties)

    return list(merged.values()) + unlocated


def search_overpass_oil_sources(latitude, longitude, radius):

    # Keep Overpass queries small; Geoapify still uses the app's full radius.
    overpass_radius = min(radius, 30000)

    query = f"""
    [out:json][timeout:25];
    (
      nwr[\"industrial\"~\"refinery|oil|petroleum|petrochemical|chemical|fuel|port\",i](around:{overpass_radius},{latitude},{longitude});
      nwr[\"name\"~\"oil|petroleum|refinery|petrochemical|chemical|fuel|terminal|tank farm|tanker|pipeline|bunkering|lng|lpg\",i](around:{overpass_radius},{latitude},{longitude});
      nwr[\"man_made\"~\"works|storage_tank|pipeline|pumping_station\"](around:{overpass_radius},{latitude},{longitude});
      nwr[\"landuse\"~\"industrial|port\"](around:{overpass_radius},{latitude},{longitude});
      nwr[\"port\"](around:{overpass_radius},{latitude},{longitude});
      nwr[\"seamark:type\"~\"harbour|oil_terminal|terminal\"](around:{overpass_radius},{latitude},{longitude});
      nwr[\"product\"~\"oil|petroleum|fuel|gas|chemicals|crude\",i](around:{overpass_radius},{latitude},{longitude});
      nwr[\"substance\"~\"oil|petroleum|crude_oil|gas|chemical|fuel\",i](around:{overpass_radius},{latitude},{longitude});
      nwr[\"power\"=\"plant\"][\"plant:source\"~\"oil|gas\",i](around:{overpass_radius},{latitude},{longitude});
      nwr[\"industrial\"~\"manufacture|factory|production\",i][\"product\"~\"oil|petroleum|fuel|gas|chemical\",i](around:{overpass_radius},{latitude},{longitude});
    );
    out center tags 500;
    """

    response = None
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers={
                "User-Agent": "Oceanova-IndustryRisk/1.0",
                "Accept": "application/json"
            },
        timeout=30
        )
        response.raise_for_status()

        features = []
        for element in response.json().get("elements", []):
            tags = element.get("tags", {})
            center = element.get("center", {})
            element_lat = element.get("lat", center.get("lat"))
            element_lon = element.get("lon", center.get("lon"))
            if element_lat is None or element_lon is None:
                continue

            category_tags = [
                f"{key}={value}"
                for key, value in tags.items()
                if key in {
                    "industrial", "landuse", "man_made", "power",
                    "plant:source", "product", "substance"
                }
            ]
            features.append({
                "properties": {
                    "name": tags.get("name", "Unnamed industrial source"),
                    "formatted": tags.get("addr:full", "OpenStreetMap source"),
                    "lat": element_lat,
                    "lon": element_lon,
                    "categories": category_tags or ["industrial"],
                    "datasource": {"raw": {"tags": tags}},
                    "facility_type": tags.get("industrial") or tags.get("man_made") or tags.get("landuse") or tags.get("power"),
                    "source": "OpenStreetMap"
                }
            })

        return {"features": features, "error": None}
    except requests.exceptions.Timeout:
        return {"features": [], "error": "OpenStreetMap search timed out."}
    except requests.exceptions.HTTPError:
        status = response.status_code if response is not None else "unknown"
        return {"features": [], "error": f"OpenStreetMap search error: {status}"}
    except requests.exceptions.RequestException:
        return {"features": [], "error": "Unable to connect to OpenStreetMap."}
    except Exception as error:
        return {"features": [], "error": str(error)}


# ==========================================================
# NEARBY INDUSTRIES API
# ==========================================================

@app.route("/nearby-industries", methods=["POST"])
def nearby_industries():

    try:

        # --------------------------------------------------
        # GET JSON DATA
        # --------------------------------------------------

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "error": "JSON data is required."
            }), 400

        # --------------------------------------------------
        # GET LATITUDE
        # --------------------------------------------------

        if "latitude" not in data:

            return jsonify({
                "success": False,
                "error": "Latitude is required."
            }), 400

        # --------------------------------------------------
        # GET LONGITUDE
        # --------------------------------------------------

        if "longitude" not in data:

            return jsonify({
                "success": False,
                "error": "Longitude is required."
            }), 400

        # --------------------------------------------------
        # CONVERT INPUT
        # --------------------------------------------------

        latitude = float(data["latitude"])
        longitude = float(data["longitude"])

        # Radius is supplied in metres. Reject values above the supported
        # maximum rather than silently changing the user's selected radius.
        radius = float(data.get("radius", 200000))

        # --------------------------------------------------
        # VALIDATE LATITUDE
        # --------------------------------------------------

        if latitude < -90 or latitude > 90:

            return jsonify({
                "success": False,
                "error": "Invalid latitude."
            }), 400

        # --------------------------------------------------
        # VALIDATE LONGITUDE
        # --------------------------------------------------

        if longitude < -180 or longitude > 180:

            return jsonify({
                "success": False,
                "error": "Invalid longitude."
            }), 400

        # --------------------------------------------------
        # VALIDATE RADIUS
        # --------------------------------------------------

        if not math.isfinite(radius) or radius <= 0:

            return jsonify({
                "success": False,
                "error": "Radius must be a finite number greater than 0 metres."
            }), 400

        if radius > 200000:
            return jsonify({
                "success": False,
                "error": "Maximum search radius is 200 km (200000 metres)."
            }), 400

        # --------------------------------------------------
        # Run broad industrial discovery and focused oil-term discovery,
        # merge them, and deduplicate after both searches.
        features = []
        geoapify_error = None
        if not GEOAPIFY_API_KEY:
            geoapify_error = "Geoapify API key is not configured."
        else:
            search_errors = []
            try:
                geoapify_data = search_nearby_industries(
                    latitude,
                    longitude,
                    radius
                )
                features.extend(geoapify_data.get("features", []))
            except Exception as error:
                search_errors.append(
                    f"Broad industrial search: {safe_geoapify_error(error)}"
                )

            try:
                oil_data = search_nearby_oil_facilities(
                    latitude,
                    longitude,
                    radius
                )
                features.extend(oil_data.get("features", []))
                search_errors.extend(oil_data.get("errors", []))
            except Exception as error:
                search_errors.append(
                    f"Oil-specific search: {safe_geoapify_error(error)}"
                )

            if search_errors:
                geoapify_error = "; ".join(dict.fromkeys(search_errors))[:1500]

        features = merge_geoapify_features(features)

        if geoapify_error and not features:
            return jsonify({
                "success": False,
                "error": "Geoapify candidate search failed.",
                "details": geoapify_error
            }), 502

        nearby_sources = []

        # ==================================================
        # PROCESS EVERY FACTORY
        # ==================================================

        seen_sources = set()
        for feature in features:

            properties = feature.get(
                "properties",
                {}
            )

            if not is_relevant_industrial_candidate(properties):
                continue

            # --------------------------------------------------
            # FACTORY LATITUDE
            # --------------------------------------------------

            factory_lat = properties.get("lat")

            # --------------------------------------------------
            # FACTORY LONGITUDE
            # --------------------------------------------------

            factory_lon = properties.get("lon")

            if (
                factory_lat is None
                or factory_lon is None
            ):
                continue

            try:
                factory_lat = float(factory_lat)
                factory_lon = float(factory_lon)
            except (TypeError, ValueError):
                continue

            source_key = (round(factory_lat, 5), round(factory_lon, 5))
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)

            # --------------------------------------------------
            # FACTORY NAME
            # --------------------------------------------------

            factory_name = properties.get(
                "name",
                "Unnamed Factory"
            )

            # --------------------------------------------------
            # ADDRESS
            # --------------------------------------------------

            address = properties.get(
                "formatted",
                "Address unavailable"
            )

            # --------------------------------------------------
            # INDUSTRY TYPE
            # --------------------------------------------------

            industry_type = get_industry_type(
                properties
            )

            # --------------------------------------------------
            # CALCULATE DISTANCE
            # --------------------------------------------------

            distance = calculate_distance(
                latitude,
                longitude,
                factory_lat,
                factory_lon
            )

            if distance > radius:
                continue

            # --------------------------------------------------
            # CALCULATE RISK
            # --------------------------------------------------

            risk, risk_score, score_components = calculate_risk(
                industry_type,
                distance,
                properties
            )
            risk_factors = get_risk_factors(
                properties,
                distance,
                score_components["oil_source_relevance_score"],
                score_components["connectivity_score"],
                score_components["proximity_score"]
            )
            distance_reason = next(
                factor for factor in risk_factors
                if factor.startswith("Within ") or factor.startswith("Beyond ")
            )
            reason = "; ".join([
                risk_factors[0],
                score_components["pathway_reason"],
                distance_reason
            ])

            # --------------------------------------------------
            # ADD FACTORY
            # --------------------------------------------------

            nearby_sources.append({

                "name": factory_name,

                "industry_type": industry_type,

                "latitude": factory_lat,

                "longitude": factory_lon,

                "address": address,

                "source": properties.get("source", "Geoapify"),

                "distance_m": round(
                    distance,
                    2
                ),

                "distance_km": round(
                    distance / 1000,
                    3
                ),

                "risk_score": risk_score,

                "oil_source_relevance_score": score_components["oil_source_relevance_score"],

                "connectivity_score": score_components["connectivity_score"],

                "connectivity_reason": score_components["pathway_reason"],

                "proximity_score": score_components["proximity_score"],

                "potential_source_score": score_components["potential_source_score"],

                "risk": risk,

                "risk_factors": risk_factors,

                "reason": reason
            })

        # Keep oil-evidenced candidates separate from generic nearby features.
        # Only actual mapped oil relevance can enter potential_sources.
        potential_sources = [
            facility for facility in nearby_sources
            if facility["oil_source_relevance_score"] > 0
        ]
        other_nearby_facilities = [
            facility for facility in nearby_sources
            if facility["oil_source_relevance_score"] <= 0
        ]

        # Rank potential sources exactly by oil evidence, mapped connectivity,
        # then distance. Generic facilities stay in their separate list.
        potential_sources.sort(
            key=lambda x: (
                -x["oil_source_relevance_score"],
                -x["connectivity_score"],
                x["distance_m"]
            )
        )
        other_nearby_facilities.sort(key=lambda x: x["distance_m"])
        all_nearby_facilities = potential_sources + other_nearby_facilities

        # ==================================================
        # OVERALL RISK
        # ==================================================

        if len(all_nearby_facilities) == 0:

            overall_risk = "LOW"

        elif any(
            source["risk"] == "VERY HIGH"
            for source in all_nearby_facilities
        ):

            overall_risk = "VERY HIGH"

        elif any(
            source["risk"] == "HIGH"
            for source in all_nearby_facilities
        ):

            overall_risk = "HIGH"

        elif any(
            source["risk"] == "MEDIUM"
            for source in all_nearby_facilities
        ):

            overall_risk = "MEDIUM"

        elif any(
            source["risk"] == "POSSIBLE"
            for source in all_nearby_facilities
        ):

            overall_risk = "POSSIBLE"

        else:

            overall_risk = "LOW"

        # ==================================================
        # FINAL RESPONSE
        # ==================================================

        return jsonify({

            "success": True,

            "input_location": {

                "latitude": latitude,

                "longitude": longitude
            },

            "search_radius_m": round(radius, 3),

            "search_radius_km": round(
                radius / 1000,
                3
            ),

            "nearby_factory_count":
                len(all_nearby_facilities),

            "potential_source_count":
                len(potential_sources),

            "score_model": {
                "formula": "if oil relevance = 0, final = 0; otherwise oil relevance * 0.90 + connectivity * 0.07 + normalized proximity * 0.03",
                "oil_relevance_weight": 0.90,
                "connectivity_weight": 0.07,
                "proximity_weight": 0.03,
                "ranking_order": [
                    "oil_source_relevance_score descending",
                    "connectivity_score descending",
                    "distance_m ascending"
                ]
            },

            "overall_risk":
                overall_risk,

            "potential_sources":
                potential_sources,

            # Compatibility alias for existing clients.
            "nearby_sources":
                potential_sources,

            "other_nearby_facilities":
                other_nearby_facilities,

            "providers": {
                "geoapify": "available" if not geoapify_error or features else "error"
            },

            "provider_errors": {
                "geoapify": geoapify_error
            }
        })

    # ======================================================
    # ERROR HANDLING
    # ======================================================

    except ValueError:

        return jsonify({

            "success": False,

            "error":
                "Latitude, longitude and radius must be numbers."
        }), 400

    except requests.exceptions.Timeout:

        return jsonify({

            "success": False,

            "error":
                "Geoapify request timed out."
        }), 504

    except requests.exceptions.RequestException as error:

        return jsonify({

            "success": False,

            "error":
                "Unable to connect to Geoapify.",

            "details":
                str(error)
        }), 502

    except Exception as error:

        return jsonify({

            "success": False,

            "error":
                str(error)
        }), 500


# ==========================================================
# HOME / STATUS
# ==========================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({

        "project":
            "Factory and Industry Risk Detection",

        "status":
            "Backend running",

        "api":
            "Geoapify",

        "endpoint":
            "/nearby-industries",

        "method":
            "POST"
    })


# ==========================================================
# START SERVER
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )
