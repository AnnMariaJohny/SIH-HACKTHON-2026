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

const controls = new OrbitControls(
    camera,
    renderer.domElement
);

controls.enableDamping = true;

controls.dampingFactor = 0.035;

controls.enablePan = false;

controls.minDistance = 2.0;

controls.maxDistance = 7.0;


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