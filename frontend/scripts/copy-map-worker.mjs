import {copyFileSync, mkdirSync} from "node:fs";
import {dirname, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(projectRoot, "node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs");
const destination = resolve(projectRoot, "public/maplibre-gl-worker.mjs");

mkdirSync(dirname(destination), {recursive: true});
copyFileSync(source, destination);
console.log("MapLibre module worker copied to public/maplibre-gl-worker.mjs");
