/**
 * Benchmark Deployment Script for zkWF Model Contract on anvil-zksync
 *
 * Deploys Model with a blank initial hash to a local anvil-zksync node
 * and writes structured JSON metrics with real measured gas values.
 *
 * Usage (pipeline):
 *   BENCHMARK_ZKSYNC_DEPLOY_OUT=/tmp/zk-deploy.json \
 *     npx hardhat run scripts/benchmark-zksync-deploy.js --network anvilZkSync
 */

const hre = require("hardhat");
const fs = require("fs");
const { Deployer } = require("@matterlabs/hardhat-zksync-deploy");
const { Wallet, Provider } = require("zksync-ethers");

const INITIAL_HASH = { a: 0, b: 0, c: 0, d: 0, e: 0, f: 0, g: 0, h: 0 };
const INITIAL_CIPHERTEXT = "";

async function main() {
  const network = hre.network.name;
  const provider = new Provider(hre.network.config.url);
  const chainId = Number((await provider.getNetwork()).chainId);

  // Use the rich wallet private key from the network config
  const privateKey = hre.network.config.accounts[0];
  const wallet = new Wallet(privateKey, provider);

  const deployer = new Deployer(hre, wallet);

  // Load zkSync artifact
  const artifact = await deployer.loadArtifact("Model");
  const bytecodeSizeBytes = artifact.bytecode
    ? (artifact.bytecode.length - 2) / 2
    : 0;

  const balanceBefore = await provider.getBalance(wallet.address);

  const startMs = Date.now();
  const contract = await deployer.deploy(artifact, [
    INITIAL_HASH,
    INITIAL_CIPHERTEXT,
  ]);
  await contract.waitForDeployment();
  const deployTimeS = parseFloat(((Date.now() - startMs) / 1000).toFixed(3));

  const contractAddress = await contract.getAddress();
  const balanceAfter = await provider.getBalance(wallet.address);
  const feePaid = balanceBefore - balanceAfter;

  // Get deployment transaction receipt for gas details
  const deployTx = contract.deploymentTransaction();
  let gasUsed = 0;
  let effectiveGasPrice = 0n;
  let blockNumber = 0;
  let blockTimestamp = null;

  if (deployTx) {
    const receipt = await deployTx.wait();
    gasUsed = Number(receipt.gasUsed);
    effectiveGasPrice = receipt.gasPrice ?? deployTx.gasPrice ?? 0n;
    blockNumber = receipt.blockNumber;
    try {
      const block = await provider.getBlock(receipt.blockNumber);
      blockTimestamp = block ? block.timestamp : null;
    } catch (_) {
      // anvil-zksync may not support all block fields
    }
  }

  // Capture raw deploy tx data for mainnet fee estimation (zks_estimateFee)
  let deployTxData = null;
  let deployTxTo = null;
  if (deployTx) {
    deployTxData = deployTx.data || null;
    deployTxTo = deployTx.to || null;
  }

  const result = {
    network,
    chain_id: chainId,
    deployment: {
      contracts: [{ name: "Model", bytecode_size_bytes: bytecodeSizeBytes }],
      contract_count: 1,
      tx_count: 1,
      contract_address: contractAddress,
      gas_used: gasUsed,
      effective_gas_price_wei: effectiveGasPrice.toString(),
      fee_paid_wei: feePaid.toString(),
      block_number: blockNumber,
      block_timestamp: blockTimestamp,
      deploy_time_s: deployTimeS,
      deploy_tx_data: deployTxData,
      deploy_tx_to: deployTxTo,
    },
  };

  const outStr = JSON.stringify(result, null, 2);
  const outFile = process.env.BENCHMARK_ZKSYNC_DEPLOY_OUT;
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
