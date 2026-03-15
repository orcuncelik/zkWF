/**
 * L2 benchmark: deploys fresh Model per test on anvil-zksync, calls stepModel, records gas.
 *
 * Usage:
 *   PROOF_DIR=../../generator BENCHMARK_ZKSYNC_EXEC_OUT=/tmp/zk-exec.json \
 *     npx hardhat run scripts/benchmark-zksync-execution.js --network anvilZkSync
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");
const { Deployer } = require("@matterlabs/hardhat-zksync-deploy");
const { Wallet, Provider } = require("zksync-ethers");
const { loadAllowedTestIds, findProofFiles, parseProofInputs, writeResult } = require("./benchmark-utils");

async function main() {
  const proofDir = process.env.PROOF_DIR || path.join(__dirname, "../../generator");
  const outFile = process.env.BENCHMARK_ZKSYNC_EXEC_OUT;
  const allowedTestIds = loadAllowedTestIds(process.env.BENCHMARK_ZK_TESTS_FILE);

  const files = findProofFiles(proofDir, allowedTestIds);

  if (files.length === 0) {
    writeResult({ skipped: true, operations: [] }, outFile);
    return;
  }

  const provider = new Provider(hre.network.config.url);
  const privateKey = hre.network.config.accounts[0];
  const wallet = new Wallet(privateKey, provider);
  const deployer = new Deployer(hre, wallet);
  const artifact = await deployer.loadArtifact("Model");

  const operations = [];

  for (const fname of files) {
    const testId = parseInt(fname.match(/\d+/)[0], 10);
    const spData = JSON.parse(fs.readFileSync(path.join(proofDir, fname), "utf8"));

    // zkSync deployer needs string values (no BigInt serialization)
    const { initHash, sig, newHash } = parseProofInputs(spData.proof.inputs, false);
    const zkProof = { a: spData.proof.proof.a, b: spData.proof.proof.b, c: spData.proof.proof.c };
    const ciphertext = JSON.stringify(spData.state);

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
      const calldata = contract.interface.encodeFunctionData("stepModel", [newHash, ciphertext, sig, zkProof]);
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
      console.error(`  [WARN] stepModel reverted for test ${testId}: ${e.message}`);
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

    console.log(`  [exec-zksync] Test ${testId}: gas=${gasUsed}, calldata=${calldataBytes}B, reverted=${reverted}`);
  }

  writeResult({ operations }, outFile);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
