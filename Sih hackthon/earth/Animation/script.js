import * as THREE from "three";


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
camera.position.set(0, 0, 3.8);


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

renderer.outputColorSpace = THREE.SRGBColorSpace;

renderer.toneMapping =
    THREE.ACESFilmicToneMapping;

renderer.toneMappingExposure = 1.15;

document
    .getElementById("earth-container")
    .appendChild(renderer.domElement);


// ============================================================
// CONTROLS
// ============================================================

// ============================================================
// LIGHTING
// ============================================================

// Strong sunlight from upper-left
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


// ============================================================
// EARTH GROUP
// ============================================================

const earthGroup = new THREE.Group();

scene.add(earthGroup);


// ============================================================
// TEXTURES
// ============================================================

const loader = new THREE.TextureLoader();
let earthTexturesReady = false;
loader.manager.onLoad = () => {
    earthTexturesReady = true;
    window.parent.postMessage(
        { type: "oceanova-earth-ready" },
        window.location.origin
    );
};


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


function createSatellite() {
    const satellite = new THREE.Group();
    const gold = new THREE.MeshStandardMaterial({ color: 0xc5a46a, metalness: 0.62, roughness: 0.4 });
    const silver = new THREE.MeshStandardMaterial({ color: 0xd8e0e3, metalness: 0.58, roughness: 0.32 });
    const panel = new THREE.MeshStandardMaterial({ color: 0x174b76, metalness: 0.38, roughness: 0.34, emissive: 0x071522, emissiveIntensity: 0.12 });
    const addBox = (size, position, material) => {
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
        mesh.position.set(...position);
        satellite.add(mesh);
        return mesh;
    };

    addBox([0.38, 0.32, 0.3], [0, 0, 0], gold);
    addBox([0.3, 0.22, 0.018], [0, 0, 0.16], silver);
    addBox([0.2, 0.025, 0.025], [0, -0.09, 0.18], gold);
    for (const side of [-1, 1]) {
        addBox([0.025, 0.28, 0.018], [side * 0.19, 0, 0.165], gold);
        addBox([0.24, 0.018, 0.018], [0, side * 0.14, 0.165], gold);
    }

    for (const direction of [-1, 1]) {
        const centerX = direction * 0.76;
        addBox([0.76, 0.42, 0.025], [centerX, 0, 0], panel);

        const grid = [];
        for (let column = 0; column <= 4; column++) {
            const x = centerX - 0.38 + column * 0.19;
            grid.push(x, -0.21, 0.016, x, 0.21, 0.016);
        }
        for (let row = 0; row <= 3; row++) {
            const y = -0.21 + row * 0.14;
            grid.push(centerX - 0.38, y, 0.016, centerX + 0.38, y, 0.016);
        }
        const gridGeometry = new THREE.BufferGeometry();
        gridGeometry.setAttribute("position", new THREE.Float32BufferAttribute(grid, 3));
        satellite.add(new THREE.LineSegments(gridGeometry, new THREE.LineBasicMaterial({ color: 0x8bbbd5 })));

        const boom = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.38, 8), silver);
        boom.rotation.z = Math.PI / 2;
        boom.position.x = direction * 0.39;
        satellite.add(boom);
    }

    const dishRadius = 0.14;
    const dishPositions = [];
    const dishIndices = [];
    const rings = 8;
    const segments = 32;
    for (let ring = 0; ring <= rings; ring++) {
        const radius = dishRadius * ring / rings;
        const depth = -0.025 * (radius / dishRadius) ** 2;
        for (let segment = 0; segment <= segments; segment++) {
            const angle = segment / segments * Math.PI * 2;
            dishPositions.push(Math.cos(angle) * radius, Math.sin(angle) * radius, depth);
        }
    }
    for (let ring = 0; ring < rings; ring++) {
        for (let segment = 0; segment < segments; segment++) {
            const current = ring * (segments + 1) + segment;
            const next = current + segments + 1;
            dishIndices.push(current, next, current + 1, current + 1, next, next + 1);
        }
    }
    const dishGeometry = new THREE.BufferGeometry();
    dishGeometry.setAttribute("position", new THREE.Float32BufferAttribute(dishPositions, 3));
    dishGeometry.setIndex(dishIndices);
    dishGeometry.computeVertexNormals();

    const dish = new THREE.Mesh(
        dishGeometry,
        new THREE.MeshStandardMaterial({ color: 0xe0e5e7, metalness: 0.36, roughness: 0.42, side: THREE.DoubleSide })
    );
    dish.rotation.y = -0.2;
    dish.position.set(-0.1, 0.27, 0.2);
    satellite.add(dish);

    const rim = new THREE.Mesh(new THREE.TorusGeometry(dishRadius, 0.01, 8, 28), silver);
    rim.rotation.y = -0.2;
    rim.position.copy(dish.position);
    satellite.add(rim);

    satellite.scale.setScalar(0.45);
    scene.add(satellite);
    return satellite;
}

const orbitingSatellite = createSatellite();


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

        opacity: 0.16,

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
            1.022,
            96,
            96
        ),

        cloudSoftMaterial

    );

earthGroup.add(softClouds);


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

let satelliteTravelStarted = null;
let satelliteCenterReported = false;
const satelliteOrbitDuration = 3600;

function animate(currentTime) {

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


    // --------------------------------------------------------
    // STARS
    // --------------------------------------------------------

    stars.rotation.y += 0.000015;

    dust.rotation.y += 0.000008;

    if (earthTexturesReady) {
        if (satelliteTravelStarted === null) satelliteTravelStarted = currentTime;
        const progress = Math.min((currentTime - satelliteTravelStarted) / satelliteOrbitDuration, 1);
        const easedProgress = progress * progress * (3 - 2 * progress);
        const angle = THREE.MathUtils.lerp(Math.PI * 1.15, Math.PI * 2, easedProgress);

        if (progress < 1) {
            orbitingSatellite.position.set(Math.sin(angle) * 1.18, 0.06, Math.cos(angle) * 1.18);
            orbitingSatellite.rotation.set(0.05, angle, Math.sin(progress * Math.PI) * 0.04);
        } else {
            orbitingSatellite.position.set(0, 0.06, 1.18);
            orbitingSatellite.rotation.set(0, 0, 0);
            if (!satelliteCenterReported) {
                satelliteCenterReported = true;
                window.parent.postMessage(
                    { type: "oceanova-satellite-centered" },
                    window.location.origin
                );
            }
        }
    }

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

requestAnimationFrame(animate);


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
            Math.min(window.devicePixelRatio, 2)
        );

    }
);