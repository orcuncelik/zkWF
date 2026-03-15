/**
 * zkSync Era Deployment Script for zkWF Model Contract
 *
 * This script deploys the Model contract (which inherits from Verifier)
 * to zkSync Era networks.
 *
 * Usage:
 *   npx hardhat deploy-zksync --script deploy-model.js --network zkSyncTestnet
 *   npx hardhat deploy-zksync --script deploy-model.js --network zkSyncMainnet
 */

const { Deployer } = require("@matterlabs/hardhat-zksync-deploy");
const { Wallet } = require("zksync-ethers");

// Initial hash values (8 uint values) - modify these for your specific BPMN model
const INITIAL_HASH = {
  a: 0,
  b: 0,
  c: 0,
  d: 0,
  e: 0,
  f: 0,
  g: 0,
  h: 0,
};

// Initial ciphertext - modify for your specific BPMN model
const INITIAL_CIPHERTEXT = "";

module.exports = async function (hre) {
  console.log("====================================");
  console.log("zkWF Model Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  // Get private key from environment
  const PRIVATE_KEY = process.env.PRIVATE_KEY;
  if (!PRIVATE_KEY) {
    throw new Error("Please set PRIVATE_KEY in your .env file");
  }

  // Initialize wallet
  const wallet = new Wallet(PRIVATE_KEY);
  console.log("Deployer address:", wallet.address);

  // Create deployer
  const deployer = new Deployer(hre, wallet);

  // Load contract artifacts
  console.log("\nLoading contract artifacts...");
  const modelArtifact = await deployer.loadArtifact("Model");

  // Estimate deployment fee
  console.log("Estimating deployment fee...");
  const deploymentFee = await deployer.estimateDeployFee(modelArtifact, [
    INITIAL_HASH,
    INITIAL_CIPHERTEXT,
  ]);
  console.log(`Estimated deployment fee: ${hre.ethers.formatEther(deploymentFee)} ETH\n`);

  // Deploy contract
  console.log("Deploying Model contract...");
  const startTime = Date.now();

  const modelContract = await deployer.deploy(modelArtifact, [
    INITIAL_HASH,
    INITIAL_CIPHERTEXT,
  ]);

  const deployTime = (Date.now() - startTime) / 1000;

  // Wait for deployment to complete
  await modelContract.waitForDeployment();

  const contractAddress = await modelContract.getAddress();
  console.log("\n====================================");
  console.log("Deployment Successful!");
  console.log("====================================");
  console.log("Contract address:", contractAddress);
  console.log("Deployment time:", deployTime.toFixed(2), "seconds");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  // Verify contract on zkSync Explorer (optional)
  if (hre.network.name !== "zkSyncLocal") {
    console.log("To verify the contract, run:");
    console.log(`npx hardhat verify --network ${hre.network.name} ${contractAddress}`);
  }

  return modelContract;
};
