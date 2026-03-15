/**
 * Standard Hardhat Deployment Script for zkWF Model Contract
 *
 * This script deploys the Model contract (which inherits from Verifier)
 * to standard EVM networks (Sepolia, mainnet, localhost, etc.)
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network localhost
 *   npx hardhat run scripts/deploy.js --network sepolia
 *   npx hardhat run scripts/deploy.js --network mainnet
 */

const hre = require("hardhat");

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

async function main() {
  console.log("====================================");
  console.log("zkWF Model Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  // Get deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer address:", deployer.address);

  // Get deployer balance
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Deployer balance:", hre.ethers.formatEther(balance), "ETH\n");

  // Deploy Model contract
  console.log("Deploying Model contract...");
  const startTime = Date.now();

  const Model = await hre.ethers.getContractFactory("Model");
  const model = await Model.deploy(INITIAL_HASH, INITIAL_CIPHERTEXT);

  await model.waitForDeployment();

  const deployTime = (Date.now() - startTime) / 1000;
  const contractAddress = await model.getAddress();

  // Get deployment transaction receipt for gas info
  const deployTx = model.deploymentTransaction();
  const receipt = await deployTx.wait();

  console.log("\n====================================");
  console.log("Deployment Successful!");
  console.log("====================================");
  console.log("Contract address:", contractAddress);
  console.log("Gas used:", receipt.gasUsed.toString());
  console.log("Deployment time:", deployTime.toFixed(2), "seconds");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  // Calculate cost
  const gasPrice = receipt.gasPrice || deployTx.gasPrice;
  if (gasPrice) {
    const cost = receipt.gasUsed * gasPrice;
    console.log("Deployment cost:", hre.ethers.formatEther(cost), "ETH");
  }

  // Verify contract on Etherscan (for testnets/mainnet)
  if (hre.network.name !== "localhost" && hre.network.name !== "hardhat") {
    console.log("\nTo verify the contract on Etherscan, run:");
    console.log(`npx hardhat verify --network ${hre.network.name} ${contractAddress}`);
  }

  return model;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
