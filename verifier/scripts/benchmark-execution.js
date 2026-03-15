/**
 * L1 benchmark: deploys fresh Model per test, calls stepModel, records gas metrics.
 *
 * Usage:
 *   PROOF_DIR=../../generator BENCHMARK_EXEC_OUT=/tmp/exec.json \
 *     npx hardhat run scripts/benchmark-execution.js
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");
const { loadAllowedTestIds, findProofFiles, parseProofInputs, writeResult } = require("./benchmark-utils");

async function main() {
  const proofDir = process.env.PROOF_DIR || path.join(__dirname, "../../generator");
  const outFile = process.env.BENCHMARK_EXEC_OUT;
  const allowedTestIds = loadAllowedTestIds(process.env.BENCHMARK_ZK_TESTS_FILE);

  const files = findProofFiles(proofDir, allowedTestIds);

  if (files.length === 0) {
    writeResult({ skipped: true, operations: [] }, outFile);
    return;
  }

  const Model = await hre.ethers.getContractFactory("Model");
  const operations = [];

  for (const fname of files) {
    const testId = parseInt(fname.match(/\d+/)[0], 10);
    const spData = JSON.parse(fs.readFileSync(path.join(proofDir, fname), "utf8"));

    const { initHash, sig, newHash } = parseProofInputs(spData.proof.inputs, true);
    const zkProof = { a: spData.proof.proof.a, b: spData.proof.proof.b, c: spData.proof.proof.c };
    const ciphertext = JSON.stringify(spData.state);

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

      const calldata = model.interface.encodeFunctionData("stepModel", [newHash, ciphertext, sig, zkProof]);
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

    console.log(`  [exec] Test ${testId}: gas=${gasUsed}, calldata=${calldataBytes}B, reverted=${reverted}`);
  }

  writeResult({ operations }, outFile);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
