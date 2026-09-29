# OCEANOVA local run guide

## Start the backend (PowerShell)

Open PowerShell in this project folder and run:

```powershell
cd .\sih-backend-main\bakend
# If this virtual environment was created for a removed/moved Python install,
# delete it before recreating it:
# Remove-Item -Recurse -Force .venv
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If `py -m venv .venv` reports that no Python installation is found, install
Python 3.11 or newer with the Python launcher enabled, then reopen PowerShell.
The backend needs Flask and Requests from `requirements.txt`. An existing
virtual environment stops working if its base Python installation is moved or
removed.

Keep that PowerShell window open. The backend serves the frontend at
`http://127.0.0.1:5000` and searches broad facility candidates through Geoapify
within the selected radius (up to 200 km). Internet access and a Geoapify API
key are required for nearby facility discovery. Add the key to
`sih-backend-main\bakend\.env` to enable facility discovery:

```text
GEOAPIFY_API_KEY=your_key_here
```

Address lookup also uses Geoapify. The backend filters broad candidate results
using facility names, categories, address text, Geoapify properties, and
available raw OSM tags, then calculates exact Haversine distances and returns
only results inside the selected radius. Oil relevance, proximity, and
mapped-pathway connectivity are returned separately. Facilities without oil
evidence remain LOW with a final score of zero. Exact oil infrastructure
descriptions (such as oil/petroleum ports, terminals, refineries, tank farms,
storage, bunkering, oil pipelines, and diesel power plants) receive the
strongest oil relevance. Generic ports, pipelines, factories, and power plants
do not establish oil relevance by themselves. The final score weights oil
relevance at 90%, connectivity at 7%, and proximity at 3%, so distance alone
cannot create a high source score. Nearby facilities are checked across names,
categories, tags, product, substance, and facility type. Oil-evidenced
facilities are returned first in `potential_sources`, sorted by oil relevance,
connectivity, then distance. Facilities without oil evidence are listed under
`other_nearby_facilities`. Discovery merges broad industrial category results
with focused Geoapify name searches for refinery, petroleum, oil, fuel, tank
farm, petrochemical, bunkering, tanker, diesel, and crude terms; duplicate
locations are merged before classification. Harbour/port connectivity raises
priority when oil/fuel evidence is also mapped, while a generic harbour stays
outside the potential-source list. Facilities are
potential candidates, not confirmed spill sources.

## Open the app

Visit `http://127.0.0.1:5000` in your browser. Do not open `frontend/index.html`
directly from File Explorer. Enter latitude and longitude in their separate
fields, choose a radius, and click Analyze.

If you change Python files, stop the server with Ctrl+C and run `py app.py`
again. Search results depend on which facilities are mapped by the data
providers, and an empty result does not confirm there are no industrial sites.
