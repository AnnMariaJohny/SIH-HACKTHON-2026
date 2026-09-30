const fs = require("node:fs");
const path = require("node:path");

const projectRoot = path.resolve(__dirname, "..");
const outputDirectory = path.join(projectRoot, "dist");
const localEndpoints = {
    analysis: "http://127.0.0.1:8000",
    industry: "http://127.0.0.1:8000/industry-api",
    vessel: "http://127.0.0.1:8000/vessel-api"
};

const endpoints = process.env.VERCEL
    ? "Object.freeze({analysis:window.location.origin,industry:window.location.origin,vessel:window.location.origin})"
    : `Object.freeze(${JSON.stringify(localEndpoints)})`;

const files = [
    ["index.html", "analysis/index.html"],
    ["Sih hackthon/welcome.html", "index.html"],
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
    `window.OCEANOVA_ENDPOINTS = ${endpoints};\n`
);

console.log(`Built OCEANOVA frontend to ${outputDirectory}`);