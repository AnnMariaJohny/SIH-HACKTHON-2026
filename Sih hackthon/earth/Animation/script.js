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
    
    // Materials
    const goldFoil = new THREE.MeshStandardMaterial({ 
        color: 0xffb700, 
        metalness: 0.8, 
        roughness: 0.35, 
        bumpScale: 0.02
    });
    
    // Create a procedural bump map for the gold foil
    const canvas = document.createElement('canvas');
    canvas.width = 256; canvas.height = 256;
    const ctx = canvas.getContext('2d');
    for(let i = 0; i < 256; i++) {
        for(let j = 0; j < 256; j++) {
            const val = Math.floor(Math.random() * 255);
            ctx.fillStyle = `rgb(${val},${val},${val})`;
            ctx.fillRect(i, j, 1, 1);
        }
    }
    const foilTex = new THREE.CanvasTexture(canvas);
    foilTex.wrapS = THREE.RepeatWrapping;
    foilTex.wrapT = THREE.RepeatWrapping;
    foilTex.repeat.set(4, 4);
    goldFoil.bumpMap = foilTex;

    const silver = new THREE.MeshStandardMaterial({ color: 0xe0e5e9, metalness: 0.9, roughness: 0.2 });
    const darkMetal = new THREE.MeshStandardMaterial({ color: 0x333333, metalness: 0.7, roughness: 0.5 });
    
    const panelMaterial = new THREE.MeshStandardMaterial({ 
        color: 0x0a1d3a, 
        metalness: 0.6, 
        roughness: 0.1, 
        emissive: 0x051020, 
        emissiveIntensity: 0.2 
    });

    const addMesh = (geom, mat, pos, rot = [0,0,0]) => {
        const mesh = new THREE.Mesh(geom, mat);
        mesh.position.set(...pos);
        mesh.rotation.set(...rot);
        satellite.add(mesh);
        return mesh;
    };

    // Main Body (Hexagonal Cylinder)
    addMesh(new THREE.CylinderGeometry(0.25, 0.25, 0.5, 6), goldFoil, [0, 0, 0], [Math.PI/2, Math.PI/2, 0]);
    
    // End caps
    addMesh(new THREE.CylinderGeometry(0.22, 0.22, 0.52, 6), darkMetal, [0, 0, 0], [Math.PI/2, Math.PI/2, 0]);

    // Antennas & Instruments on body
    addMesh(new THREE.BoxGeometry(0.1, 0.1, 0.1), silver, [0, 0.2, 0.15]);
    addMesh(new THREE.CylinderGeometry(0.02, 0.02, 0.2, 8), silver, [0, 0.3, 0.15]); // Top antenna
    addMesh(new THREE.CylinderGeometry(0.04, 0.08, 0.15, 8), darkMetal, [-0.15, 0.15, 0.2], [0, 0, Math.PI/4]); // Star tracker
    addMesh(new THREE.CylinderGeometry(0.04, 0.08, 0.15, 8), darkMetal, [0.15, 0.15, 0.2], [0, 0, -Math.PI/4]); // Star tracker

    // Huge Solar Panels
    for (const direction of [-1, 1]) {
        // Boom
        addMesh(new THREE.CylinderGeometry(0.015, 0.015, 0.4, 8), silver, [direction * 0.4, 0, 0], [0, 0, Math.PI / 2]);

        // Panel Base
        const panelGroup = new THREE.Group();
        panelGroup.position.set(direction * 1.05, 0, 0);
        
        // 3 segments of solar panels
        for (let seg = -1; seg <= 1; seg++) {
            const segX = seg * 0.42;
            const pMesh = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.6, 0.02), panelMaterial);
            pMesh.position.set(segX, 0, 0);
            panelGroup.add(pMesh);
            
            // Grid lines on panel
            const grid = [];
            for (let column = -3; column <= 3; column++) {
                const x = segX + column * (0.4/7);
                grid.push(x, -0.3, 0.012, x, 0.3, 0.012);
            }
            for (let row = -5; row <= 5; row++) {
                const y = row * (0.6/11);
                grid.push(segX - 0.2, y, 0.012, segX + 0.2, y, 0.012);
            }
            const gridGeom = new THREE.BufferGeometry();
            gridGeom.setAttribute("position", new THREE.Float32BufferAttribute(grid, 3));
            panelGroup.add(new THREE.LineSegments(gridGeom, new THREE.LineBasicMaterial({ color: 0x8bbbd5, transparent: true, opacity: 0.5 })));
        }
        
        satellite.add(panelGroup);
    }

    // Main Dish Antenna (Communication)
    const dishRadius = 0.22;
    const dishPositions = [];
    const dishIndices = [];
    const rings = 12;
    const segments = 48;
    for (let ring = 0; ring <= rings; ring++) {
        const radius = dishRadius * ring / rings;
        const depth = -0.06 * (radius / dishRadius) ** 2;
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

    const dishGroup = new THREE.Group();
    dishGroup.position.set(0, -0.2, 0.25);
    dishGroup.rotation.set(-0.4, 0, 0);

    const dishMesh = new THREE.Mesh(dishGeometry, new THREE.MeshStandardMaterial({ color: 0xf0f5f9, metalness: 0.2, roughness: 0.5, side: THREE.DoubleSide }));
    dishGroup.add(dishMesh);
    
    // Dish feed horn
    const feedHorn = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.02, 0.15, 8), darkMetal);
    feedHorn.position.set(0, 0, 0.075);
    feedHorn.rotation.set(Math.PI/2, 0, 0);
    dishGroup.add(feedHorn);

    // Feed horn supports
    for(let i=0; i<3; i++) {
        const angle = i * Math.PI * 2 / 3;
        const support = new THREE.Mesh(new THREE.CylinderGeometry(0.002, 0.002, 0.18), silver);
        support.position.set(Math.cos(angle) * 0.05, Math.sin(angle) * 0.05, 0.035);
        support.lookAt(0,0,0.15);
        dishGroup.add(support);
    }

    satellite.add(dishGroup);

    satellite.scale.setScalar(0.35);
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