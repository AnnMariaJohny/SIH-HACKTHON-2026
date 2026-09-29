# OCEANOVA — quick start

This folder contains the OCEANOVA upload page and the local service that analyzes SAR GeoTIFF images.

## Requirements

- Windows with Python 3.11 or newer.
- Internet access for first-run package installation and live industry/vessel data.
- A Geoapify API key for industry searches and an AISStream API key for vessel searches.

## Start the app

The app uses three local services. Start each in its own PowerShell window from the project root and leave all three running while using the app.

### 1. SAR analysis and main page

Double-click `start-oceanova.bat`. On first run it installs Python packages, including PyTorch, and loads the bundled model. Open **http://127.0.0.1:8000** after the terminal reports that Uvicorn is running.

### 2. Nearby industry API

In a second PowerShell window:

```powershell
Set-Location .\sih-backend-main\sih-backend-main\bakend
$env:GEOAPIFY_API_KEY = "your Geoapify API key"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

This API listens on port `5000`. Set the key in this PowerShell session before starting the service; do not commit API keys to the repository.

### 3. Nearby vessel API

In a third PowerShell window:

```powershell
Set-Location .\anzil\sih_backend-main\backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Configure `AISSTREAM_API_KEY` in `anzil/sih_backend-main/backend/.env` using `.env.example` as a template. This API listens on port `5001`.

Do not open `index.html` directly. Use **http://127.0.0.1:8000** so the browser can reach the local services. Choose a `.tif` or `.tiff` SAR image and click **Analyze image**. Keep all service windows open; press Ctrl+C in each one to stop its service.

## What’s included

- `index.html` — OCEANOVA upload, preview, and results page.
- `start-oceanova.bat` — installs/checks dependencies and starts the local service.
- `backend/` — API code and bundled model checkpoint.
- `backend/requirements.txt` — Python packages needed by the service.
- `backend/model/benchmark/garcia_boundary_test.json` — held-out benchmark summary reported by the training pipeline.

## Model metrics

The results grid shows **MODEL SCORE** separately from **PIXEL ACCURACY**. Model Score is this image's prediction score; it is not accuracy. Pixel Accuracy is the overall held-out test-set value for the 22 Garcia boundary-aware U-Net scenes. Precision, Recall and Dice/F1 are also displayed from the held-out evaluation. It is calculated from the matching test split ground-truth pixel total, full image pixel count, and final micro-averaged test metrics using `(TP + TN) / (TP + TN + FP + FN)`. It is separate from the current image Model Score.

The results show the SAR image with the predicted oil region highlighted, generated from the actual uploaded raster. The upload and analysis flow uses the actual selected GeoTIFF. The spill centroid coordinates are transformed from the GeoTIFF CRS and are not predicted directly by the U-Net.

## Nearby searches

After image analysis, the **Search Nearby Industry** and **Search Nearby Vessel** buttons pass the spill centroid latitude and longitude from the SAR result into their respective screens. Each screen fills the coordinates and starts its search automatically. The coordinates come from the GeoTIFF geospatial metadata; the U-Net predicts the oil mask, not latitude or longitude. A valid georeferenced centroid is required.

- **Industry** uses the Geoapify-backed service on port `5000` with a default search radius of 200 km. Results are mapped candidates, not confirmed spill sources; coverage depends on provider data.
- **Vessel** uses the AISStream-backed service on port `5001` with a default search radius of 100 km. AIS positions are time-limited and may not include every vessel; proximity does not establish cause.

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
