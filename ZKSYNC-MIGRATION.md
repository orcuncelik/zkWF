# zkSync Era Migration Changelog

This document details all changes made to enable zkSync Era deployment for zkWF while maintaining backward compatibility with Ethereum/Truffle.

---

## Summary of Changes

| Category | Files Changed | Files Created |
|----------|---------------|---------------|
| Configuration | 2 | 2 |
| Smart Contracts | 2 | 0 |
| Deployment Scripts | 0 | 2 |
| Documentation | 1 | 1 |

**Total: 4 files modified, 5 files created**

---

## Files Created

### 1. `verifier/hardhat.config.js`

New Hardhat configuration with zkSync Era support.

```javascript
require("@nomicfoundation/hardhat-toolbox");
require("@matterlabs/hardhat-zksync-deploy");
require("@matterlabs/hardhat-zksync-solc");
require("@matterlabs/hardhat-zksync-verify");

const dotenv = require("dotenv");
dotenv.config();

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x0000000000000000000000000000000000000000000000000000000000000001";
const INFURA_PROJECT_ID = process.env.INFURA_PROJECT_ID || "";

module.exports = {
  defaultNetwork: "hardhat",

  networks: {
    // Local development
    hardhat: {
      chainId: 31337,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,
    },

    // Ethereum networks
    sepolia: {
      url: `https://sepolia.infura.io/v3/${INFURA_PROJECT_ID}`,
      accounts: [PRIVATE_KEY],
      chainId: 11155111,
    },
    mainnet: {
      url: `https://mainnet.infura.io/v3/${INFURA_PROJECT_ID}`,
      accounts: [PRIVATE_KEY],
      chainId: 1,
    },

    // zkSync Era networks
    zkSyncMainnet: {
      url: "https://mainnet.era.zksync.io",
      ethNetwork: "mainnet",
      zksync: true,
      verifyURL: "https://zksync2-mainnet-explorer.zksync.io/contract_verification",
      accounts: [PRIVATE_KEY],
    },
    zkSyncTestnet: {
      url: "https://sepolia.era.zksync.dev",
      ethNetwork: "sepolia",
      zksync: true,
      verifyURL: "https://explorer.sepolia.era.zksync.dev/contract_verification",
      accounts: [PRIVATE_KEY],
    },
    zkSyncLocal: {
      url: "http://localhost:3050",
      ethNetwork: "http://localhost:8545",
      zksync: true,
      accounts: [PRIVATE_KEY],
    },
  },

  solidity: {
    version: "0.8.0",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },

  zksolc: {
    version: "1.5.0",
    settings: {
      optimizer: {
        enabled: true,
        mode: "3",
      },
    },
  },

  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache-hardhat",
    artifacts: "./artifacts-hardhat",
    zksync: {
      artifacts: "./artifacts-zk",
      cache: "./cache-zk",
    },
  },

  etherscan: {
    apiKey: {
      sepolia: process.env.ETHERSCAN_API_KEY || "",
      mainnet: process.env.ETHERSCAN_API_KEY || "",
    },
  },
};
```

---

### 2. `verifier/deploy/deploy-model.js`

zkSync Era deployment script using Matter Labs deployer.

```javascript
const { Deployer } = require("@matterlabs/hardhat-zksync-deploy");
const { Wallet } = require("zksync-ethers");

const INITIAL_HASH = {
  a: 0, b: 0, c: 0, d: 0, e: 0, f: 0, g: 0, h: 0,
};
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
  console.log("Deployer address:", wallet.address);

  const deployer = new Deployer(hre, wallet);

  console.log("\nLoading contract artifacts...");
  const modelArtifact = await deployer.loadArtifact("Model");

  console.log("Estimating deployment fee...");
  const deploymentFee = await deployer.estimateDeployFee(modelArtifact, [
    INITIAL_HASH,
    INITIAL_CIPHERTEXT,
  ]);
  console.log(`Estimated deployment fee: ${hre.ethers.formatEther(deploymentFee)} ETH\n`);

  console.log("Deploying Model contract...");
  const startTime = Date.now();

  const modelContract = await deployer.deploy(modelArtifact, [
    INITIAL_HASH,
    INITIAL_CIPHERTEXT,
  ]);

  const deployTime = (Date.now() - startTime) / 1000;
  await modelContract.waitForDeployment();

  const contractAddress = await modelContract.getAddress();
  console.log("\n====================================");
  console.log("Deployment Successful!");
  console.log("====================================");
  console.log("Contract address:", contractAddress);
  console.log("Deployment time:", deployTime.toFixed(2), "seconds");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  if (hre.network.name !== "zkSyncLocal") {
    console.log("To verify the contract, run:");
    console.log(`npx hardhat verify --network ${hre.network.name} ${contractAddress}`);
  }

  return modelContract;
};
```

---

### 3. `verifier/scripts/deploy.js`

Standard Hardhat deployment script for Ethereum networks.

```javascript
const hre = require("hardhat");

const INITIAL_HASH = {
  a: 0, b: 0, c: 0, d: 0, e: 0, f: 0, g: 0, h: 0,
};
const INITIAL_CIPHERTEXT = "";

async function main() {
  console.log("====================================");
  console.log("zkWF Model Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer address:", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Deployer balance:", hre.ethers.formatEther(balance), "ETH\n");

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
  console.log("Contract address:", contractAddress);
  console.log("Gas used:", receipt.gasUsed.toString());
  console.log("Deployment time:", deployTime.toFixed(2), "seconds");
  console.log("Network:", hre.network.name);
  console.log("====================================\n");

  const gasPrice = receipt.gasPrice || deployTx.gasPrice;
  if (gasPrice) {
    const cost = receipt.gasUsed * gasPrice;
    console.log("Deployment cost:", hre.ethers.formatEther(cost), "ETH");
  }

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
```

---

### 4. `verifier/scripts/estimate-gas.js`

Gas estimation and comparison script.

```javascript
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const GAS_PRICES = {
  ganache: 3,
  sepolia: 20,
  mainnet: 30,
  zkSyncTestnet: 0.25,
  zkSyncMainnet: 0.25,
};

const ETH_PRICE_USD = 2500;

async function main() {
  console.log("====================================");
  console.log("zkWF Gas Estimation Report");
  console.log("====================================\n");

  const hardhatArtifactPath = path.join(__dirname, "../artifacts-hardhat/contracts/model.sol/Model.json");
  const zkArtifactPath = path.join(__dirname, "../artifacts-hardhat-zk/contracts/model.sol/Model.json");

  let hardhatBytecode = null;
  let zkBytecode = null;

  if (fs.existsSync(hardhatArtifactPath)) {
    const artifact = JSON.parse(fs.readFileSync(hardhatArtifactPath, "utf8"));
    hardhatBytecode = artifact.bytecode;
    console.log("Hardhat artifact found");
  }

  if (fs.existsSync(zkArtifactPath)) {
    const artifact = JSON.parse(fs.readFileSync(zkArtifactPath, "utf8"));
    zkBytecode = artifact.bytecode;
    console.log("zkSync artifact found");
  }

  console.log("\n====================================");
  console.log("Bytecode Size Comparison");
  console.log("====================================\n");

  if (hardhatBytecode) {
    const sizeBytes = (hardhatBytecode.length - 2) / 2;
    console.log(`Ethereum (solc):     ${sizeBytes.toLocaleString()} bytes`);
  }

  if (zkBytecode) {
    const sizeBytes = (zkBytecode.length - 2) / 2;
    console.log(`zkSync Era (zksolc): ${sizeBytes.toLocaleString()} bytes`);
  }

  // ... (rest of estimation logic)
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
```

---

### 5. `verifier/.env.example`

Environment variables template.

```bash
# zkWF Verifier Environment Variables
# Copy this file to .env and fill in your values
# NEVER commit .env to version control!

# Private key for deployment (without 0x prefix)
PRIVATE_KEY=your_private_key_here

# Infura Project ID (for Ethereum networks)
INFURA_PROJECT_ID=your_infura_project_id

# Etherscan API Key (for contract verification)
ETHERSCAN_API_KEY=your_etherscan_api_key
```

---

## Files Modified

### 1. `verifier/package.json`

**Before:**
```json
{
  "name": "verifier",
  "version": "1.0.0",
  "main": "truffle-config.js",
  "scripts": {
    "test": "echo \"Error: no test specified\" && exit 1"
  },
  "dependencies": {
    "@truffle/hdwallet-provider": "^2.1.15",
    "truffle": "^5.11.5"
  }
}
```

**After:**
```json
{
  "name": "zkwf-verifier",
  "version": "1.0.0",
  "description": "zkWF Smart Contract Verifier - Supports Truffle, Hardhat, and zkSync Era",
  "main": "truffle-config.js",
  "scripts": {
    "test": "npx hardhat test",
    "compile:truffle": "npx truffle compile",
    "compile:hardhat": "npx hardhat compile",
    "compile:zksync": "npx hardhat compile --network zkSyncTestnet",
    "deploy:ganache": "npx truffle migrate --network development",
    "deploy:localhost": "npx hardhat run scripts/deploy.js --network localhost",
    "deploy:sepolia": "npx hardhat run scripts/deploy.js --network sepolia",
    "deploy:mainnet": "npx hardhat run scripts/deploy.js --network mainnet",
    "deploy:zksync-testnet": "npx hardhat deploy-zksync --script deploy-model.js --network zkSyncTestnet",
    "deploy:zksync-mainnet": "npx hardhat deploy-zksync --script deploy-model.js --network zkSyncMainnet",
    "ganache": "npx ganache --port 8545",
    "clean": "rm -rf cache cache-hardhat cache-zk artifacts artifacts-hardhat artifacts-zk build"
  },
  "dependencies": {
    "@truffle/hdwallet-provider": "^2.1.15",
    "truffle": "^5.11.5"
  },
  "devDependencies": {
    "@nomicfoundation/hardhat-toolbox": "^4.0.0",
    "@matterlabs/hardhat-zksync-deploy": "^1.1.2",
    "@matterlabs/hardhat-zksync-solc": "^1.0.6",
    "@matterlabs/hardhat-zksync-verify": "^1.2.2",
    "dotenv": "^16.3.1",
    "ethers": "^6.9.0",
    "hardhat": "^2.19.4",
    "zksync-ethers": "^6.0.0"
  }
}
```

**Changes:**
- Added Hardhat and zkSync devDependencies
- Added npm scripts for all deployment targets
- Added compile scripts for each target
- Added clean script

---

### 2. `verifier/.gitignore`

**Before:**
```
contracts/.placeholder
test/.placeholder
build
node_modules
deploy_mnemonic.key
```

**After:**
```
# Truffle
build
contracts/.placeholder
test/.placeholder

# Hardhat
cache
cache-hardhat
artifacts
artifacts-hardhat

# zkSync
cache-zk
artifacts-zk

# Dependencies
node_modules

# Environment & Secrets
.env
deploy_mnemonic.key
*.key
*.secret

# IDE
.idea
.vscode

# OS
.DS_Store
Thumbs.db

# Logs
*.log
npm-debug.log*

# Coverage
coverage
coverage.json
```

**Changes:**
- Added Hardhat artifact directories
- Added zkSync artifact directories
- Added .env to gitignore
- Added IDE and OS files

---

### 3. `verifier/contracts/Migrations.sol`

**Before:**
```solidity
// SPDX-License-Identifier: MIT
pragma solidity >=0.4.22 <0.9.0;

contract Migrations {
  address public owner = msg.sender;
  uint public last_completed_migration;

  modifier restricted() {
    require(
      msg.sender == owner,
      "This function is restricted to the contract's owner"
    );
    _;
  }

  function setCompleted(uint completed) public restricted {
    last_completed_migration = completed;
  }
}
```

**After:**
```solidity
// SPDX-License-Identifier: MIT
pragma solidity >=0.4.22 <0.9.0;

contract Migrations {
  address public owner = msg.sender;
  uint public last_completed_migration;

  function setCompleted(uint completed) public {
    require(
      msg.sender == owner,
      "This function is restricted to the contract's owner"
    );
    last_completed_migration = completed;
  }
}
```

**Changes:**
- Removed `modifier restricted()` (zkSync doesn't support modifiers)
- Inlined the require statement directly in the function

---

### 4. `verifier/contracts/model.sol`

**Before:**
```solidity
pragma solidity ^0.8.0;

import "./verifier.sol";

contract Model is Verifier{
    struct Hash {
        uint a; uint b; uint c; uint d;
        uint e; uint f; uint g; uint h;
    }

    struct Signiture {
        uint256[2] R;
        uint256 S;
    }

    Hash current_hash;
    Signiture sig;
    string current_ciphertext = "";

    constructor(Hash memory start_hash, string memory start_ciphertext) {
        current_hash = start_hash;
        current_ciphertext = start_ciphertext;
    }

    function stepModel(Hash memory hash, string memory ciphertext, Signiture memory sig_new, Proof memory p) public {
        uint[19] memory inputs = [current_hash.a,current_hash.b,current_hash.c,current_hash.d,current_hash.e,current_hash.f,current_hash.g,current_hash.h,sig_new.R[0],sig_new.R[1],sig_new.S,hash.a,hash.b,hash.c,hash.d,hash.e,hash.f,hash.g,hash.h];
        bool verified = verifyTx(p, inputs);
        assert(verified);
        current_ciphertext = ciphertext;
        sig = sig_new;
        current_hash = hash;
    }

    function getCurrentHash() public view returns (Hash memory) {
        return current_hash;
    }

    function getLastSignature() public view returns (Signiture memory) {
        return sig;
    }

    function getCiphertext() public view returns (string memory) {
        return current_ciphertext;
    }
}
```

**After:**
```solidity
// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.0;

import "./verifier.sol";

contract Model is Verifier{
    struct Hash {
        uint a; uint b; uint c; uint d;
        uint e; uint f; uint g; uint h;
    }

    struct Signiture {
        uint256[2] R;
        uint256 S;
    }

    Hash current_hash;
    Signiture sig;
    string current_ciphertext = "";

    constructor(Hash memory start_hash, string memory start_ciphertext) {
        current_hash = start_hash;
        current_ciphertext = start_ciphertext;
    }

    function stepModel(Hash memory hash, string memory ciphertext, Signiture memory sig_new, Proof memory p) public {
        uint[19] memory inputs = [current_hash.a,current_hash.b,current_hash.c,current_hash.d,current_hash.e,current_hash.f,current_hash.g,current_hash.h,sig_new.R[0],sig_new.R[1],sig_new.S,hash.a,hash.b,hash.c,hash.d,hash.e,hash.f,hash.g,hash.h];
        bool verified = verifyTx(p, inputs);
        assert(verified);
        current_ciphertext = ciphertext;
        sig = sig_new;
        current_hash = hash;
    }

    // zkSync-compatible: return individual values instead of struct
    function getCurrentHash() public view returns (uint, uint, uint, uint, uint, uint, uint, uint) {
        return (current_hash.a, current_hash.b, current_hash.c, current_hash.d, current_hash.e, current_hash.f, current_hash.g, current_hash.h);
    }

    // zkSync-compatible: return individual values instead of struct
    function getLastSignature() public view returns (uint256[2] memory, uint256) {
        return (sig.R, sig.S);
    }

    function getCiphertext() public view returns (string memory) {
        return current_ciphertext;
    }
}
```

**Changes:**
- Added SPDX license identifier
- Changed `getCurrentHash()` to return tuple instead of struct
- Changed `getLastSignature()` to return tuple instead of struct
- Added comments explaining zkSync compatibility

---

### 5. `verifier/contracts/verifier.sol`

**Before:**
```solidity
// This file is MIT Licensed.
//
// Copyright 2017 Christian Reitwiessner
// ...
pragma solidity ^0.8.0;
```

**After:**
```solidity
// SPDX-License-Identifier: MIT
// This file is MIT Licensed.
//
// Copyright 2017 Christian Reitwiessner
// ...
pragma solidity ^0.8.0;
```

**Changes:**
- Added SPDX license identifier on first line

---

## Directory Structure After Migration

```
verifier/
├── contracts/
│   ├── Migrations.sol          # Modified: removed modifier
│   ├── model.sol               # Modified: tuple returns
│   └── verifier.sol            # Modified: added SPDX
├── migrations/                  # Truffle migrations (unchanged)
│   ├── 1_initial_migration.js
│   └── 2_deploy_model.js
├── deploy/                      # NEW: zkSync deployment
│   └── deploy-model.js
├── scripts/                     # NEW: Hardhat scripts
│   ├── deploy.js
│   └── estimate-gas.js
├── test/                        # Test directory (unchanged)
├── truffle-config.js            # Truffle config (unchanged)
├── hardhat.config.js            # NEW: Hardhat + zkSync config
├── package.json                 # Modified: added dependencies
├── .env.example                 # NEW: environment template
└── .gitignore                   # Modified: added new ignores
```

---

## Backward Compatibility

All existing functionality is preserved:

| Feature | Before | After |
|---------|--------|-------|
| Truffle compile | `npx truffle compile` | `npm run compile:truffle` |
| Truffle deploy (Ganache) | `npx truffle migrate` | `npm run deploy:ganache` |
| Truffle deploy (Sepolia) | `npx truffle migrate --network sepolia` | Still works |

**New capabilities added:**

| Feature | Command |
|---------|---------|
| Hardhat compile | `npm run compile:hardhat` |
| zkSync compile | `npm run compile:zksync` |
| Hardhat deploy (localhost) | `npm run deploy:localhost` |
| Hardhat deploy (Sepolia) | `npm run deploy:sepolia` |
| zkSync deploy (testnet) | `npm run deploy:zksync-testnet` |
| zkSync deploy (mainnet) | `npm run deploy:zksync-mainnet` |

---

## zkSync Compiler Limitations Encountered

### 1. Modifiers Not Supported

**Error:**
```
UnimplementedFeatureError: Modifiers not implemented yet.
```

**Solution:** Inline modifier logic directly in functions.

### 2. Complex Struct Returns Not Supported

**Error:**
```
CodeGenerationError: Unimplemented feature error
--> contracts/model.sol:63:9:
   |
63 |         return sig;
   |         ^^^^^^^^^^
```

**Solution:** Return tuples instead of structs.

### 3. Deprecated Compiler Version

**Error:**
```
The solc version 1.3.21 is deprecated and will be removed for security reasons soon.
```

**Solution:** Updated to zksolc v1.5.0 in hardhat.config.js.

---

## Testing the Migration

### Test Ethereum Deployment

```bash
# Start Ganache
npm run ganache

# In another terminal
npm run compile:hardhat
npm run deploy:localhost
```

### Test zkSync Compilation

```bash
npm run compile:zksync
```

### Compare Gas Costs

```bash
npx hardhat run scripts/estimate-gas.js
```

---

## Rollback Instructions

If you need to revert to Ethereum-only:

1. Delete new files:
   ```bash
   rm -rf verifier/hardhat.config.js
   rm -rf verifier/deploy/
   rm -rf verifier/scripts/
   rm -rf verifier/.env.example
   ```

2. Restore original contracts from git:
   ```bash
   git checkout verifier/contracts/Migrations.sol
   git checkout verifier/contracts/model.sol
   git checkout verifier/contracts/verifier.sol
   ```

3. Restore original package.json:
   ```bash
   git checkout verifier/package.json
   ```

4. Clean up:
   ```bash
   rm -rf node_modules
   npm install
   ```
