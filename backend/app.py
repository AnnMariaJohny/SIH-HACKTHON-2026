"""FastAPI adapter for the Eclipso boundary-aware SAR segmentation model."""
from __future__ import annotations

import base64
import asyncio
import importlib.util
import io
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import httpx
import rasterio
import torch
import websockets
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.wsgi import WSGIMiddleware
from PIL import Image
from pyproj import Geod, Transformer
from rasterio.crs import CRS
from rasterio.features import rasterize, shapes
from rasterio.io import MemoryFile
from rasterio.warp import Resampling, reproject
from shapely.geometry import shape
from shapely.ops import transform as transform_geometry, unary_union

HERE = Path(__file__).resolve().parent
WELCOME_PAGE = HERE.parent / "Sih hackthon" / "welcome.html"
LOGIN_ASSETS = HERE.parent / "Sih hackthon" / "LOGIN"
EARTH_ASSETS = HERE.parent / "Sih hackthon" / "earth"
INDUSTRY_FRONTEND = HERE.parent / "sih-backend-main" / "frontend"
VESSEL_FRONTEND = HERE.parent / "anzil" / "sih_backend-main"
INDUSTRY_BACKEND = HERE.parent / "sih-backend-main" / "sih-backend-main" / "bakend" / "app.py"
VESSEL_BACKEND = HERE.parent / "anzil" / "sih_backend-main" / "backend" / "app.py"
BUNDLED_ROOT = HERE / "model"
ECLIPSO_ROOT = Path(os.environ.get("ECLIPSO_ROOT", str(BUNDLED_ROOT))).resolve()
WEIGHTS_ROOT = BUNDLED_ROOT / "weights"
# Prefer the real-data checkpoint from the supplied Garcia-INPE training run.
# An explicit environment override remains available for another compatible checkpoint.
CHECKPOINT_OVERRIDE = os.environ.get("ECLIPSO_CHECKPOINT")
REAL_CHECKPOINT_CANDIDATES = (
    WEIGHTS_ROOT / "Eclipso_Final_UNet.pt",
    WEIGHTS_ROOT / "garcia_unet_boundary_best.pt",
)
CHECKPOINT = (
    Path(CHECKPOINT_OVERRIDE).resolve() if CHECKPOINT_OVERRIDE else
    next((candidate for candidate in REAL_CHECKPOINT_CANDIDATES if candidate.is_file()),
         REAL_CHECKPOINT_CANDIDATES[0])
).resolve()
THRESHOLD, TILE_SIZE, STRIDE = 0.5, 512, 448
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BENCHMARK_PATH = BUNDLED_ROOT / "benchmark" / "garcia_boundary_test.json"
try:
    MODEL_BENCHMARK = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    MODEL_BENCHMARK = None

if not ECLIPSO_ROOT.is_dir():
    raise RuntimeError(f"ECLIPSO_ROOT does not exist: {ECLIPSO_ROOT}")
if not CHECKPOINT.is_file():
    raise RuntimeError(f"Eclipso checkpoint not found: {CHECKPOINT}")
sys.path.insert(0, str(ECLIPSO_ROOT))
from eclipso.detect.unet import UNet  # noqa: E402

checkpoint = torch.load(CHECKPOINT, map_location=DEVICE, weights_only=False)
if "model_state_dict" not in checkpoint:
    raise RuntimeError(f"Checkpoint is not a Garcia-trained U-Net state: {CHECKPOINT}")
model = UNet(in_ch=1, base=16, depth=4).to(DEVICE)
model.load_state_dict(checkpoint["model_state_dict"])
SAR_MEAN, SAR_STD = -18.651564, 4.844823
THRESHOLD, TILE_SIZE, STRIDE = 0.96, 256, 128
MODEL_LABEL = "Garcia-INPE real-data boundary-aware U-Net"
if CHECKPOINT.name not in {"Eclipso_Final_UNet.pt", "garcia_unet_boundary_best.pt"}:
    MODEL_BENCHMARK = None
model.eval()
print(
    f"OCEANOVA loaded {MODEL_LABEL} from {CHECKPOINT.name} "
    f"(threshold={THRESHOLD:.2f}, device={DEVICE})"
)

app = FastAPI(title="OCEANOVA SAR oil-spill detection")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST", "GET"], allow_headers=["*"])
app.mount("/LOGIN", StaticFiles(directory=LOGIN_ASSETS), name="login-assets")
app.mount("/earth", StaticFiles(directory=EARTH_ASSETS), name="earth-assets")


def load_flask_app(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load backend module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.app


if not os.environ.get("VERCEL"):
    industry_api = load_flask_app("oceanova_industry_backend", INDUSTRY_BACKEND)
    vessel_api = load_flask_app("oceanova_vessel_backend", VESSEL_BACKEND)
    app.mount("/industry-api", WSGIMiddleware(industry_api), name="industry-api")
    app.mount("/vessel-api", WSGIMiddleware(vessel_api), name="vessel-api")


def infer(sar: np.ndarray) -> np.ndarray:
    height, width = sar.shape
    sums = np.zeros((height, width), np.float32)
    counts = np.zeros((height, width), np.float32)
    with torch.inference_mode():
        for y in range(0, height, STRIDE):
            for x in range(0, width, STRIDE):
                y2, x2 = min(y + TILE_SIZE, height), min(x + TILE_SIZE, width)
                tile = sar[y:y2, x:x2]
                h, w = tile.shape
                tile = np.pad(tile, ((0, TILE_SIZE - h), (0, TILE_SIZE - w)), mode="reflect")
                tile = ((tile - SAR_MEAN) / SAR_STD).astype(np.float32)
                tensor = torch.from_numpy(tile).unsqueeze(0).unsqueeze(0).to(DEVICE)
                probability = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()[:h, :w]
                sums[y:y2, x:x2] += probability
                counts[y:y2, x:x2] += 1
    return sums / np.maximum(counts, 1)


def overlay_png(sar: np.ndarray, mask: np.ndarray) -> str:
    low, high = np.nanpercentile(sar, (2, 98))
    gray = np.clip((sar - low) / max(float(high - low), 1e-6) * 255, 0, 255).astype(np.uint8)
    rgb = np.repeat(gray[..., None], 3, axis=2)
    # Warm translucent red marks the predicted oil pixels.
    oil = mask.astype(bool)
    rgb[oil] = (0.35 * rgb[oil] + 0.65 * np.array([245, 111, 76])).astype(np.uint8)
    out = io.BytesIO()
    Image.fromarray(rgb).save(out, format="PNG", optimize=True)
    return base64.b64encode(out.getvalue()).decode("ascii")


def input_png(sar: np.ndarray) -> str:
    low, high = np.nanpercentile(sar, (2, 98))
    gray = np.clip((sar - low) / max(float(high - low), 1e-6) * 255, 0, 255).astype(np.uint8)
    out = io.BytesIO()
    Image.fromarray(gray).save(out, format="PNG", optimize=True)
    return base64.b64encode(out.getvalue()).decode("ascii")


def mask_png(mask: np.ndarray) -> str:
    out = io.BytesIO()
    Image.fromarray(mask.astype(np.uint8) * 255).save(out, format="PNG", optimize=True)
    return base64.b64encode(out.getvalue()).decode("ascii")


def evaluate_prediction(predicted: np.ndarray, truth: np.ndarray) -> dict:
    """Calculate thresholded pixel metrics against a matching scene label."""
    tp = int(np.logical_and(predicted, truth).sum())
    fp_pixels = int(np.logical_and(predicted, ~truth).sum())
    fn = int(np.logical_and(~predicted, truth).sum())
    tn = int(truth.size - tp - fp_pixels - fn)
    precision = tp / (tp + fp_pixels) if tp + fp_pixels else None
    recall = tp / (tp + fn) if tp + fn else None
    pixel_accuracy = (tp + tn) / truth.size if truth.size else None
    iou = tp / (tp + fp_pixels + fn) if tp + fp_pixels + fn else None
    dice = (2 * tp) / (2 * tp + fp_pixels + fn) if 2 * tp + fp_pixels + fn else None
    return {
        "precision": precision, "recall": recall, "pixel_accuracy": pixel_accuracy,
        "iou": iou, "dice": dice, "true_positive_pixels": tp,
        "false_positive_pixels": fp_pixels, "false_negative_pixels": fn,
        "true_negative_pixels": tn,
        "evaluation_method": "pixel metrics at the model's operating threshold, against the uploaded matching GeoJSON",
    }


def geojson_mask(content: bytes, image_crs, affine, shape_hw: tuple[int, int]) -> np.ndarray:
    payload = json.loads(content)
    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features", [])
        geometries = [shape(f["geometry"]) for f in features if f.get("geometry")]
    elif kind == "Feature":
        geometries = [shape(payload["geometry"])] if payload.get("geometry") else []
    else:
        geometries = [shape(payload)]
    if not geometries:
        raise ValueError("GeoJSON contains no labeled geometries.")
    crs_info = payload.get("crs") or {}
    crs_name = (crs_info.get("properties") or {}).get("name") or "EPSG:4326"
    label_crs = CRS.from_user_input(crs_name)
    if label_crs != image_crs:
        project = Transformer.from_crs(label_crs, image_crs, always_xy=True).transform
        geometries = [transform_geometry(project, geom) for geom in geometries]
    return rasterize([(geom, 1) for geom in geometries], out_shape=shape_hw, transform=affine,
                     fill=0, dtype=np.uint8).astype(bool)


def ground_truth_mask(content: bytes, filename: str, image_crs, affine,
                      shape_hw: tuple[int, int]) -> np.ndarray:
    """Load an aligned binary mask or rasterize matching GeoJSON labels."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".geojson", ".json"}:
        return geojson_mask(content, image_crs, affine, shape_hw)
    if suffix == ".png":
        with Image.open(io.BytesIO(content)) as mask_image:
            mask = np.asarray(mask_image.convert("L"))
        if mask.shape != shape_hw:
            raise ValueError(f"Ground-truth PNG must match the SAR image dimensions ({shape_hw[1]}×{shape_hw[0]} pixels).")
        return mask > 0
    if suffix in {".tif", ".tiff"}:
        with MemoryFile(content) as memory_file:
            with memory_file.open() as label_src:
                label = label_src.read(1)
                if label_src.crs is None:
                    if label.shape != shape_hw:
                        raise ValueError("A ground-truth GeoTIFF without a CRS must match the SAR image dimensions exactly.")
                    return label > 0
                aligned = np.zeros(shape_hw, dtype=np.uint8)
                reproject(
                    source=label,
                    destination=aligned,
                    src_transform=label_src.transform,
                    src_crs=label_src.crs,
                    dst_transform=affine,
                    dst_crs=image_crs,
                    resampling=Resampling.nearest,
                    src_nodata=label_src.nodata,
                    dst_nodata=0,
                )
                return aligned > 0
    raise ValueError("Ground truth must be a matching GeoJSON, binary PNG, or GeoTIFF mask.")


def validate_search_location(lat: float, lon: float, radius_km: float) -> None:
    if not math.isfinite(lat) or not -90 <= lat <= 90:
        raise HTTPException(422, "Latitude must be between -90 and 90 degrees.")
    if not math.isfinite(lon) or not -180 <= lon <= 180:
        raise HTTPException(422, "Longitude must be between -180 and 180 degrees.")
    if not math.isfinite(radius_km) or not 1 <= radius_km <= 100:
        raise HTTPException(422, "Search radius must be between 1 and 100 km.")


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    _, _, meters = Geod(ellps="WGS84").inv(lon1, lat1, lon2, lat2)
    return meters / 1000


@app.get("/api/nearby-industries")
async def nearby_industries(lat: float, lon: float, radius_km: float = 50):
    """Search OpenStreetMap for mapped industrial facilities near a detection."""
    validate_search_location(lat, lon, radius_km)
    radius_m = int(radius_km * 1000)
    query = f"""[out:json][timeout:25];
(
  nwr(around:{radius_m},{lat},{lon})[industrial~"^(oil|refinery|chemical|petrochemical|gas|port|harbour)$"];
  nwr(around:{radius_m},{lat},{lon})[man_made~"^(works|storage_tank|petroleum_well)$"];
  nwr(around:{radius_m},{lat},{lon})[landuse=industrial];
  nwr(around:{radius_m},{lat},{lon})[amenity=port];
  nwr(around:{radius_m},{lat},{lon})[harbour=yes];
);
out center tags;"""
    try:
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent": "OCEANOVA/1.0 nearby facility search"}) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise HTTPException(502, "The OpenStreetMap facility search is temporarily unavailable. Please try again.") from exc

    results = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        point = element.get("center") or element
        item_lat, item_lon = point.get("lat"), point.get("lon")
        if item_lat is None or item_lon is None:
            continue
        distance = distance_km(lat, lon, float(item_lat), float(item_lon))
        if distance > radius_km:
            continue
        facility_type = (tags.get("industrial") or tags.get("man_made") or tags.get("amenity") or
                         tags.get("harbour") or tags.get("landuse") or "industrial facility")
        results.append({
            "name": tags.get("name") or "Unnamed facility",
            "type": str(facility_type).replace("_", " ").title(),
            "distance_km": round(distance, 2), "latitude": float(item_lat), "longitude": float(item_lon),
            "osm_type": element.get("type"), "osm_id": element.get("id"),
        })
    results.sort(key=lambda item: item["distance_km"])
    return {"source": "OpenStreetMap", "radius_km": radius_km, "results": results[:50],
            "note": "Nearby mapped facilities only. Proximity does not establish a cause."}


def ais_bbox(lat: float, lon: float, radius_km: float) -> list[list[list[float]]]:
    lat_delta = radius_km / 110.574
    lon_delta = min(180.0, radius_km / max(111.320 * math.cos(math.radians(lat)), 0.01))
    south, north = max(-90.0, lat - lat_delta), min(90.0, lat + lat_delta)
    west, east = lon - lon_delta, lon + lon_delta
    if west < -180:
        return [[[north, west + 360], [south, 180]], [[north, -180], [south, east]]]
    if east > 180:
        return [[[north, west], [south, 180]], [[north, -180], [south, east - 360]]]
    return [[[north, west], [south, east]]]


def vessel_type_name(code) -> str | None:
    try:
        code = int(code)
    except (TypeError, ValueError):
        return str(code) if code else None
    if 80 <= code <= 89:
        return "Tanker"
    if 70 <= code <= 79:
        return "Cargo"
    if 60 <= code <= 69:
        return "Passenger"
    if 30 <= code <= 39:
        return "Fishing / service vessel"
    if 50 <= code <= 59:
        return "Special-purpose vessel"
    return f"AIS type {code}" if code else None


@app.get("/api/nearby-vessels")
async def nearby_vessels(lat: float, lon: float, radius_km: float = 25):
    """Collect recent AIS reports near a detection from the configured AISStream API."""
    validate_search_location(lat, lon, radius_km)
    api_key = os.environ.get("AISSTREAM_API_KEY")
    if not api_key:
        raise HTTPException(503, "Vessel search is not configured. Set AISSTREAM_API_KEY on the server and restart it.")
    ships: dict[str, dict] = {}
    subscription = {
        "APIKey": api_key, "BoundingBoxes": ais_bbox(lat, lon, radius_km),
        "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport",
                               "LongRangeAISBroadcastMessage", "ShipStaticData", "StaticDataReport"],
    }
    deadline = asyncio.get_running_loop().time() + 8
    try:
        async with websockets.connect("wss://stream.aisstream.io/v0/stream", compression="deflate",
                                      open_timeout=5, close_timeout=2, max_size=2_000_000) as socket:
            await socket.send(json.dumps(subscription))
            while asyncio.get_running_loop().time() < deadline:
                remaining = deadline - asyncio.get_running_loop().time()
                try:
                    raw = await asyncio.wait_for(socket.recv(), timeout=max(0.1, remaining))
                except asyncio.TimeoutError:
                    break
                message = json.loads(raw)
                metadata = message.get("MetaData") or {}
                contents = message.get("Message") or {}
                detail = next((value for value in contents.values() if isinstance(value, dict)), {})
                mmsi = str(metadata.get("MMSI") or detail.get("UserID") or detail.get("MMSI") or "")
                if not mmsi:
                    continue
                ship = ships.setdefault(mmsi, {"mmsi": mmsi})
                ship["name"] = metadata.get("ShipName") or detail.get("Name") or ship.get("name")
                ship["vessel_type"] = vessel_type_name(detail.get("Type") or detail.get("ShipType")) or ship.get("vessel_type")
                ship["latitude"] = metadata.get("Latitude", detail.get("Latitude", ship.get("latitude")))
                ship["longitude"] = metadata.get("Longitude", detail.get("Longitude", ship.get("longitude")))
                ship["last_seen"] = metadata.get("time_utc") or metadata.get("TimeUTC") or ship.get("last_seen")
                if ship.get("latitude") is not None and ship.get("longitude") is not None:
                    ship["distance_km"] = round(distance_km(lat, lon, float(ship["latitude"]), float(ship["longitude"])), 2)
    except (OSError, websockets.WebSocketException, json.JSONDecodeError, asyncio.TimeoutError) as exc:
        raise HTTPException(502, "The live AIS vessel search is temporarily unavailable. Please try again.") from exc

    results = [ship for ship in ships.values()
               if ship.get("distance_km") is not None and ship["distance_km"] <= radius_km]
    results.sort(key=lambda item: item["distance_km"])
    for item in results:
        item.setdefault("name", "Name unavailable")
        item.setdefault("vessel_type", "Type unavailable")
    return {"source": "AISStream live AIS", "radius_km": radius_km, "results": results[:100],
            "note": "Nearby vessels from AIS reports received during this live search window. AIS coverage is incomplete; proximity does not imply responsibility."}


@app.get("/api/health")
def health():
    return {"ready": True, "model": MODEL_LABEL, "checkpoint": str(CHECKPOINT), "device": str(DEVICE), "threshold": THRESHOLD}


@app.get("/")
@app.get("/welcome.html", include_in_schema=False)
def welcome():
    return FileResponse(WELCOME_PAGE)


@app.get("/analysis/", include_in_schema=False)
@app.get("/analysis", include_in_schema=False)
def index():
    return FileResponse(HERE.parent / "index.html")


@app.get("/deployment-config.js", include_in_schema=False)
def deployment_config():
    return Response(
        "window.OCEANOVA_ENDPOINTS = Object.freeze({"
        "analysis: window.location.origin, "
        "industry: window.location.origin + '/industry-api', "
        "vessel: window.location.origin + '/vessel-api'"
        "});\n",
        media_type="application/javascript",
    )


@app.post("/api/preview")
async def preview(image: UploadFile = File(...)):
    """Render a quick local-looking thumbnail for browser-incompatible GeoTIFFs."""
    content = await image.read(250 * 1024 * 1024 + 1)
    if len(content) > 250 * 1024 * 1024:
        raise HTTPException(413, "Maximum upload size is 250 MB.")
    try:
        with rasterio.MemoryFile(content) as memfile:
            with memfile.open() as src:
                band = src.read(1, out_shape=(min(src.height, 1000), min(src.width, 1400)))
        low, high = np.nanpercentile(band, (2, 98))
        gray = np.clip((band - low) / max(float(high - low), 1e-6) * 255, 0, 255).astype(np.uint8)
        out = io.BytesIO()
        Image.fromarray(gray).save(out, format="PNG", optimize=True)
        return {"preview_image_base64": base64.b64encode(out.getvalue()).decode("ascii")}
    except rasterio.errors.RasterioError as exc:
        raise HTTPException(422, f"Could not read the uploaded GeoTIFF: {exc}") from exc


@app.get("/industry/", include_in_schema=False)
def industry_frontend():
    from fastapi.responses import FileResponse
    return FileResponse(INDUSTRY_FRONTEND / "index.html")


@app.get("/industry/{asset_name}", include_in_schema=False)
def industry_frontend_asset(asset_name: str):
    from fastapi.responses import FileResponse
    if asset_name not in {"script.js", "style.css"}:
        raise HTTPException(404, "Industry frontend asset not found.")
    return FileResponse(INDUSTRY_FRONTEND / asset_name)


@app.get("/vessel/", include_in_schema=False)
def vessel_frontend():
    from fastapi.responses import FileResponse
    return FileResponse(VESSEL_FRONTEND / "index.html")


@app.post("/api/detect")
async def detect(image: UploadFile = File(...), ground_truth: UploadFile | None = File(None)):
    suffix = Path(image.filename or "image.tif").suffix.lower()
    if suffix not in {".tif", ".tiff"}:
        raise HTTPException(415, "OCEANOVA requires a SAR GeoTIFF (.tif or .tiff).")
    data = await image.read(250 * 1024 * 1024 + 1)
    if len(data) > 250 * 1024 * 1024:
        raise HTTPException(413, "Maximum upload size is 250 MB.")
    if not data:
        raise HTTPException(400, "The uploaded image is empty.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(data)
            temp_path = temp.name
        with rasterio.open(temp_path) as src:
            if src.count < 1 or src.crs is None:
                raise HTTPException(422, "Image must contain a raster band and valid geospatial CRS metadata.")
            sar = src.read(1).astype(np.float32)
            affine, crs = src.transform, src.crs
        if sar.ndim != 2 or min(sar.shape) < 2 or not np.isfinite(sar).all():
            raise HTTPException(422, "The SAR image has invalid dimensions or non-finite pixel values.")

        infer_started = time.perf_counter()
        probability = infer(sar)
        inference_seconds = time.perf_counter() - infer_started
        mask = probability >= THRESHOLD
        count = int(mask.sum())
        evaluation = {"precision": None, "recall": None, "pixel_accuracy": None,
                      "iou": None, "dice": None, "note": "Attach the matching ground-truth mask to calculate per-scene pixel metrics."}
        if ground_truth is not None:
            label_bytes = await ground_truth.read(250 * 1024 * 1024 + 1)
            if len(label_bytes) > 250 * 1024 * 1024:
                raise HTTPException(413, "Ground-truth mask must be 250 MB or smaller.")
            try:
                truth = ground_truth_mask(label_bytes, ground_truth.filename or "ground_truth.geojson", crs, affine, sar.shape)
                evaluation = evaluate_prediction(mask, truth)
                evaluation["note"] = "Per-scene pixel metrics calculated against the ground-truth mask uploaded with this SAR image."
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, rasterio.errors.RasterioError) as exc:
                raise HTTPException(422, f"Could not evaluate against the ground-truth mask: {exc}") from exc
        model_score = float(probability[mask].mean()) if count else float(probability.max())
        result = {"detected": count > 0, "confidence": model_score, "model_score": model_score,
                  "oil_pixels": count, "estimated_area_km2": None, "latitude": None, "longitude": None,
                  "input_image_base64": input_png(sar), "predicted_mask_base64": mask_png(mask),
                  "processed_image_base64": overlay_png(sar, mask), "crs": str(crs),
                  "threshold": THRESHOLD, "model": MODEL_LABEL, "inference_time_seconds": inference_seconds,
                  "evaluation": evaluation, "model_benchmark": MODEL_BENCHMARK}
        if count:
            geometries = [shape(g) for g, value in shapes(mask.astype(np.uint8), mask=mask, transform=affine) if value == 1]
            merged = unary_union(geometries)
            to_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
            geographic = transform_geometry(to_wgs84, merged)
            center = geographic.centroid
            if -180 <= center.x <= 180 and -90 <= center.y <= 90:
                result["longitude"], result["latitude"] = float(center.x), float(center.y)
                result["estimated_area_km2"] = abs(Geod(ellps="WGS84").geometry_area_perimeter(geographic)[0]) / 1_000_000
        return result
    except rasterio.errors.RasterioError as exc:
        raise HTTPException(422, f"Could not read the uploaded GeoTIFF: {exc}") from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
