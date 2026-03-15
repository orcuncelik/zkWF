/**
 * Shared utilities for benchmark scripts.
 */

const fs = require("fs");

/**
 * Loads allowed test IDs from a JSON file (array of ints or {test_id} objects).
 * Returns null if no file specified (meaning all tests allowed).
 */
function loadAllowedTestIds(filePath) {
  if (!filePath) return null;

  try {
    const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
    const ids = new Set();

    if (Array.isArray(raw)) {
      for (const entry of raw) {
        if (typeof entry === "number" && Number.isInteger(entry)) {
          ids.add(entry);
        } else if (entry && typeof entry === "object" && Number.isInteger(entry.test_id)) {
          ids.add(entry.test_id);
        }
      }
    }

    return ids;
  } catch (e) {
    console.error(`  [WARN] Failed to read test IDs file: ${e.message}`);
    return null;
  }
}

/**
 * Finds and sorts stateProof*.json files, optionally filtered by allowed test IDs.
 */
function findProofFiles(proofDir, allowedTestIds) {
  try {
    let files = fs
      .readdirSync(proofDir)
      .filter((f) => /^stateProof\d+\.json$/.test(f))
      .sort((a, b) => {
        const na = parseInt(a.match(/\d+/)[0], 10);
        const nb = parseInt(b.match(/\d+/)[0], 10);
        return na - nb;
      });

    if (allowedTestIds !== null) {
      files = files.filter((fname) => {
        const testId = parseInt(fname.match(/\d+/)[0], 10);
        return allowedTestIds.has(testId);
      });
    }

    return files;
  } catch (e) {
    return [];
  }
}

/**
 * Parses proof inputs into initHash, signature, and newHash objects.
 * If useBigInt is true, values are converted to BigInt; otherwise kept as strings.
 */
function parseProofInputs(inputs, useBigInt = true) {
  const convert = useBigInt ? (v) => BigInt(v) : (v) => v;

  return {
    initHash: {
      a: convert(inputs[0]), b: convert(inputs[1]),
      c: convert(inputs[2]), d: convert(inputs[3]),
      e: convert(inputs[4]), f: convert(inputs[5]),
      g: convert(inputs[6]), h: convert(inputs[7]),
    },
    sig: {
      R: [convert(inputs[8]), convert(inputs[9])],
      S: convert(inputs[10]),
    },
    newHash: {
      a: convert(inputs[11]), b: convert(inputs[12]),
      c: convert(inputs[13]), d: convert(inputs[14]),
      e: convert(inputs[15]), f: convert(inputs[16]),
      g: convert(inputs[17]), h: convert(inputs[18]),
    },
  };
}

/**
 * Writes result JSON to file and stdout.
 */
function writeResult(result, outFile) {
  const outStr = JSON.stringify(result, null, 2);
  if (outFile) fs.writeFileSync(outFile, outStr);
  console.log(outStr);
}

module.exports = {
  loadAllowedTestIds,
  findProofFiles,
  parseProofInputs,
  writeResult,
};
