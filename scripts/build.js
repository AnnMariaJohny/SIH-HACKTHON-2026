const fs = require("node:fs");
const path = require("node:path");

const projectRoot = path.resolve(__dirname, "..");
const outputDirectory = path.join(projectRoot, "dist");
const endpointVariables = {
    analysis: "OCEANOVA_ANALYSIS_URL",
    industry: "OCEANOVA_INDUSTRY_URL",
    vessel: "OCEANOVA_VESSEL_URL"
};
const localEndpoints = {
    analysis: "http://127.0.0.1:8000",
    industry: "http://127.0.0.1:5000",
    vessel: "http://127.0.0.1:5001"
};

if (process.env.VERCEL) {
    const missing = Object.values(endpointVariables).filter((name) => !process.env[name]);
    if (missing.length) {
        throw new Error(`Set these Vercel environment variables before deploying: ${missing.join(", ")}`);
    }
}

const endpoints = Object.fromEntries(
    Object.entries(endpointVariables).map(([service, variable]) => [
        service,
        (process.env[variable] || localEndpoints[service]).replace(/\/+$/, "")
    ])
);

const files = [
    ["index.html", "index.html"],
    ["Sih hackthon/welcome.html", "welcome.html"],
    ["sih-backend-main/frontend/index.html", "industry/index.html"],
    ["sih-backend-main/frontend/style.css", "industry/style.css"],
    ["sih-backend-main/frontend/script.js", "industry/script.js"],
    ["anzil/sih_backend-main/index.html", "vessel/index.html"]
];
const directories = [
    ["Sih hackthon/earth/Animation", "earth/Animation"],
    ["Sih hackthon/LOGIN/Sih-oilspil-main", "LOGIN/Sih-oilspil-main"]
];

fs.rmSync(outputDirectory, { recursive: true, force: true });
for (const [source, destination] of files) {
    const sourcePath = path.join(projectRoot, source);
    const destinationPath = path.join(outputDirectory, destination);
    fs.mkdirSync(path.dirname(destinationPath), { recursive: true });
    fs.copyFileSync(sourcePath, destinationPath);
}
for (const [source, destination] of directories) {
    fs.cpSync(
        path.join(projectRoot, source),
        path.join(outputDirectory, destination),
        {
            recursive: true,
            filter: (sourcePath) => !/[\\/](?:\.git|\.venv|__pycache__|node_modules)(?:[\\/]|$)/.test(sourcePath)
        }
    );
}

fs.writeFileSync(
    path.join(outputDirectory, "deployment-config.js"),
    `window.OCEANOVA_ENDPOINTS = Object.freeze(${JSON.stringify(endpoints)});\n`
);

console.log(`Built OCEANOVA frontend to ${outputDirectory}`);