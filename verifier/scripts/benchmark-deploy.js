/**
 * Benchmark Deployment Script for zkWF Model Contract
 *
 * Deploys Model with a blank initial hash and writes structured JSON metrics
 * to stdout and to the file specified by $BENCHMARK_DEPLOY_OUT.
 *
 * Usage (pipeline):
 *   BENCHMARK_DEPLOY_OUT=/tmp/deploy.json npx hardhat run scripts/benchmark-deploy.js
 */

const hre = require("hardhat");
const fs = require("fs");

const INITIAL_HASH = { a: 0, b: 0, c: 0, d: 0, e: 0, f: 0, g: 0, h: 0 };
const INITIAL_CIPHERTEXT = "";

async function main() {
  const network = await hre.ethers.provider.getNetwork();

  const artifact = await hre.artifacts.readArtifact("Model");
  const bytecodeSizeBytes = (artifact.bytecode.length - 2) / 2;

  const Model = await hre.ethers.getContractFactory("Model");

  const startMs = Date.now();
  const model = await Model.deploy(INITIAL_HASH, INITIAL_CIPHERTEXT);
  await model.waitForDeployment();
  const deployTimeS = parseFloat(((Date.now() - startMs) / 1000).toFixed(3));

  const contractAddress = await model.getAddress();
  const deployTx = model.deploymentTransaction();
  const receipt = await deployTx.wait();

  const block = await hre.ethers.provider.getBlock(receipt.blockNumber);
  const gasUsed = Number(receipt.gasUsed);
  const effectiveGasPrice = receipt.gasPrice ?? deployTx.gasPrice ?? 0n;
  const feePaid = BigInt(gasUsed) * BigInt(effectiveGasPrice);

  const result = {
    network: hre.network.name,
    chain_id: Number(network.chainId),
    deployment: {
      contracts: [{ name: "Model", bytecode_size_bytes: bytecodeSizeBytes }],
      contract_count: 1,
      tx_count: 1,
      contract_address: contractAddress,
      gas_used: gasUsed,
      effective_gas_price_wei: effectiveGasPrice.toString(),
      fee_paid_wei: feePaid.toString(),
      block_number: receipt.blockNumber,
      block_timestamp: block ? block.timestamp : null,
      deploy_time_s: deployTimeS,
    },
  };

  const outStr = JSON.stringify(result, null, 2);
  // Write file first so it is persisted even if stdout pipe closes early
  const outFile = process.env.BENCHMARK_DEPLOY_OUT;
  if (outFile) {
    fs.writeFileSync(outFile, outStr);
  }
  console.log(outStr);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
