// Install with npm ci --ignore-scripts; npm verifies the package-lock integrity hashes.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const root = path.resolve(__dirname, "..");
const target = path.join(root, "public/vendor/ocr");
const copies = [
  ["tesseract.js/dist/tesseract.min.js", "tesseract.min.js"],
  ["tesseract.js/dist/worker.min.js", "worker.min.js"],
  ["tesseract.js/dist/tesseract.min.js.LICENSE.txt", "tesseract.min.js.LICENSE.txt"],
  ["tesseract.js/dist/worker.min.js.LICENSE.txt", "worker.min.js.LICENSE.txt"],
  ["tesseract.js/LICENSE.md", "TESSERACT_JS_LICENSE.md"],
  ["tesseract.js-core/LICENSE", "CORE_LICENSE"],
  ["tesseract.js-core/tesseract-core-lstm.wasm.js", "core/tesseract-core-lstm.wasm.js"],
  ["tesseract.js-core/tesseract-core-simd-lstm.wasm.js", "core/tesseract-core-simd-lstm.wasm.js"],
  ["tesseract.js-core/tesseract-core-lstm.wasm", "core/tesseract-core-lstm.wasm"],
  ["tesseract.js-core/tesseract-core-simd-lstm.wasm", "core/tesseract-core-simd-lstm.wasm"],
  ["@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz", "lang/eng.traineddata.gz"]
];
const manifest = [];
for (const [source, dest] of copies) {
  const bytes = fs.readFileSync(path.join(root, "node_modules", source));
  const file = path.join(target, dest);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, bytes);
  manifest.push({file: dest, sha256: crypto.createHash("sha256").update(bytes).digest("hex")});
}
fs.writeFileSync(path.join(target, "manifest.json"), JSON.stringify({
  packages: {
    "tesseract.js": require("../node_modules/tesseract.js/package.json").version,
    "tesseract.js-core": require("../node_modules/tesseract.js-core/package.json").version,
    "@tesseract.js-data/eng": require("../node_modules/@tesseract.js-data/eng/package.json").version
  },
  files: manifest
}, null, 2) + "\n");
console.log(`Copied and hashed ${copies.length} OCR assets.`);
