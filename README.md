# OCEANOVA — quick start

This folder contains the OCEANOVA upload page and the local service that analyzes SAR GeoTIFF images.

## Start it

1. Extract the ZIP to a folder on your computer.
2. Double-click **`start-oceanova.bat`** and wait for the server to start.
3. The first run downloads Python packages, including PyTorch. It needs an internet connection and can take a few minutes.
4. When the terminal says the server is running, open **http://127.0.0.1:8000** in your browser.
5. Choose a `.tif` or `.tiff` SAR image, then click **Analyze image**. Keep the terminal open while you use the site. Press **Ctrl+C** in the terminal to stop the server.

Do not open `index.html` directly. Use the local website address in step 4 so the page can talk to the analysis service.

## What’s included

- `index.html` — OCEANOVA upload, preview, and results page.
- `start-oceanova.bat` — installs/checks dependencies and starts the local service.
- `backend/` — API code and bundled model checkpoint.
- `backend/requirements.txt` — Python packages needed by the service.
- `backend/model/benchmark/garcia_boundary_test.json` — held-out benchmark summary reported by the training pipeline.

## Model metrics

The results grid shows **MODEL SCORE** separately from **PIXEL ACCURACY**. Model Score is this image's prediction score; it is not accuracy. Pixel Accuracy is the overall held-out test-set value for the 22 Garcia boundary-aware U-Net scenes. Precision, Recall and Dice/F1 are also displayed from the held-out evaluation. It is calculated from the matching test split ground-truth pixel total, full image pixel count, and final micro-averaged test metrics using `(TP + TN) / (TP + TN + FP + FN)`. It is separate from the current image Model Score.

The results show the SAR image with the predicted oil region highlighted, generated from the actual uploaded raster. The upload and analysis flow uses the actual selected GeoTIFF. The spill centroid coordinates are transformed from the GeoTIFF CRS and are not predicted directly by the U-Net.

## Nearby industry and vessel searches

- **Nearby industry** queries live OpenStreetMap/Overpass mapped facilities within 50 km. The Overpass `around` filter searches by distance [as documented here](https://wiki.openstreetmap.org/wiki/OverpassQL). Results are sorted by geodesic distance and include an OpenStreetMap attribution. Coverage depends on mapped data; proximity does not establish a cause.
- **Nearby vessel** subscribes to AISStream live AIS reports within 25 km for 8 seconds. Create an AISStream key and set it on the server before starting the app. In PowerShell, run `$env:AISSTREAM_API_KEY="YOUR_KEY"` and then start `start-oceanova.bat`. The API key stays on the backend; AISStream requires server-side WebSocket subscriptions [per its docs](https://aisstream.io/documentation). If no key is configured, the app reports that vessel search is unavailable instead of showing fabricated ships. AIS is a time-limited position feed, not a complete historical track, and nearby vessels are not accused of causing a spill.

The search buttons appear after successful image analysis. They use the detected centroid latitude and longitude; they are disabled if no georeferenced spill centroid was produced.

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
