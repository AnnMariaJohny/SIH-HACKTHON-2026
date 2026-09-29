import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";


// ============================================================
// SCENE
// ============================================================

const scene = new THREE.Scene();

scene.background = new THREE.Color(0x000000);


// ============================================================
// CAMERA
// ============================================================

const camera = new THREE.PerspectiveCamera(
    38,
    window.innerWidth / window.innerHeight,
    0.1,
    2000
);

// Smaller Earth appearance like the video
camera.position.set(0, 0, 3.2);


// ============================================================
// RENDERER
// ============================================================

const renderer = new THREE.WebGLRenderer({
    antialias: true,
    powerPreference: "high-performance"
});

renderer.setSize(
    window.innerWidth,
    window.innerHeight
);

renderer.setPixelRatio(
    Math.min(window.devicePixelRatio, 2)
);

renderer.shadowMap.enabled = false;

renderer.outputColorSpace = THREE.SRGBColorSpace;

renderer.toneMapping =
    THREE.ACESFilmicToneMapping;

renderer.toneMappingExposure = 1.05;

document
    .getElementById("earth-container")
    .appendChild(renderer.domElement);


// ============================================================
// CONTROLS
// ============================================================

const controls = new OrbitControls(
    camera,
    renderer.domElement
);

controls.enableDamping = true;

controls.dampingFactor = 0.035;

controls.enablePan = false;
controls.enableZoom = false;

controls.minDistance = 2.0;

controls.maxDistance = 7.0;


// ============================================================
// LIGHTING
// ============================================================

// Sunlight from the right keeps the satellite's left side shaded.
const sun = new THREE.DirectionalLight(
    0xffffff,
    3.5
);

sun.position.set(
    5,
    3,
    5
);

scene.add(sun);


// Soft blue fill light
const ambient = new THREE.AmbientLight(
    0x416b91,
    0.12
);

scene.add(ambient);

const rimLight = new THREE.DirectionalLight(
    0x347dff,
    1.15
);
rimLight.position.set(-4, 1.5, -3);
scene.add(rimLight);


// ============================================================
// EARTH GROUP
// ============================================================

const earthGroup = new THREE.Group();

scene.add(earthGroup);


// ============================================================
// TEXTURES
// ============================================================

const loader = new THREE.TextureLoader();


// ------------------------------------------------------------
// REAL EARTH DAY TEXTURE
// ------------------------------------------------------------

const earthDay = loader.load(
    "https://cdn.apewebapps.com/threejs/168/examples/textures/planets/earth_day_4096.jpg"
);

earthDay.colorSpace =
    THREE.SRGBColorSpace;

earthDay.anisotropy =
    renderer.capabilities.getMaxAnisotropy();


// ------------------------------------------------------------
// NORMAL MAP
// ------------------------------------------------------------

const earthNormal = loader.load(
    "https://cdn.apewebapps.com/threejs/168/examples/textures/planets/earth_normal_2048.jpg"
);


// ------------------------------------------------------------
// SPECULAR MAP
// ------------------------------------------------------------

const earthSpecular = loader.load(
    "https://cdn.apewebapps.com/threejs/168/examples/textures/planets/earth_specular_2048.jpg"
);


// ------------------------------------------------------------
// CLOUDS
// ------------------------------------------------------------

const cloudTexture = loader.load(
    "https://cdn.apewebapps.com/threejs/168/examples/textures/planets/earth_clouds_2048.png"
);

cloudTexture.colorSpace =
    THREE.SRGBColorSpace;

cloudTexture.anisotropy =
    renderer.capabilities.getMaxAnisotropy();


// ============================================================
// EARTH
// ============================================================

const earthGeometry =
    new THREE.SphereGeometry(
        0.78,
        128,
        128
    );


const earthMaterial =
    new THREE.MeshPhongMaterial({

        map: earthDay,

        normalMap: earthNormal,

        normalScale:
            new THREE.Vector2(
                0.75,
                0.75
            ),

        specularMap:
            earthSpecular,

        specular:
            new THREE.Color(
                0x222222
            ),

        shininess: 18,

        color:
            new THREE.Color(
                0xffffff
            )

    });


const earth =
    new THREE.Mesh(
        earthGeometry,
        earthMaterial
    );

earthGroup.add(earth);


// ============================================================
// CLOUD LAYER
// ============================================================

const cloudGeometry =
    new THREE.SphereGeometry(
        0.79,
        128,
        128
    );


const cloudMaterial =
    new THREE.MeshPhongMaterial({

        map: cloudTexture,

        transparent: true,

        opacity: 0.72,

        depthWrite: false,

        alphaTest: 0.02,

        side: THREE.DoubleSide,

        color:
            new THREE.Color(
                0xf4f9ff
            )

    });


const clouds =
    new THREE.Mesh(
        cloudGeometry,
        cloudMaterial
    );

earthGroup.add(clouds);


// ============================================================
// SECOND VERY SOFT CLOUD LAYER
// ============================================================
//
// Gives the clouds more depth without creating
// an obvious outline.
//

const cloudSoftMaterial =
    new THREE.MeshPhongMaterial({

        map: cloudTexture,

        transparent: true,

        opacity: 0.08,

        depthWrite: false,
        alphaTest: 0.01,
        side: THREE.DoubleSide,
        color:
            new THREE.Color(
                0xffffff
            )

    });


const softClouds =
    new THREE.Mesh(

        new THREE.SphereGeometry(
            0.802,
            96,
            96
        ),

        cloudSoftMaterial

    );

earthGroup.add(softClouds);


// ============================================================
// ORBITING SATELLITE
// ============================================================

const satelliteOrbitRadius = 1.28;
const satelliteOrbitAngleStart = Math.PI / 2;
const satelliteOrbitDuration = 1.5;
let arrivalShown = false;

const satellite = new THREE.Group();
scene.add(satellite);

const satelliteFrameMaterial = new THREE.MeshStandardMaterial({
    color: 0xd1d5d8,
    metalness: 0.72,
    roughness: 0.3
});

const satelliteBodyMaterial = new THREE.MeshStandardMaterial({
    color: 0xc4a167,
    metalness: 0.6,
    roughness: 0.38
});

const satelliteBody = new THREE.Mesh(
    new THREE.BoxGeometry(0.3, 0.25, 0.23),
    satelliteBodyMaterial
);
satellite.add(satelliteBody);

const bodySidePanel = new THREE.Mesh(
    new THREE.BoxGeometry(0.035, 0.18, 0.19),
    new THREE.MeshStandardMaterial({
        color: 0x303b46,
        metalness: 0.35,
        roughness: 0.54
    })
);
bodySidePanel.position.x = -0.16;
satellite.add(bodySidePanel);

const solarPanelMaterial = new THREE.MeshStandardMaterial({
    color: 0x174b79,
    metalness: 0.38,
    roughness: 0.38,
    emissive: 0x07192a
});

const solarCellMaterial = new THREE.MeshStandardMaterial({
    color: 0x4b91bd,
    metalness: 0.28,
    roughness: 0.42,
    emissive: 0x07131e
});

const panelShadeCanvas = document.createElement("canvas");
panelShadeCanvas.width = 128;
panelShadeCanvas.height = 8;

const panelShadeContext = panelShadeCanvas.getContext("2d");
const panelShadeGradient = panelShadeContext.createLinearGradient(0, 0, 128, 0);
panelShadeGradient.addColorStop(0, "rgba(0, 3, 10, 0.88)");
panelShadeGradient.addColorStop(0.38, "rgba(0, 4, 12, 0.62)");
panelShadeGradient.addColorStop(0.76, "rgba(0, 5, 14, 0.24)");
panelShadeGradient.addColorStop(1, "rgba(0, 5, 14, 0.08)");
panelShadeContext.fillStyle = panelShadeGradient;
panelShadeContext.fillRect(0, 0, 128, 8);

const panelShadeTexture = new THREE.CanvasTexture(panelShadeCanvas);
const panelShadeMaterial = new THREE.MeshBasicMaterial({
    map: panelShadeTexture,
    transparent: true,
    depthWrite: false,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    toneMapped: false
});

const solarWings = [];

for (const wingDirection of [-1, 1]) {
    const wing = new THREE.Group();
    wing.position.y = wingDirection * 0.58;
    satellite.add(wing);
    solarWings.push(wing);

    const panel = new THREE.Mesh(
        new THREE.BoxGeometry(0.36, 0.68, 0.025),
        solarPanelMaterial
    );
    wing.add(panel);

    const panelShade = new THREE.Mesh(
        new THREE.PlaneGeometry(0.36, 0.68),
        panelShadeMaterial
    );
    panelShade.position.z = 0.027;
    wing.add(panelShade);

    for (const x of [-0.12, 0, 0.12]) {
        const cellLine = new THREE.Mesh(
            new THREE.BoxGeometry(0.006, 0.67, 0.01),
            solarCellMaterial
        );
        cellLine.position.set(x, 0, 0.018);
        wing.add(cellLine);
    }

    for (const y of [-0.25, -0.125, 0, 0.125, 0.25]) {
        const cellLine = new THREE.Mesh(
            new THREE.BoxGeometry(0.35, 0.006, 0.01),
            solarCellMaterial
        );
        cellLine.position.set(0, y, 0.018);
        wing.add(cellLine);
    }

    const boom = new THREE.Mesh(
        new THREE.BoxGeometry(0.045, 0.17, 0.045),
        satelliteFrameMaterial
    );
    boom.position.y = -wingDirection * 0.405;
    wing.add(boom);
}

const antennaArm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.018, 0.16, 12),
    satelliteFrameMaterial
);
antennaArm.rotation.z = -Math.PI / 2;
antennaArm.position.set(0.21, 0.025, 0);
satellite.add(antennaArm);

const antennaDish = new THREE.Mesh(
    new THREE.SphereGeometry(0.16, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshStandardMaterial({
        color: 0xe2e5e6,
        metalness: 0.72,
        roughness: 0.26,
        side: THREE.DoubleSide
    })
);
antennaDish.rotation.set(0, 0, -Math.PI / 2);
antennaDish.scale.set(1, 1, 0.28);
antennaDish.position.set(0.32, 0.025, 0);
satellite.add(antennaDish);

const arrivalPanel = document.getElementById("arrival-panel");
const earthContainer = document.getElementById("earth-container");
const orbitClock = new THREE.Clock();
let lastRippleTime = 0;

earthContainer.addEventListener("pointermove", (event) => {
    const now = performance.now();
    if (now - lastRippleTime < 90) return;
    lastRippleTime = now;

    const bounds = earthContainer.getBoundingClientRect();
    const ripple = document.createElement("span");
    ripple.className = "pointer-ripple";
    ripple.setAttribute("aria-hidden", "true");
    ripple.style.left = `${event.clientX - bounds.left}px`;
    ripple.style.top = `${event.clientY - bounds.top}px`;
    earthContainer.appendChild(ripple);
    ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
});


// ============================================================
// EARTH TILT
// ============================================================

earthGroup.rotation.z =
    THREE.MathUtils.degToRad(
        23.5
    );


// ============================================================
// STARS
// ============================================================

const starGeometry =
    new THREE.BufferGeometry();

const starCount = 10000;

const starPositions =
    new Float32Array(
        starCount * 3
    );


for (
    let i = 0;
    i < starCount;
    i++
) {

    const radius =
        18 +
        Math.random() * 90;

    const theta =
        Math.random() *
        Math.PI *
        2;

    const phi =
        Math.acos(
            2 *
            Math.random() -
            1
        );


    starPositions[
        i * 3
    ] =
        radius *
        Math.sin(phi) *
        Math.cos(theta);


    starPositions[
        i * 3 + 1
    ] =
        radius *
        Math.sin(phi) *
        Math.sin(theta);


    starPositions[
        i * 3 + 2
    ] =
        radius *
        Math.cos(phi);
}


starGeometry.setAttribute(
    "position",
    new THREE.BufferAttribute(
        starPositions,
        3
    )
);


const starMaterial =
    new THREE.PointsMaterial({

        color: 0xffffff,

        size: 0.025,

        transparent: true,

        opacity: 0.75,

        sizeAttenuation: true

    });


const stars =
    new THREE.Points(
        starGeometry,
        starMaterial
    );

scene.add(stars);


// ============================================================
// BACKGROUND STAR DUST
// ============================================================

const dustGeometry =
    new THREE.BufferGeometry();

const dustCount = 2500;

const dustPositions =
    new Float32Array(
        dustCount * 3
    );


for (
    let i = 0;
    i < dustCount;
    i++
) {

    dustPositions[i * 3] =
        (Math.random() - 0.5) * 60;

    dustPositions[i * 3 + 1] =
        (Math.random() - 0.5) * 60;

    dustPositions[i * 3 + 2] =
        (Math.random() - 0.5) * 60;
}


dustGeometry.setAttribute(
    "position",
    new THREE.BufferAttribute(
        dustPositions,
        3
    )
);


const dustMaterial =
    new THREE.PointsMaterial({

        color: 0x6b8295,

        size: 0.009,

        transparent: true,

        opacity: 0.45

    });


const dust =
    new THREE.Points(
        dustGeometry,
        dustMaterial
    );

scene.add(dust);


// ============================================================
// ANIMATION
// ============================================================

function animate() {

    requestAnimationFrame(
        animate
    );


    // --------------------------------------------------------
    // EARTH ROTATION
    // --------------------------------------------------------

    earth.rotation.y += 0.0011;


    // --------------------------------------------------------
    // CLOUD ROTATION
    // --------------------------------------------------------

    clouds.rotation.y += 0.00165;

    softClouds.rotation.y += 0.0018;

    const orbitProgress = Math.min(
        orbitClock.getElapsedTime() / satelliteOrbitDuration,
        1
    );
    panelShadeMaterial.opacity = 0.8 + orbitProgress * 0.2;
    const satelliteOrbitAngle = satelliteOrbitAngleStart * (1 - orbitProgress);

    satellite.position.set(
        satelliteOrbitRadius * Math.sin(satelliteOrbitAngle),
        satelliteOrbitRadius * 0.12 * Math.sin(satelliteOrbitAngle * 2),
        satelliteOrbitRadius * Math.cos(satelliteOrbitAngle)
    );
    const satelliteHeading = satelliteOrbitAngle + Math.PI / 2;
    satellite.rotation.y = satelliteHeading;
    for (const wing of solarWings) {
        wing.rotation.y = -satelliteHeading;
    }

    if (!arrivalShown && orbitProgress >= 1) {
        arrivalShown = true;
        arrivalPanel.classList.add("is-visible");
        arrivalPanel.setAttribute("aria-hidden", "false");
    }


    // --------------------------------------------------------
    // STARS
    // --------------------------------------------------------

    stars.rotation.y += 0.000015;

    dust.rotation.y += 0.000008;


    // --------------------------------------------------------
    // CONTROLS
    // --------------------------------------------------------

    controls.update();


    // --------------------------------------------------------
    // RENDER
    // --------------------------------------------------------

    renderer.render(
        scene,
        camera
    );
}


// ============================================================
// START IMMEDIATELY
// ============================================================

animate();


// ============================================================
// RESIZE
// ============================================================

window.addEventListener(
    "resize",
    () => {

        camera.aspect =
            window.innerWidth /
            window.innerHeight;

        camera.updateProjectionMatrix();

        renderer.setSize(
            window.innerWidth,
            window.innerHeight
        );

        renderer.setPixelRatio(
            Math.min(
                window.devicePixelRatio,
                2
            )
        );

    }
);