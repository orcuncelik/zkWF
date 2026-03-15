/**
 * Benchmark Execution Script for zkWF (Phase 6.5)
 *
 * For each current-run stateProof<N>.json in $PROOF_DIR:
 *   1. Deploys a fresh Model contract with initHash = proof.inputs[0..7]
 *   2. Calls stepModel(newHash, ciphertext, sig, zkProof)
 *   3. Records gas_used, effective_gas_price_wei, fee_paid_wei, calldata_bytes
 *
 * Writes JSON to stdout and to $BENCHMARK_EXEC_OUT.
 *
 * Usage (pipeline):
 *   PROOF_DIR=../../generator BENCHMARK_EXEC_OUT=/tmp/exec.json \
 *   BENCHMARK_ZK_TESTS_FILE=/tmp/zktests.json \
 *     npx hardhat run scripts/benchmark-execution.js
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

function loadAllowedTestIds(filePath) {
  if (!filePath) {
    return null;
  }

  try {
    const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
    const ids = new Set();

    if (Array.isArray(raw)) {
      for (const entry of raw) {
        if (typeof entry === "number" && Number.isInteger(entry)) {
          ids.add(entry);
        } else if (
          entry &&
          typeof entry === "object" &&
          Number.isInteger(entry.test_id)
        ) {
          ids.add(entry.test_id);
        }
      }
    }

    return ids;
  } catch (e) {
    console.error(`  [WARN] Failed to read BENCHMARK_ZK_TESTS_FILE: ${e.message}`);
    return null;
  }
}

async function main() {
  const proofDir = process.env.PROOF_DIR || path.join(__dirname, "../../generator");
  const outFile = process.env.BENCHMARK_EXEC_OUT;
  const allowedTestIds = loadAllowedTestIds(process.env.BENCHMARK_ZK_TESTS_FILE);

  // Find and sort stateProof files by numeric ID
  let files = [];
  try {
    files = fs
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
  } catch (e) {
    // directory missing or unreadable
  }

  if (files.length === 0) {
    const result = { skipped: true, operations: [] };
    const outStr = JSON.stringify(result, null, 2);
    if (outFile) fs.writeFileSync(outFile, outStr);
    console.log(outStr);
    return;
  }

  const Model = await hre.ethers.getContractFactory("Model");
  const operations = [];

  for (const fname of files) {
    const testId = parseInt(fname.match(/\d+/)[0], 10);
    const spData = JSON.parse(fs.readFileSync(path.join(proofDir, fname), "utf8"));

    // stateProof structure: { proof: { inputs: [...], proof: { a, b, c } }, state: {...} }
    const inputs = spData.proof.inputs;
    const proofData = spData.proof.proof;
    const stateObj = spData.state;

    // inputs[0..7] → initHash (current state hash = constructor argument)
    const initHash = {
      a: BigInt(inputs[0]),
      b: BigInt(inputs[1]),
      c: BigInt(inputs[2]),
      d: BigInt(inputs[3]),
      e: BigInt(inputs[4]),
      f: BigInt(inputs[5]),
      g: BigInt(inputs[6]),
      h: BigInt(inputs[7]),
    };

    // inputs[8..10] → signature
    const sig = {
      R: [BigInt(inputs[8]), BigInt(inputs[9])],
      S: BigInt(inputs[10]),
    };

    // inputs[11..18] → newHash
    const newHash = {
      a: BigInt(inputs[11]),
      b: BigInt(inputs[12]),
      c: BigInt(inputs[13]),
      d: BigInt(inputs[14]),
      e: BigInt(inputs[15]),
      f: BigInt(inputs[16]),
      g: BigInt(inputs[17]),
      h: BigInt(inputs[18]),
    };

    // ZK proof struct
    const zkProof = { a: proofData.a, b: proofData.b, c: proofData.c };

    // Ciphertext: deterministic JSON serialisation of the state object
    const ciphertext = JSON.stringify(stateObj);

    // Deploy a fresh contract initialised with this proof's initial hash
    const model = await Model.deploy(initHash, "");
    await model.waitForDeployment();

    let reverted = false;
    let gasUsed = 0;
    let effectiveGasPriceWei = "0";
    let feePaidWei = "0";
    let calldataBytes = 0;

    try {
      const tx = await model.stepModel(newHash, ciphertext, sig, zkProof);
      const receipt = await tx.wait();

      gasUsed = Number(receipt.gasUsed);
      const effectiveGasPrice = receipt.gasPrice ?? tx.gasPrice ?? 0n;
      const feePaid = BigInt(gasUsed) * BigInt(effectiveGasPrice);
      effectiveGasPriceWei = effectiveGasPrice.toString();
      feePaidWei = feePaid.toString();

      // Measure calldata size
      const calldata = model.interface.encodeFunctionData("stepModel", [
        newHash,
        ciphertext,
        sig,
        zkProof,
      ]);
      calldataBytes = (calldata.length - 2) / 2;
    } catch (e) {
      reverted = true;
      console.error(`  [WARN] stepModel reverted for test ${testId}: ${e.message}`);
    }

    operations.push({
      op: "stepModel",
      test_id: testId,
      gas_used: gasUsed,
      effective_gas_price_wei: effectiveGasPriceWei,
      fee_paid_wei: feePaidWei,
      calldata_bytes: calldataBytes,
      reverted,
    });

    console.log(
      `  [exec] Test ${testId}: gas=${gasUsed}, calldata=${calldataBytes}B, reverted=${reverted}`
    );
  }

  const result = { operations };
  const outStr = JSON.stringify(result, null, 2);
  // Write file first so it is persisted even if stdout pipe closes early
  if (outFile) fs.writeFileSync(outFile, outStr);
  console.log(outStr);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
