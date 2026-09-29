// ============================================================
// INDUSTRYRISK
// REAL 3D EARTH + LOCATION SEARCH + NEARBY FACTORIES
// ============================================================


const statusText =
    document.getElementById("statusText");

const latitudeInput =
    document.getElementById("latitudeInput");

const longitudeInput =
    document.getElementById("longitudeInput");

const radiusInput =
    document.getElementById("radiusInput");

const analyzeBtn =
    document.getElementById("analyzeBtn");

const resultText =
    document.getElementById("resultText");

const coordinatesText =
    document.getElementById("coordinates");


const API_BASE_URL =
    window.OCEANOVA_ENDPOINTS?.industry ?? "http://127.0.0.1:5000";

const MAX_SEARCH_RADIUS_METERS =
    200000;

const CESIUM_ION_TOKEN =
    "YOUR_CESIUM_ION_TOKEN";


let viewer;

let searchedLocationEntity = null;

let factoryEntities = [];

let searchCircleEntity = null;


// ============================================================
// CREATE MARKER
// ============================================================

function createPin(color) {

    const svg = `
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="64"
            height="82"
            viewBox="0 0 64 82"
        >

            <path
                d="
                    M32 2
                    C15.4 2 2 15.4 2 32
                    C2 54 32 80 32 80
                    C32 80 62 54 62 32
                    C62 15.4 48.6 2 32 2Z
                "

                fill="${color}"

                stroke="#ffffff"

                stroke-width="3"
            />

            <circle
                cx="32"
                cy="31"
                r="12"

                fill="#071019"

                opacity="0.9"
            />

            <circle
                cx="32"
                cy="31"
                r="5"

                fill="#ffffff"
            />

        </svg>
    `;

    return (
        "data:image/svg+xml;charset=UTF-8," +
        encodeURIComponent(svg)
    );
}


// GREEN = SEARCHED LOCATION
const GREEN_PIN =
    createPin("#35e59a");


// RED = FACTORY
const RED_PIN =
    createPin("#ff3e4d");


// ============================================================
// START CESIUM 3D EARTH
// ============================================================

function initializeEarth() {

    const hasCesiumToken =
        CESIUM_ION_TOKEN &&
        CESIUM_ION_TOKEN !== "YOUR_CESIUM_ION_TOKEN";

    if (hasCesiumToken) {
        Cesium.Ion.defaultAccessToken =
            CESIUM_ION_TOKEN;
    }

    viewer = new Cesium.Viewer(
        "cesiumContainer",
        {

            baseLayer: false,

            terrain: hasCesiumToken
                ? Cesium.Terrain.fromWorldTerrain()
                : undefined,

            terrainProvider: hasCesiumToken
                ? undefined
                : new Cesium.EllipsoidTerrainProvider(),

            animation: false,

            timeline: false,

            baseLayerPicker: false,

            geocoder: false,

            homeButton: false,

            sceneModePicker: false,

            navigationHelpButton: false,

            fullscreenButton: false,

            infoBox: true,

            selectionIndicator: true
        }
    );

    const satelliteProvider =
        new Cesium.UrlTemplateImageryProvider({
            url:
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",

            credit:
                "Esri World Imagery",

            maximumLevel: 19,

            enablePickFeatures: false
        });

    viewer.imageryLayers.addImageryProvider(
        satelliteProvider
    );

    viewer.scene.mode = Cesium.SceneMode.SCENE3D;
    viewer.scene.globe.show = true;
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.screenSpaceCameraController.enableTilt = true;
    viewer.scene.screenSpaceCameraController.enableRotate = true;


    // Lighting
    viewer.scene.globe.enableLighting = false;


    // Earth atmosphere
    viewer.scene.globe.showGroundAtmosphere = true;


    // Dark space colour
    viewer.scene.backgroundColor =
        Cesium.Color.fromCssColorString(
            "#020810"
        );


    // Start camera above Earth
    viewer.camera.setView({

        destination:
            Cesium.Cartesian3.fromDegrees(
                78.9629,
                20.5937,
                8000000
            )
    });


    statusText.textContent =
        "SYSTEM READY";
}


initializeEarth();


// ============================================================
// REMOVE OLD SEARCH RESULTS
// ============================================================

function clearResults() {

    // Remove green marker
    if (searchedLocationEntity) {

        viewer.entities.remove(
            searchedLocationEntity
        );

        searchedLocationEntity = null;
    }


    // Remove factory markers
    factoryEntities.forEach(
        entity => {

            viewer.entities.remove(
                entity
            );
        }
    );


    factoryEntities = [];


    // Remove radius
    if (searchCircleEntity) {

        viewer.entities.remove(
            searchCircleEntity
        );

        searchCircleEntity = null;
    }
}


// ============================================================
// GREEN SEARCH LOCATION
// ============================================================

function addSearchedLocation(
    latitude,
    longitude,
    label
) {

    searchedLocationEntity =
        viewer.entities.add({

            name:
                "Searched Location",


            position:
                Cesium.Cartesian3.fromDegrees(
                    longitude,
                    latitude
                ),


            billboard: {

                image:
                    GREEN_PIN,

                width: 38,

                height: 49,

                verticalOrigin:
                    Cesium.VerticalOrigin.BOTTOM,

                disableDepthTestDistance:
                    Number.POSITIVE_INFINITY,

                show: true
            },

            ellipse: {

                semiMajorAxis:
                    new Cesium.CallbackProperty(
                        () => 120 + (Date.now() % 1200) / 4,
                        false
                    ),

                semiMinorAxis:
                    new Cesium.CallbackProperty(
                        () => 120 + (Date.now() % 1200) / 4,
                        false
                    ),

                material:
                    Cesium.Color.fromCssColorString(
                        "#38e59d"
                    ).withAlpha(0.12),

                outline: true,

                outlineColor:
                    Cesium.Color.fromCssColorString(
                        "#38e59d"
                    ).withAlpha(0.85),

                outlineWidth: 2
            },


            label: {

                text:
                    label ||
                    "Searched Location",

                font:
                    "bold 13px Arial",

                fillColor:
                    Cesium.Color.WHITE,

                outlineColor:
                    Cesium.Color.BLACK,

                outlineWidth: 3,

                style:
                    Cesium.LabelStyle
                        .FILL_AND_OUTLINE,

                pixelOffset:
                    new Cesium.Cartesian2(
                        0,
                        -54
                    ),

                disableDepthTestDistance:
                    Number.POSITIVE_INFINITY,

                show: true
            },


            description: `

                <b>Searched Location</b>

                <br><br>

                Latitude:
                ${latitude.toFixed(6)}

                <br>

                Longitude:
                ${longitude.toFixed(6)}

                <br><br>

                This green marker represents
                the location searched by the user.

                <br><br>

                It does NOT mean that a factory
                exists at this exact location.

            `
        });
}


// ============================================================
// SEARCH RADIUS
// ============================================================

function addSearchRadius(
    latitude,
    longitude,
    radius
) {

    searchCircleEntity =
        viewer.entities.add({

            position:
                Cesium.Cartesian3.fromDegrees(
                    longitude,
                    latitude
                ),


            ellipse: {

                semiMajorAxis:
                    radius,

                semiMinorAxis:
                    radius,


                material:
                    Cesium.Color
                        .fromCssColorString(
                            "#45d6c5"
                        )
                        .withAlpha(0.055),


                outline:
                    true,


                outlineColor:
                    Cesium.Color
                        .fromCssColorString(
                            "#45d6c5"
                        )
                        .withAlpha(0.55),


                outlineWidth: 2
            }
        });
}


// ============================================================
// RED FACTORY MARKER
// ============================================================

function addFactoryMarker(
    factory
) {

    const latitude =
        Number(
            factory.latitude ??
            factory.lat ??
            factory.location?.latitude ??
            factory.location?.lat
        );


    const longitude =
        Number(
            factory.longitude ??
            factory.lon ??
            factory.lng ??
            factory.location?.longitude ??
            factory.location?.lon ??
            factory.location?.lng
        );


    // Skip invalid factory
    if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude)
    ) {
        return;
    }


    const name =
        factory.name ||
        factory.company ||
        factory.title ||
        "Industrial Facility";

    const risk =
        factory.risk ||
        "UNKNOWN";


    const entity =
        viewer.entities.add({

            name: name,


            position:
                Cesium.Cartesian3.fromDegrees(
                    longitude,
                    latitude
                ),


            billboard: {

                image:
                    RED_PIN,

                width: 34,

                height: 44,

                verticalOrigin:
                    Cesium.VerticalOrigin.BOTTOM,

                disableDepthTestDistance:
                    Number.POSITIVE_INFINITY
            },


            label: {

                text: name + " [" + risk + "]",

                font:
                    "bold 12px Arial",

                fillColor:
                    Cesium.Color.fromCssColorString(
                        "#ff6973"
                    ),

                outlineColor:
                    Cesium.Color.BLACK,

                outlineWidth: 3,

                style:
                    Cesium.LabelStyle
                        .FILL_AND_OUTLINE,

                pixelOffset:
                    new Cesium.Cartesian2(
                        0,
                        -48
                    ),

                disableDepthTestDistance:
                    Number.POSITIVE_INFINITY,

                show: false
            },


            description: `

                <b>${escapeHtml(name)}</b>

                <br><br>

                Potential industrial spill-source candidate

                <br>

                Not a confirmed spill source

                <br>

                Oil relevance: ${factory.oil_source_relevance_score ?? 0}/100

                <br>

                Connectivity: ${factory.connectivity_score ?? 0}/100

                <br>

                Proximity: ${factory.proximity_score ?? 0}/30

                <br>

                Final potential-source score: ${factory.potential_source_score ?? 0}/100

                <br>

                ${escapeHtml(factory.reason || "No additional mapped evidence.")}

                <br>

                Latitude:
                ${latitude.toFixed(6)}

                <br>

                Longitude:
                ${longitude.toFixed(6)}

            `
        });


    factoryEntities.push(entity);
}


// ============================================================
// GET LATITUDE + LONGITUDE
// ============================================================

async function getCoordinates(input) {

    const text =
        input.trim();


    // --------------------------------------------------------
    // USER CAN ENTER:
    //
    // 10.5276, 76.2144
    // --------------------------------------------------------

    const coordinateMatch =
        text.match(
            /^(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)$/
        );


    if (coordinateMatch) {

        const latitude =
            Number(
                coordinateMatch[1]
            );


        const longitude =
            Number(
                coordinateMatch[2]
            );


        if (
            latitude >= -90 &&
            latitude <= 90 &&
            longitude >= -180 &&
            longitude <= 180
        ) {

            return {

                latitude,

                longitude,

                displayName:
                    "Selected Coordinates"
            };
        }
    }


    // --------------------------------------------------------
    // OTHERWISE SEARCH ADDRESS
    // --------------------------------------------------------

    const response =
        await fetch(
            API_BASE_URL +
            "/geocode?text=" +
            encodeURIComponent(text)
        );


    const data = await response.json();

    if (!response.ok || data.success === false) {
        throw new Error(
            data.error ||
            "Could not find that place. Try a fuller city, address, or place name. Coordinates are optional."
        );
    }


    const result =
        Array.isArray(data)
            ? data[0]
            : data;


    if (!result) {

        throw new Error(
            "Location not found."
        );
    }


    const latitude =
        Number(
            result.latitude ??
            result.lat
        );


    const longitude =
        Number(
            result.longitude ??
            result.lon ??
            result.lng
        );


    if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude)
    ) {

        throw new Error(
            "Invalid coordinates returned."
        );
    }


    return {

        latitude,

        longitude,

        displayName:
            result.address ||
            result.display_name ||
            result.name ||
            text
    };
}


// ============================================================
// FIND NEARBY INDUSTRIES
// ============================================================

async function findNearbyIndustries(
    latitude,
    longitude,
    radius
) {

    const response =
        await fetch(
            API_BASE_URL + "/nearby-industries",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    latitude,
                    longitude,
                    radius
                })
            }
        );


    const data =
        await response.json();

    if (!response.ok || data.success === false) {
        throw new Error(
            [data.error, data.details].filter(Boolean).join(" ") ||
            "Nearby industry search failed."
        );
    }


    return {
        sources: data.potential_sources || data.nearby_sources || [],
        otherNearbyFacilities: data.other_nearby_facilities || [],
        providers: data.providers || {},
        providerErrors: data.provider_errors || {},
        searchRadiusMeters: data.search_radius_m
    };
}


// ============================================================
// ANALYZE LOCATION
// ============================================================

analyzeBtn.addEventListener(
    "click",
    async () => {

        if (!API_BASE_URL) {
            resultText.textContent = "Industry search is not connected yet. Add OCEANOVA_INDUSTRY_URL in Vercel after deploying the Railway API.";
            statusText.textContent = "API NOT CONFIGURED";
            return;
        }

        const latitude = Number(latitudeInput.value);
        const longitude = Number(longitudeInput.value);
        const radiusKm = Number(radiusInput.value);
        const searchRadiusMeters = radiusKm * 1000;

        if (
            latitudeInput.value.trim() === "" ||
            longitudeInput.value.trim() === "" ||
            !Number.isFinite(latitude) ||
            latitude < -90 ||
            latitude > 90 ||
            !Number.isFinite(longitude) ||
            longitude < -180 ||
            longitude > 180 ||
            !Number.isFinite(radiusKm) ||
            radiusKm <= 0 ||
            searchRadiusMeters > MAX_SEARCH_RADIUS_METERS
        ) {

            resultText.textContent =
                "Enter a valid latitude, longitude, and radius greater than 0 km and no more than 200 km.";

            return;
        }


        analyzeBtn.disabled =
            true;


        statusText.textContent =
            "ANALYZING LOCATION...";


        resultText.textContent =
            "Finding the selected location...";


        // Remove previous markers
        clearResults();


        try {

            // ------------------------------------------------
            // GREEN MARKER
            // ONLY SEARCHED LOCATION
            // ------------------------------------------------

            addSearchedLocation(
                latitude,
                longitude,
                formatCoordinatePair(latitude, longitude)
            );


            // ------------------------------------------------
            // STEP 3:
            // SEARCH RADIUS
            // ------------------------------------------------

            addSearchRadius(
                latitude,
                longitude,
                searchRadiusMeters
            );


            // Show coordinates
            coordinatesText.textContent =
                formatCoordinatePair(
                    latitude,
                    longitude
                );


            // ------------------------------------------------
            // STEP 4:
            // MOVE CAMERA
            // ------------------------------------------------

            await viewer.camera.flyTo({

                destination:
                    Cesium.Cartesian3.fromDegrees(
                        longitude,
                        latitude,

                        Math.max(
                            searchRadiusMeters * 2.8,
                            18000
                        )
                    ),

                orientation: {
                    heading: Cesium.Math.toRadians(0),
                    pitch: Cesium.Math.toRadians(-65),
                    roll: 0
                },

                duration: 3
            });


            // ------------------------------------------------
            // STEP 5:
            // SEARCH FACTORIES
            // ------------------------------------------------

            resultText.textContent =
                    "Searching for potential industrial spill-source candidates...";


            const searchResult =
                await findNearbyIndustries(
                    latitude,
                    longitude,
                    searchRadiusMeters
                );
            const reportedRadiusMeters =
                Number(searchResult.searchRadiusMeters ?? searchRadiusMeters);
            const factories = searchResult.sources;
            const otherFacilities = searchResult.otherNearbyFacilities;

            const renderRiskRows = (items, startIndex = 0) => items.map(
                (factory, index) => `
                    <tr>
                        <td>${startIndex + index + 1}</td>
                        <td>${escapeHtml(factory.name || "Industrial Facility")}</td>
                        <td>${escapeHtml(factory.industry_type || "Industrial category")}</td>
                        <td>${factory.distance_km ?? "-"} km</td>
                        <td>${factory.oil_source_relevance_score ?? 0}/100</td>
                        <td>${factory.connectivity_score ?? 0}/100</td>
                        <td>${factory.proximity_score ?? 0}/30</td>
                        <td><span class="risk-badge risk-${String(factory.risk || "LOW").toLowerCase().replaceAll(" ", "-")}">${escapeHtml(factory.risk || "LOW")}</span><br>${factory.potential_source_score ?? factory.risk_score ?? "-"}/100</td>
                        <td>${escapeHtml(factory.reason || "No direct oil-related evidence in mapped data. No mapped pathway identified.")}</td>
                    </tr>
                `
            ).join("");


            // ------------------------------------------------
            // STEP 6:
            // RED MARKERS
            // FACTORIES ONLY
            // ------------------------------------------------

            factories.slice(0, 10).forEach(
                addFactoryMarker
            );


            // ------------------------------------------------
            // RESULTS
            // ------------------------------------------------

            if (
                factories.length === 0
            ) {

                const otherRiskRows = renderRiskRows(otherFacilities);
                resultText.innerHTML = `
                    <strong>No potential oil-spill source identified from available mapped data.</strong>
                    <small class="risk-subtitle">No oil-related evidence was found among the mapped candidates within ${formatDistance(reportedRadiusMeters)}.</small>
                    ${otherFacilities.length ? `<p>Other nearby facilities are listed separately below.</p>` : ""}
                    ${searchResult.providerErrors.geoapify
                        ? `<p>Geoapify search error: ${escapeHtml(searchResult.providerErrors.geoapify)}.</p>`
                        : ""}
                    ${otherFacilities.length ? `
                        <details class="other-facilities">
                            <summary>Other Nearby Facilities (${otherFacilities.length})</summary>
                            <div class="risk-table-wrap">
                                <table class="risk-table">
                                    <thead><tr><th>#</th><th>Facility</th><th>Type</th><th>Distance</th><th>Oil relevance</th><th>Connectivity</th><th>Proximity</th><th>Risk / final score</th><th>Reason</th></tr></thead>
                                    <tbody>${otherRiskRows}</tbody>
                                </table>
                            </div>
                        </details>
                    ` : ""}
                `;


                statusText.textContent =
                    "NO OIL-RELATED SOURCES FOUND";

            }

            else {
                const riskRows = renderRiskRows(factories);
                const otherRiskRows = renderRiskRows(otherFacilities, factories.length);

                resultText.innerHTML = `
                    <strong>Potential Oil-Spill Sources (${factories.length})</strong>
                    <small class="risk-subtitle">Within ${formatDistance(reportedRadiusMeters)} of ${formatCoordinatePair(latitude, longitude)}</small>
                    <small class="risk-subtitle">Potential ranking only; these results do not confirm a facility caused a spill.</small>
                    <div class="risk-table-wrap">
                        <table class="risk-table">
                            <thead>
                                <tr><th>#</th><th>Facility</th><th>Type</th><th>Distance</th><th>Oil relevance</th><th>Connectivity</th><th>Proximity</th><th>Risk / final score</th><th>Reason</th></tr>
                            </thead>
                            <tbody>${riskRows}</tbody>
                        </table>
                    </div>
                    ${otherFacilities.length ? `
                        <details class="other-facilities">
                            <summary>Other Nearby Facilities (${otherFacilities.length})</summary>
                            <div class="risk-table-wrap">
                                <table class="risk-table">
                                    <thead><tr><th>#</th><th>Facility</th><th>Type</th><th>Distance</th><th>Oil relevance</th><th>Connectivity</th><th>Proximity</th><th>Risk / final score</th><th>Reason</th></tr></thead>
                                    <tbody>${otherRiskRows}</tbody>
                                </table>
                            </div>
                        </details>
                    ` : ""}
                `;


                statusText.textContent =
                    "ANALYSIS COMPLETE";
            }


        }

        catch (error) {

            console.error(error);

            const errorMessage = error.message ||
                "Something went wrong while analyzing the location.";
            const backendUnavailable =
                error instanceof TypeError &&
                /fetch|network/i.test(errorMessage);
            resultText.textContent = backendUnavailable
                ? `${errorMessage} Check that the backend is running at ${API_BASE_URL}.`
                : errorMessage;


            statusText.textContent =
                "ANALYSIS ERROR";
        }


        finally {

            analyzeBtn.disabled =
                false;
        }

    }
);


// ============================================================
// DISTANCE FORMAT
// ============================================================

function formatDistance(
    meters
) {

    if (meters >= 1000) {

        return (

            (
                meters / 1000
            ).toFixed(
                meters % 1000 === 0
                    ? 0
                    : 1
            )

            +

            " km"
        );
    }


    return meters + " m";
}


// ============================================================
// HTML SAFETY
// ============================================================

function escapeHtml(
    value
) {

    return String(value)

        .replaceAll(
            "&",
            "&amp;"
        )

        .replaceAll(
            "<",
            "&lt;"
        )

        .replaceAll(
            ">",
            "&gt;"
        )

        .replaceAll(
            '"',
            "&quot;"
        )

        .replaceAll(
            "'",
            "&#039;"
        );
}


function formatCoordinatePair(
    latitude,
    longitude
) {

    const latitudeDirection =
        latitude >= 0 ? "N" : "S";

    const longitudeDirection =
        longitude >= 0 ? "E" : "W";

    return (
        Math.abs(latitude).toFixed(6) +
        "° " +
        latitudeDirection +
        ", " +
        Math.abs(longitude).toFixed(6) +
        "° " +
        longitudeDirection
    );
}


const queryParameters =
    new URLSearchParams(window.location.search);

const latitudeFromQuery =
    queryParameters.get("lat");

const longitudeFromQuery =
    queryParameters.get("lon");

if (
    latitudeFromQuery !== null &&
    longitudeFromQuery !== null
) {
    const latitude = Number(latitudeFromQuery);
    const longitude = Number(longitudeFromQuery);

    if (
        Number.isFinite(latitude) &&
        latitude >= -90 &&
        latitude <= 90 &&
        Number.isFinite(longitude) &&
        longitude >= -180 &&
        longitude <= 180
    ) {
        latitudeInput.value = String(latitude);
        longitudeInput.value = String(longitude);
        analyzeBtn.click();
    } else {
        statusText.textContent = "INVALID COORDINATES";
        resultText.textContent =
            "The latitude and longitude received from the previous page are invalid.";
    }
}
