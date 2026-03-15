/**
 * Benchmark Execution Script for zkWF on anvil-zksync
 *
 * For each current-run stateProof<N>.json in $PROOF_DIR:
 *   1. Deploys a fresh Model contract with initHash = proof.inputs[0..7]
 *   2. Calls stepModel(newHash, ciphertext, sig, zkProof)
 *   3. Records real gas_used from the local zkSync node
 *
 * Writes JSON to stdout and to $BENCHMARK_ZKSYNC_EXEC_OUT.
 *
 * Usage (pipeline):
 *   PROOF_DIR=../../generator BENCHMARK_ZKSYNC_EXEC_OUT=/tmp/zk-exec.json \
 *   BENCHMARK_ZK_TESTS_FILE=/tmp/zktests.json \
 *     npx hardhat run scripts/benchmark-zksync-execution.js --network anvilZkSync
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");
const { Deployer } = require("@matterlabs/hardhat-zksync-deploy");
const { Wallet, Provider } = require("zksync-ethers");

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
  const proofDir =
    process.env.PROOF_DIR || path.join(__dirname, "../../generator");
  const outFile = process.env.BENCHMARK_ZKSYNC_EXEC_OUT;
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

  // Set up zkSync wallet and deployer (must use zksync-ethers Provider for gas compatibility)
  const provider = new Provider(hre.network.config.url);
  const privateKey = hre.network.config.accounts[0];
  const wallet = new Wallet(privateKey, provider);
  const deployer = new Deployer(hre, wallet);
  const artifact = await deployer.loadArtifact("Model");

  const operations = [];

  for (const fname of files) {
    const testId = parseInt(fname.match(/\d+/)[0], 10);
    const spData = JSON.parse(
      fs.readFileSync(path.join(proofDir, fname), "utf8")
    );

    const inputs = spData.proof.inputs;
    const proofData = spData.proof.proof;
    const stateObj = spData.state;

    // inputs[0..7] -> initHash (use strings to avoid BigInt serialization issues in deployer)
    const initHash = {
      a: inputs[0],
      b: inputs[1],
      c: inputs[2],
      d: inputs[3],
      e: inputs[4],
      f: inputs[5],
      g: inputs[6],
      h: inputs[7],
    };

    // inputs[8..10] -> signature
    const sig = {
      R: [inputs[8], inputs[9]],
      S: inputs[10],
    };

    // inputs[11..18] -> newHash
    const newHash = {
      a: inputs[11],
      b: inputs[12],
      c: inputs[13],
      d: inputs[14],
      e: inputs[15],
      f: inputs[16],
      g: inputs[17],
      h: inputs[18],
    };

    const zkProof = { a: proofData.a, b: proofData.b, c: proofData.c };
    const ciphertext = JSON.stringify(stateObj);

    // Deploy a fresh contract initialised with this proof's initial hash
    const contract = await deployer.deploy(artifact, [initHash, ""]);
    await contract.waitForDeployment();

    let reverted = false;
    let gasUsed = 0;
    let effectiveGasPriceWei = "0";
    let feePaidWei = "0";
    let calldataBytes = 0;
    let calldataHex = null;
    let txTo = null;

    try {
      // Encode calldata before sending (for mainnet fee estimation)
      const calldata = contract.interface.encodeFunctionData("stepModel", [
        newHash,
        ciphertext,
        sig,
        zkProof,
      ]);
      calldataBytes = (calldata.length - 2) / 2;
      calldataHex = calldata;
      txTo = await contract.getAddress();

      const tx = await contract.stepModel(newHash, ciphertext, sig, zkProof);
      const receipt = await tx.wait();

      gasUsed = Number(receipt.gasUsed);
      const effectiveGasPrice = receipt.gasPrice ?? tx.gasPrice ?? 0n;
      const feePaid = BigInt(gasUsed) * BigInt(effectiveGasPrice);
      effectiveGasPriceWei = effectiveGasPrice.toString();
      feePaidWei = feePaid.toString();
    } catch (e) {
      reverted = true;
      console.error(
        `  [WARN] stepModel reverted for test ${testId}: ${e.message}`
      );
    }

    operations.push({
      op: "stepModel",
      test_id: testId,
      gas_used: gasUsed,
      effective_gas_price_wei: effectiveGasPriceWei,
      fee_paid_wei: feePaidWei,
      calldata_bytes: calldataBytes,
      calldata_hex: calldataHex,
      tx_to: txTo,
      reverted,
    });

    console.log(
      `  [exec-zksync] Test ${testId}: gas=${gasUsed}, calldata=${calldataBytes}B, reverted=${reverted}`
    );
  }

  const result = { operations };
  const outStr = JSON.stringify(result, null, 2);
  if (outFile) fs.writeFileSync(outFile, outStr);
  console.log(outStr);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
