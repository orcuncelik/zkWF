# zkWF Deployment to zkSync Era

This guide covers deploying zkWF smart contracts to zkSync Era, a ZK rollup that offers significantly lower gas costs compared to Ethereum mainnet.

## Why zkSync Era?

| Metric | Ethereum Mainnet | zkSync Era | Savings |
|--------|------------------|------------|---------|
| Deployment Gas | 1,962,382 | ~196,238 | 90% |
| Deployment Cost | ~$147 | ~$0.12 | **99.9%** |
| Transaction Finality | ~12 min | ~1 min | 12x faster |
| Security | L1 | L1 (via ZK proofs) | Same |

*Costs based on ETH at $2,500 and typical gas prices*

---

## Prerequisites

### Required Software

- **Node.js 18+** - JavaScript runtime
- **Java 11+** - For zkWF CLI tool
- **ZoKrates** - Zero-knowledge proof compiler
- **Python 3** - For cryptographic utilities

### Required Accounts

- **Wallet** - MetaMask or any Ethereum wallet
- **Testnet ETH** - Sepolia ETH for bridging to zkSync

---

## Step 1: Install Dependencies

```bash
cd verifier
npm install
```

This installs:
- Hardhat (smart contract development framework)
- @matterlabs/hardhat-zksync-solc (zkSync Solidity compiler)
- @matterlabs/hardhat-zksync-deploy (zkSync deployment plugin)
- zksync-ethers (zkSync SDK)

---

## Step 2: Generate Verifier Contract from BPMN

Before deploying, generate the ZoKrates verifier from your BPMN model.

### Build the CLI tool

```bash
cd generator
./gradlew cli:shadowjar
```

### Generate circuits from BPMN

```bash
cd generator
source ../pycrypto/venv/bin/activate
java -jar cli/build/libs/cli-1.0-SNAPSHOT-all.jar --skip-tests \
    ../models/leasing-payment/leasing-payment.bpmn \
    ../models/leasing-payment/testCases.json
```

### Export verifier contract

```bash
cd generator
zokrates export-verifier
```

### Copy to contracts folder

```bash
cp generator/verifier.sol verifier/contracts/
```

---

## Step 3: Configure Environment

### Create environment file

```bash
cd verifier
cp .env.example .env
```

### Edit .env file

```bash
# Open .env and add your private key
PRIVATE_KEY=your_private_key_here_without_0x_prefix
```

### How to get your private key

1. Open MetaMask
2. Click on the three dots menu
3. Select "Account details"
4. Click "Export Private Key"
5. Enter your password
6. Copy the private key (without the 0x prefix)

**Security Warning:** Never share your private key or commit it to version control.

---

## Step 4: Get zkSync Testnet ETH

### Option A: Bridge from Sepolia

1. Get Sepolia ETH from a faucet:
   - https://sepoliafaucet.com
   - https://www.alchemy.com/faucets/ethereum-sepolia

2. Bridge to zkSync Era Testnet:
   - Go to https://portal.zksync.io/bridge
   - Connect your wallet
   - Select "Sepolia" as source
   - Select "zkSync Era Sepolia Testnet" as destination
   - Enter amount and bridge

### Option B: zkSync Faucet (if available)

- Check https://portal.zksync.io for faucet availability

---

## Step 5: Compile for zkSync

```bash
cd verifier
npx hardhat compile --network zkSyncTestnet
```

Expected output:
```
Compiling contracts for ZKsync Era with zksolc v1.5.0
Compiling 3 Solidity files
Successfully compiled 3 Solidity files
```

**Note:** zkSync uses a different compiler (zksolc) that generates different bytecode than standard solc.

---

## Step 6: Deploy to zkSync Era Testnet

```bash
cd verifier
npm run deploy:zksync-testnet
```

Or using npx directly:
```bash
npx hardhat deploy-zksync --script deploy-model.js --network zkSyncTestnet
```

Expected output:
```
====================================
zkWF Model Contract Deployment
Network: zkSyncTestnet
====================================

Deployer address: 0x...
Estimated deployment fee: 0.0001 ETH

Deploying Model contract...

====================================
Deployment Successful!
====================================
Contract address: 0x...
Deployment time: X.XX seconds
Network: zkSyncTestnet
====================================
```

---

## Step 7: Verify Contract (Optional)

```bash
npx hardhat verify --network zkSyncTestnet <CONTRACT_ADDRESS>
```

View your contract on zkSync Explorer:
- Testnet: https://sepolia.explorer.zksync.io/address/<CONTRACT_ADDRESS>
- Mainnet: https://explorer.zksync.io/address/<CONTRACT_ADDRESS>

---

## Step 8: Deploy to zkSync Era Mainnet

Once tested on testnet, deploy to mainnet:

```bash
cd verifier
npm run deploy:zksync-mainnet
```

Or:
```bash
npx hardhat deploy-zksync --script deploy-model.js --network zkSyncMainnet
```

**Warning:** Mainnet deployment uses real ETH. Ensure you have sufficient funds.

---

## Available Commands

| Command | Description |
|---------|-------------|
| `npm run compile:zksync` | Compile contracts for zkSync |
| `npm run deploy:zksync-testnet` | Deploy to zkSync Era Testnet |
| `npm run deploy:zksync-mainnet` | Deploy to zkSync Era Mainnet |
| `npm run clean` | Remove all build artifacts |

---

## Gas Estimation

Run the gas estimation script to compare costs:

```bash
cd verifier
npx hardhat run scripts/estimate-gas.js
```

Sample output:
```
====================================
zkWF Gas Estimation Report
====================================

Bytecode Size Comparison
--------------------------------------------------
Ethereum (solc):     9,310 bytes
zkSync Era (zksolc): 21,600 bytes

Estimated Deployment Costs
--------------------------------------------------
Ethereum Mainnet:  0.058871 ETH ($147.18)
zkSync Era:        0.000049 ETH ($0.12)
Estimated Savings: 99.9%
```

---

## zkSync-Specific Code Changes

The following changes were made for zkSync compatibility:

### 1. Migrations.sol

zkSync doesn't support Solidity modifiers. Changed from:

```solidity
// Before (not zkSync compatible)
modifier restricted() {
    require(msg.sender == owner, "Restricted");
    _;
}
function setCompleted(uint completed) public restricted { ... }
```

To:

```solidity
// After (zkSync compatible)
function setCompleted(uint completed) public {
    require(msg.sender == owner, "Restricted");
    ...
}
```

### 2. model.sol

zkSync has limited support for returning structs. Changed from:

```solidity
// Before (not zkSync compatible)
function getCurrentHash() public view returns (Hash memory) {
    return current_hash;
}
```

To:

```solidity
// After (zkSync compatible)
function getCurrentHash() public view returns (uint, uint, uint, uint, uint, uint, uint, uint) {
    return (current_hash.a, current_hash.b, ...);
}
```

### 3. verifier.sol

Added SPDX license identifier:

```solidity
// SPDX-License-Identifier: MIT
```

---

## Network Configuration

### zkSync Era Testnet

| Parameter | Value |
|-----------|-------|
| Network Name | zkSync Era Sepolia Testnet |
| RPC URL | https://sepolia.era.zksync.dev |
| Chain ID | 300 |
| Currency | ETH |
| Explorer | https://sepolia.explorer.zksync.io |

### zkSync Era Mainnet

| Parameter | Value |
|-----------|-------|
| Network Name | zkSync Era Mainnet |
| RPC URL | https://mainnet.era.zksync.io |
| Chain ID | 324 |
| Currency | ETH |
| Explorer | https://explorer.zksync.io |

### Add to MetaMask

1. Open MetaMask
2. Click network dropdown
3. Click "Add Network"
4. Enter the parameters above

---

## Troubleshooting

### "Modifiers not implemented yet"

The zkSync compiler doesn't support Solidity modifiers. Inline the modifier logic directly in the function.

### "Unimplemented feature error" for struct returns

zkSync has limited support for returning complex structs. Return individual values as tuples instead.

### "Insufficient funds"

Ensure you have enough ETH on zkSync Era:
1. Bridge ETH from Sepolia/Ethereum to zkSync
2. Wait for bridge confirmation (~15 minutes)

### "Please set PRIVATE_KEY"

Create a `.env` file with your private key:
```bash
cp .env.example .env
# Edit .env and add PRIVATE_KEY=your_key_here
```

### Compilation takes too long

zkSync compilation downloads the zksolc compiler on first run. This is normal and only happens once.

### Contract verification fails

Ensure you're using the same compiler version:
```bash
npx hardhat verify --network zkSyncTestnet <ADDRESS>
```

---

## File Structure

```
verifier/
├── contracts/
│   ├── Migrations.sol      # zkSync-compatible (no modifiers)
│   ├── model.sol           # zkSync-compatible (tuple returns)
│   └── verifier.sol        # Generated by ZoKrates
├── deploy/
│   └── deploy-model.js     # zkSync deployment script
├── scripts/
│   ├── deploy.js           # Standard Hardhat deployment
│   └── estimate-gas.js     # Gas comparison script
├── hardhat.config.js       # Hardhat + zkSync configuration
├── package.json            # Dependencies and scripts
├── .env.example            # Environment template
└── .gitignore              # Ignores .env and artifacts
```

---

## Resources

- **zkSync Documentation:** https://docs.zksync.io
- **zkSync Portal:** https://portal.zksync.io
- **zkSync Explorer (Testnet):** https://sepolia.explorer.zksync.io
- **zkSync Explorer (Mainnet):** https://explorer.zksync.io
- **Hardhat zkSync Plugins:** https://docs.zksync.io/build/tooling/hardhat

---

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review zkSync documentation: https://docs.zksync.io
3. Open an issue on the zkWF repository
