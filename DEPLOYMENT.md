# zkWF Deployment Guide

This guide explains how to deploy zkWF smart contracts to Ethereum, zkSync Era, and other EVM-compatible networks.

## Supported Networks

| Network | Tooling | Status |
|---------|---------|--------|
| Local Ganache | Truffle | ✅ Supported |
| Ethereum Sepolia | Truffle / Hardhat | ✅ Supported |
| Ethereum Mainnet | Truffle / Hardhat | ✅ Supported |
| zkSync Era Testnet | Hardhat | ✅ Supported |
| zkSync Era Mainnet | Hardhat | ✅ Supported |

---

## Prerequisites

Before starting, ensure you have the following installed:

- **Java 11+** - For running the CLI tool
- **Node.js 18+** - For Truffle, Hardhat, and Ganache
- **ZoKrates** - For zero-knowledge proof compilation
- **Python 3** - For cryptographic utilities

### Install Node.js Dependencies

```bash
cd verifier
npm install
```

This installs both Truffle (for Ganache/Ethereum) and Hardhat (for zkSync Era).

### Install Python Dependencies

```bash
cd pycrypto
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install bitstring
```

---

## Quick Start Commands

After setup, use these npm scripts:

```bash
cd verifier

# Compile contracts
npm run compile:truffle     # For Truffle
npm run compile:hardhat     # For Hardhat
npm run compile:zksync      # For zkSync

# Deploy contracts
npm run deploy:ganache          # Local Ganache (Truffle)
npm run deploy:localhost        # Local Hardhat node
npm run deploy:sepolia          # Ethereum Sepolia testnet
npm run deploy:zksync-testnet   # zkSync Era testnet
npm run deploy:zksync-mainnet   # zkSync Era mainnet
```

---

## Part 1: Generate ZoKrates Circuits from BPMN

Before deploying to any network, you need to generate the verifier contract from your BPMN model.

### Step 1: Build the CLI Tool

```bash
cd generator
./gradlew cli:shadowjar
```

### Step 2: Generate ZoKrates Circuits

```bash
cd generator
source ../pycrypto/venv/bin/activate
java -jar cli/build/libs/cli-1.0-SNAPSHOT-all.jar --skip-tests \
    ../models/leasing-payment/leasing-payment.bpmn \
    ../models/leasing-payment/testCases.json
```

### Step 3: Export Verifier Contract

```bash
cd generator
zokrates export-verifier
```

### Step 4: Copy Verifier to Contracts Folder

```bash
cp generator/verifier.sol verifier/contracts/
```

---

## Part 2: Deploy to Local Ganache (Truffle)

### Step 5: Start Ganache

```bash
cd verifier
npm run ganache
```

Keep this terminal open.

### Step 6: Deploy (new terminal)

```bash
cd verifier
npm run compile:truffle
npm run deploy:ganache
```

### Expected Output

```
Deploying 'Model'
-----------------
> contract address:    0x07F7Febd1D0Bc3cB981e0Fbfd67A6941809D8D93
> gas used:            2764874
> total cost:          0.008033 ETH
```

---

## Part 3: Deploy to Ethereum Sepolia (Hardhat)

### Step 7: Configure Environment

```bash
cd verifier
cp .env.example .env
```

Edit `.env` and add your credentials:

```
PRIVATE_KEY=your_private_key_without_0x
INFURA_PROJECT_ID=your_infura_project_id
ETHERSCAN_API_KEY=your_etherscan_api_key
```

### Step 8: Get Testnet ETH

Get free Sepolia ETH from:
- https://sepoliafaucet.com
- https://www.alchemy.com/faucets/ethereum-sepolia

### Step 9: Deploy to Sepolia

```bash
cd verifier
npm run compile:hardhat
npm run deploy:sepolia
```

---

## Part 4: Deploy to zkSync Era

zkSync Era is a ZK rollup that offers lower gas costs while maintaining EVM compatibility.

### Step 10: Get zkSync Testnet ETH

1. Bridge Sepolia ETH to zkSync Era Testnet:
   - https://portal.zksync.io/bridge

2. Or use the zkSync faucet (if available)

### Step 11: Configure Environment

Same `.env` file works for zkSync:

```
PRIVATE_KEY=your_private_key_without_0x
```

### Step 12: Compile for zkSync

```bash
cd verifier
npm run compile:zksync
```

This uses `zksolc` compiler instead of standard `solc`.

### Step 13: Deploy to zkSync Era Testnet

```bash
cd verifier
npm run deploy:zksync-testnet
```

### Step 14: Deploy to zkSync Era Mainnet

```bash
cd verifier
npm run deploy:zksync-mainnet
```

### Expected Output (zkSync)

```
====================================
zkWF Model Contract Deployment
Network: zkSyncTestnet
====================================

Deployer address: 0x...
Estimated deployment fee: 0.00X ETH

Deploying Model contract...

====================================
Deployment Successful!
====================================
Contract address: 0x...
```

---

## Gas Usage Reference

### Ethereum Networks

| Contract | Gas Used | Estimated Cost (ETH) |
|----------|----------|----------------------|
| Migrations | ~245,656 | ~0.0007 ETH |
| Model | ~2,764,874 | ~0.008 ETH |
| **Total** | **~3,010,530** | **~0.009 ETH** |

### Cost Comparison by Network

| Network | Gas Price | Model Deployment Cost |
|---------|-----------|----------------------|
| Ganache (local) | ~3 gwei | ~0.008 ETH |
| Sepolia (testnet) | ~20 gwei | ~0.055 ETH |
| Ethereum Mainnet | ~30 gwei | ~0.083 ETH |
| zkSync Era Testnet | Variable | ~0.001-0.01 ETH |
| zkSync Era Mainnet | Variable | ~0.005-0.02 ETH |

*zkSync costs are typically 10-100x cheaper than Ethereum L1.*

---

## Deployment Methods Summary

### Method 1: Truffle (Ganache, Ethereum)

```bash
# Compile
npx truffle compile --all

# Deploy to Ganache
npx truffle migrate --reset --network development

# Deploy to Sepolia
npx truffle migrate --network sepolia
```

### Method 2: Hardhat (Ethereum, any EVM)

```bash
# Compile
npx hardhat compile

# Deploy to localhost
npx hardhat run scripts/deploy.js --network localhost

# Deploy to Sepolia
npx hardhat run scripts/deploy.js --network sepolia
```

### Method 3: Hardhat + zkSync (zkSync Era)

```bash
# Compile for zkSync
npx hardhat compile --network zkSyncTestnet

# Deploy to zkSync testnet
npx hardhat deploy-zksync --script deploy-model.js --network zkSyncTestnet

# Deploy to zkSync mainnet
npx hardhat deploy-zksync --script deploy-model.js --network zkSyncMainnet
```

---

## CLI Options Reference

```
Usage: java -jar cli-1.0-SNAPSHOT-all.jar [OPTIONS] <bpmnFile> <testCases>

Options:
  --deploy       Deploy smart contract (default: false)
  --skip-setup   Skip the setup phase (default: false)
  --skip-tests   Skip all test cases, only compile (default: false)
  --help         Show help
```

---

## Available BPMN Models

| Model | Path |
|-------|------|
| leasing-payment | `models/leasing-payment/leasing-payment.bpmn` |
| t1_zkp - t5_zkp | `models/unit_tests/t*.bpmn` |

---

## Troubleshooting

### "No module named 'bitstring'"

```bash
source pycrypto/venv/bin/activate
pip install bitstring
```

### "verifier.sol not found"

```bash
cd generator
zokrates export-verifier
cp verifier.sol ../verifier/contracts/
```

### Ganache connection refused

```bash
cd verifier
npm run ganache
```

### "externally-managed-environment" Python error

```bash
source pycrypto/venv/bin/activate
pip install <package>
```

### zkSync compilation errors

Make sure you're using the correct network flag:

```bash
npx hardhat compile --network zkSyncTestnet
```

### "Insufficient funds" on zkSync

Bridge ETH from Sepolia to zkSync Era Testnet:
- https://portal.zksync.io/bridge

---

## File Structure

```
verifier/
├── contracts/
│   ├── Migrations.sol
│   ├── model.sol
│   └── verifier.sol          # Generated by ZoKrates
├── migrations/               # Truffle migrations
│   ├── 1_initial_migration.js
│   └── 2_deploy_model.js
├── deploy/                   # zkSync deployment scripts
│   └── deploy-model.js
├── scripts/                  # Hardhat deployment scripts
│   └── deploy.js
├── truffle-config.js         # Truffle configuration
├── hardhat.config.js         # Hardhat + zkSync configuration
├── package.json
├── .env.example
└── .gitignore
```

---

## Security Notes

- **Never commit** `.env` or private keys to version control
- Use environment variables for sensitive data
- Test on testnets before deploying to mainnet
- Verify contract source code on block explorers after deployment
