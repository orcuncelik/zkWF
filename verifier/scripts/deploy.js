/**
 * Deploys Model contract to standard EVM networks.
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network localhost
 */

const hre = require("hardhat");

const INITIAL_HASH = { a: 0, b: 0, c: 0, d: 0, e: 0, f: 0, g: 0, h: 0 };
const INITIAL_CIPHERTEXT = "";

async function main() {
  console.log("====================================");
  console.log("zkWF Model Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer:", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "ETH\n");

  console.log("Deploying Model contract...");
  const startTime = Date.now();

  const Model = await hre.ethers.getContractFactory("Model");
  const model = await Model.deploy(INITIAL_HASH, INITIAL_CIPHERTEXT);
  await model.waitForDeployment();

  const deployTime = (Date.now() - startTime) / 1000;
  const contractAddress = await model.getAddress();
  const deployTx = model.deploymentTransaction();
  const receipt = await deployTx.wait();

  console.log("\n====================================");
  console.log("Deployment Successful!");
  console.log("====================================");
  console.log("Contract:", contractAddress);
  console.log("Gas used:", receipt.gasUsed.toString());
  console.log("Deploy time:", deployTime.toFixed(2), "s");
  console.log("====================================\n");

  const gasPrice = receipt.gasPrice || deployTx.gasPrice;
  if (gasPrice) {
    const cost = receipt.gasUsed * gasPrice;
    console.log("Cost:", hre.ethers.formatEther(cost), "ETH");
  }

  if (hre.network.name !== "localhost" && hre.network.name !== "hardhat") {
    console.log(`\nVerify: npx hardhat verify --network ${hre.network.name} ${contractAddress}`);
  }

  return model;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
