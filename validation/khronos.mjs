// Khronos glTF conformance referee. Prints the validator report as JSON to
// stdout so validation/validator.py can merge it in (check 10).
//   node validation/khronos.mjs <model.glb>
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const validator = require("gltf-validator");

const path = process.argv[2];
if (!path) {
  console.error("usage: node validation/khronos.mjs <model.glb>");
  process.exit(2);
}

const bytes = new Uint8Array(readFileSync(path));
validator
  .validateBytes(bytes, { maxIssues: 100 })
  .then((report) => {
    process.stdout.write(JSON.stringify(report));
  })
  .catch((err) => {
    console.error("validator error:", err);
    process.exit(1);
  });
