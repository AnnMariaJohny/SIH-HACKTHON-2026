# OCEANOVA — quick start

This folder contains the OCEANOVA welcome, login, analysis, industry, and vessel screens, with one launcher for the local services.

## Requirements

- Windows with Python 3.11 or newer.
- Internet access for first-run package installation and live industry/vessel data.
- Geoapify and AISStream API keys configured in the existing local `.env` files.

## Start the app

Double-click `start-oceanova.bat`. On first run it installs the dependencies and starts one FastAPI server on port `8000`. Welcome, Login/Register, Analysis, Industry, Vessel, and all API requests use that port. Open **http://127.0.0.1:8000** to begin; press Ctrl+C in the launcher window to stop the app.

The Geoapify and AISStream keys are read from the local `.env` files in `sih-backend-main/sih-backend-main/bakend/` and `anzil/sih_backend-main/backend/`. Use each folder's `.env.example` as a template if a key is not configured; do not commit API keys.

Do not open the HTML files directly. Choose a `.tif` or `.tiff` SAR image and click **Analyze image**. Industry and Vessel APIs are mounted at `/industry-api` and `/vessel-api` on the same server.

## Deploy online

The root `vercel.json` defines four Vercel Services: a static frontend, SAR analysis, industry search, and vessel search. Import this repository into a Vercel project with Services enabled. Each service builds from the root path declared in `vercel.json`; Vercel's project-level rewrites expose the frontend and the API paths.

Public paths in the proposed routing are `/` and other page/static paths to the frontend, `/api/*` to SAR, `/api/ships` to vessel, and `/geocode` plus `/nearby-industries` to industry. The browser calls these same-origin paths, so no service bindings are needed: there are no server-side calls between the backend services. Geoapify and AISStream are external providers and their API keys belong in the matching Vercel service environment variables, not in the frontend.

Vercel Services are a beta feature that may require account access. Before relying on this deployment for a submission, note the platform constraints: Vercel Functions have a 4.5 MB request-body limit, while SAR uploads currently allow up to 250 MB; the PyTorch model also needs substantial memory. The AIS service starts a background WebSocket collector, which is not guaranteed to persist between serverless invocations. Large-image analysis and live vessel collection may therefore need a long-running backend host even if the site itself is served by Vercel.

## What’s included

- `Sih hackthon/welcome.html` — OCEANOVA entry page.
- `index.html` — OCEANOVA upload, preview, and results page, served at `/analysis/`.
- `start-oceanova.bat` — installs/checks dependencies and starts the unified local server.
- `backend/` — API code and bundled model checkpoint.
- `backend/requirements.txt` — Python packages needed by the service.
- `backend/model/benchmark/garcia_boundary_test.json` — held-out benchmark summary reported by the training pipeline.

## Model metrics

The results grid shows **MODEL SCORE** separately from **PIXEL ACCURACY**. Model Score is this image's prediction score; it is not accuracy. Pixel Accuracy is the overall held-out test-set value for the 22 Garcia boundary-aware U-Net scenes. Precision, Recall and Dice/F1 are also displayed from the held-out evaluation. It is calculated from the matching test split ground-truth pixel total, full image pixel count, and final micro-averaged test metrics using `(TP + TN) / (TP + TN + FP + FN)`. It is separate from the current image Model Score.

The results show the SAR image with the predicted oil region highlighted, generated from the actual uploaded raster. The upload and analysis flow uses the actual selected GeoTIFF. The spill centroid coordinates are transformed from the GeoTIFF CRS and are not predicted directly by the U-Net.

## Nearby searches

After image analysis, the **Search Nearby Industry** and **Search Nearby Vessel** buttons pass the spill centroid latitude and longitude from the SAR result into their respective screens. Each screen fills the coordinates and starts its search automatically. The coordinates come from the GeoTIFF geospatial metadata; the U-Net predicts the oil mask, not latitude or longitude. A valid georeferenced centroid is required.

- **Industry** uses the Geoapify-backed API through port `8000` with a default search radius of 200 km. Results are mapped candidates, not confirmed spill sources; coverage depends on provider data.
- **Vessel** uses the AISStream-backed API through port `8000` with a default search radius of 100 km. AIS positions are time-limited and may not include every vessel; proximity does not establish cause.

The real-data `Eclipso_Final_UNet.pt` checkpoint from the supplied checkpoints archive is included in `backend/model/weights/`. The app loads this Garcia-INPE boundary-aware U-Net and uses the notebook's normalization, 256-pixel tiles, 128-pixel stride, and 0.96 threshold. It does not silently substitute another model. The final held-out test-set pixel accuracy is **99.32%**, calculated to two decimals from the 22 matching 800×600 scenes. The notebook reports micro-averaged test metrics to four decimal places; the matching test split provides 115,125 ground-truth oil pixels across 10,560,000 total pixels. The resulting confusion-count combinations all round to the same 99.32% accuracy.

If you replace or remove the included checkpoint, you can restore it from the notebook's Google Drive:

1. In the Colab notebook, run this cell after mounting the same Google Drive that contains the checkpoint:
   `from google.colab import files; files.download('/content/drive/MyDrive/Eclipso/checkpoints/Eclipso_Final_UNet.pt')`
2. Copy the downloaded file to `backend/model/weights/Eclipso_Final_UNet.pt` in this app folder.
3. Restart `start-oceanova.bat`. The backend automatically prefers that checkpoint. The UI identifies which model was loaded.

Alternatively, set `ECLIPSO_CHECKPOINT` to the full path of another compatible Garcia-trained U-Net checkpoint before launching the server. The service refuses to start if the real checkpoint is missing or the supplied file is not in the Garcia checkpoint format; it never silently switches to a different model.

Only georeferenced, single-band SAR GeoTIFF images are supported. Coordinates and area use the image’s geospatial metadata when available. Confidence is a model score, not accuracy.

## Evaluation metrics

The Accuracy card is the overall held-out test-set pixel accuracy; it does not depend on a mask being uploaded with the current image. Model Score never fills the Accuracy card. The real checkpoint is included; the terminal prints the loaded model/checkpoint on startup.
