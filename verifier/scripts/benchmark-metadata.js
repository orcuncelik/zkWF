/**
 * Benchmark Metadata Script for zkWF
 *
 * Outputs a JSON object on stdout containing tooling versions,
 * compiler settings, and network configuration.
 *
 * Usage:
 *   npx hardhat run scripts/benchmark-metadata.js
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

function readPkgVersion(pkgPath) {
  try {
    return JSON.parse(fs.readFileSync(pkgPath, "utf8")).version;
  } catch (e) {
    return null;
  }
}

async function main() {
  const nm = path.join(__dirname, "..");

  const hardhatVersion  = readPkgVersion(path.join(nm, "node_modules/hardhat/package.json"));
  const ethersVersion   = readPkgVersion(path.join(nm, "node_modules/ethers/package.json"));
  const zkDeployVersion = readPkgVersion(path.join(nm, "node_modules/@matterlabs/hardhat-zksync-deploy/package.json"));
  const zkSolcVersion   = readPkgVersion(path.join(nm, "node_modules/@matterlabs/hardhat-zksync-solc/package.json"));

  const network = await hre.ethers.provider.getNetwork();

  // Hardhat normalises `solidity: { version, settings }` to `{ compilers: [{version,settings}] }`
  const solidityCfg = hre.config.solidity;
  const compiler = solidityCfg.compilers ? solidityCfg.compilers[0] : solidityCfg;

  const zksolcCfg = hre.config.zksolc || {};

  const meta = {
    tooling: {
      node_version: process.version,
      hardhat_version: hardhatVersion,
      ethers_version: ethersVersion,
      "hardhat-zksync-deploy_version": zkDeployVersion,
      "hardhat-zksync-solc_version": zkSolcVersion,
    },
    compiler_l1: {
      solc_version: compiler.version,
      optimizer_enabled: compiler.settings?.optimizer?.enabled ?? false,
      optimizer_runs: compiler.settings?.optimizer?.runs ?? 200,
      viaIR: compiler.settings?.viaIR ?? false,
    },
    compiler_l2: {
      zksolc_version: zksolcCfg.version || null,
      optimizer_enabled: zksolcCfg.settings?.optimizer?.enabled ?? false,
      optimizer_mode: zksolcCfg.settings?.optimizer?.mode || null,
    },
    l1_network: {
      name: hre.network.name,
      chain_id: Number(network.chainId),
    },
    l2_network: {
      zkSyncTestnet: { chain_id: 300 },
      zkSyncMainnet: { chain_id: 324 },
    },
  };

  console.log(JSON.stringify(meta, null, 2));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
