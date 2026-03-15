/**
 * Deploys Model contract to zkSync Era networks.
 *
 * Usage:
 *   npx hardhat deploy-zksync --script deploy-model.js --network zkSyncTestnet
 */

const { Deployer } = require("@matterlabs/hardhat-zksync-deploy");
const { Wallet } = require("zksync-ethers");

const INITIAL_HASH = { a: 0, b: 0, c: 0, d: 0, e: 0, f: 0, g: 0, h: 0 };
const INITIAL_CIPHERTEXT = "";

module.exports = async function (hre) {
  console.log("====================================");
  console.log("zkWF Model Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  const PRIVATE_KEY = process.env.PRIVATE_KEY;
  if (!PRIVATE_KEY) {
    throw new Error("Please set PRIVATE_KEY in your .env file");
  }

  const wallet = new Wallet(PRIVATE_KEY);
  console.log("Deployer:", wallet.address);

  const deployer = new Deployer(hre, wallet);
  const modelArtifact = await deployer.loadArtifact("Model");

  const deploymentFee = await deployer.estimateDeployFee(modelArtifact, [
    INITIAL_HASH,
    INITIAL_CIPHERTEXT,
  ]);
  console.log(`Estimated fee: ${hre.ethers.formatEther(deploymentFee)} ETH\n`);

  console.log("Deploying Model contract...");
  const startTime = Date.now();

  const modelContract = await deployer.deploy(modelArtifact, [
    INITIAL_HASH,
    INITIAL_CIPHERTEXT,
  ]);
  await modelContract.waitForDeployment();

  const deployTime = (Date.now() - startTime) / 1000;
  const contractAddress = await modelContract.getAddress();

  console.log("\n====================================");
  console.log("Deployment Successful!");
  console.log("====================================");
  console.log("Contract:", contractAddress);
  console.log("Deploy time:", deployTime.toFixed(2), "s");
  console.log("====================================\n");

  if (hre.network.name !== "zkSyncLocal") {
    console.log(`Verify: npx hardhat verify --network ${hre.network.name} ${contractAddress}`);
  }

  return modelContract;
};
