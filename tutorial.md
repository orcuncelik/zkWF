# zkWF Tutorial: Zero-Knowledge Workflow Engine

> A comprehensive, beginner-friendly guide to privacy-preserving business process verification on blockchain

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Key Concepts](#2-key-concepts)
3. [Architecture Overview](#3-architecture-overview)
4. [Prerequisites](#4-prerequisites)
5. [Step-by-Step Walkthrough](#5-step-by-step-walkthrough)
6. [CLI Reference](#6-cli-reference)
7. [Understanding Zero-Knowledge Proofs in zkWF](#7-understanding-zero-knowledge-proofs-in-zkwf)
8. [Troubleshooting](#8-troubleshooting)
9. [Next Steps & Resources](#9-next-steps--resources)

---

## 1. Introduction

### What is zkWF?

**zkWF (Zero-Knowledge WorkFlow)** is a blockchain-based orchestration engine that enables multiple parties to execute collaborative workflows while keeping sensitive process data confidential. It combines:

- **BPMN 2.0 diagrams** for modeling business processes
- **Zero-Knowledge Proofs (ZKPs)** for privacy-preserving verification
- **Smart contracts** for on-chain state management
- **EdDSA cryptography** for participant authorization

### The Problem It Solves

Imagine a supply chain involving a manufacturer, logistics company, and retailer. They need to coordinate a workflow (order → ship → deliver → pay), but:

- Each party wants to verify the process is followed correctly
- No party wants to reveal sensitive business data to others
- They need an immutable audit trail

**Traditional approaches** require trusting a central coordinator or revealing all data to all parties. **zkWF** solves this by allowing parties to prove they executed valid workflow steps without revealing the actual data.

### Real-World Analogy: The Sealed Envelope Game

Think of zkWF like a **sealed envelope verification system**:

1. **The Envelope**: Contains your current position in a board game (workflow state)
2. **The Move**: You make a move and seal your new position in a new envelope
3. **The Proof**: You provide a mathematical proof that your move was valid according to the game rules
4. **The Verifier**: Anyone can verify your proof without opening the envelopes

The blockchain stores the sealed envelopes (encrypted states), and zero-knowledge proofs ensure every move follows the rules.

### Comparison: Traditional vs zkWF Approach

| Aspect | Traditional Approach | zkWF Approach |
|--------|---------------------|---------------|
| **Privacy** | All parties see all data | Only relevant parties see their data |
| **Trust** | Requires trusted coordinator | Trustless - math guarantees correctness |
| **Auditability** | Centralized logs | Immutable on-chain proof trail |
| **Verification** | Manual or trusted third party | Automatic cryptographic verification |
| **Data Storage** | Plaintext in shared database | Encrypted ciphertext on-chain |
| **Dispute Resolution** | Legal/arbitration | Mathematical proof verification |

---

## 2. Key Concepts

### 2.1 BPMN Collaboration Diagrams

**BPMN (Business Process Model and Notation)** is a standard for modeling business workflows. In zkWF, we use BPMN to define:

- **Participants**: Entities involved (e.g., Buyer, Seller, Logistics)
- **Tasks**: Actions to be performed
- **Gateways**: Decision points (exclusive OR, parallel AND)
- **Message Flows**: Communication between participants
- **Events**: Start and end points

```
┌─────────────────────────────────────────────────────────────┐
│                     BPMN Collaboration                       │
│                                                             │
│  ○──→ [Place Order] ──→ ◇ ──→ [Ship] ──→ [Deliver] ──→ ●   │
│  │       Buyer        │XOR│   Logistics    Logistics    │   │
│  Start               Gateway                           End  │
└─────────────────────────────────────────────────────────────┘
```

**Key insight**: BPMN diagrams define the "rules of the game" - which state transitions are valid.

### 2.2 Zero-Knowledge Proofs (ZKPs)

A **Zero-Knowledge Proof** allows you to prove you know something without revealing what you know.

**The Classic Example**: Proving you know a password without typing it.

```
┌──────────────┐         ┌──────────────┐
│   Prover     │         │   Verifier   │
│ (knows secret)│         │ (skeptical)  │
└──────┬───────┘         └──────┬───────┘
       │                        │
       │   "I know the secret"  │
       │───────────────────────→│
       │                        │
       │    Challenge question  │
       │←───────────────────────│
       │                        │
       │   Proof (no secret     │
       │   revealed!)           │
       │───────────────────────→│
       │                        │
       │   "Verified! ✓"        │
       │←───────────────────────│
```

**In zkWF**, ZKPs prove:
- The current state hash is valid
- The state transition follows BPMN rules
- The participant has authority to make this transition
- All without revealing the actual state data

zkWF uses **Groth16 SNARKs** - a specific ZKP system that produces small, fast-to-verify proofs.

### 2.3 State Vectors and Petri Nets

Internally, zkWF represents workflow state as a **Petri Net**:

- **Places**: Positions in the workflow (numbered locations)
- **Tokens**: Markers showing current position(s)
- **Transitions**: Valid moves from one state to another

```
State Vector Example:
┌─────┬─────┬─────┬─────┬─────┐
│  1  │  0  │  0  │  0  │  0  │  ← Token at Start
└─────┴─────┴─────┴─────┴─────┘
   ↓ (execute Task 1)
┌─────┬─────┬─────┬─────┬─────┐
│  0  │  1  │  0  │  0  │  0  │  ← Token at Task 1
└─────┴─────┴─────┴─────┴─────┘
   ↓ (execute Task 2)
┌─────┬─────┬─────┬─────┬─────┐
│  0  │  0  │  1  │  0  │  0  │  ← Token at Task 2
└─────┴─────┴─────┴─────┴─────┘
```

**Parallel gateways** can create multiple tokens (concurrent execution), while **exclusive gateways** choose one path.

### 2.4 EdDSA Signatures on BabyJubJub

zkWF uses **EdDSA (Edwards-curve Digital Signature Algorithm)** on the **BabyJubJub curve** for:

- **Participant identity**: Each participant has a public/private key pair
- **Authorization**: Signatures prove who executed a state transition
- **SNARK-friendliness**: BabyJubJub is optimized for ZK circuits

```
Key Generation:
┌─────────────────┐    ┌─────────────────────────────────────────┐
│  Random Seed    │───→│  Private Key: 0x1234...                 │
└─────────────────┘    │  Public Key:  (x, y) point on curve     │
                       └─────────────────────────────────────────┘
```

### 2.5 Workflow Execution Model

zkWF workflow execution consists of two stages:

| Stage | Function | What Happens |
|-------|----------|--------------|
| **Deployment** | `constructor()` | Initial state hash and ciphertext are set on-chain |
| **Step Execution** | `stepModel()` | Each workflow transition is verified and state is updated |

The `stepModel()` function is called for every state transition until the workflow reaches an end state. Each call verifies:
- The current state hash matches what's stored on-chain
- The state transition follows BPMN rules
- The participant signature is valid
- The new state hash is correctly computed

---

## 3. Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           zkWF Architecture                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐    │
│  │    Editor    │     │    Generator     │     │     Verifier      │    │
│  │  (Browser)   │     │   (Kotlin/JVM)   │     │   (Blockchain)    │    │
│  │              │     │                  │     │                   │    │
│  │  • Draw BPMN │────→│  • Parse BPMN    │────→│  • Model.sol      │    │
│  │  • Add keys  │     │  • Gen circuits  │     │  • Verifier.sol   │    │
│  │  • Export XML│     │  • Create proofs │     │  • State storage  │    │
│  └──────────────┘     └────────┬─────────┘     └─────────┬─────────┘    │
│                                │                         │              │
│                                ▼                         │              │
│                       ┌──────────────────┐               │              │
│                       │    ZoKrates      │               │              │
│                       │                  │               │              │
│                       │  • Compile .zok  │───────────────┘              │
│                       │  • Setup keys    │   (verification key         │
│                       │  • Gen witness   │    embedded in contract)    │
│                       │  • Create proof  │                              │
│                       └──────────────────┘                              │
│                                                                          │
│  ┌──────────────┐                                                        │
│  │   pycrypto   │     Python utilities for key generation,              │
│  │   (Python)   │     hashing, and signature operations                 │
│  └──────────────┘                                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Step 1: Design Phase
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  User    │────→│ BPMN Editor  │────→│  .bpmn file │
│          │     │ (draw flow)  │     │  (XML)      │
└──────────┘     └──────────────┘     └──────┬──────┘
                                             │
Step 2: Generation Phase                     ▼
                                    ┌─────────────────┐
                                    │    Generator    │
                                    │                 │
                                    │ 1. Parse BPMN   │
                                    │ 2. Extract state│
                                    │ 3. Gen circuits │
                                    └────────┬────────┘
                                             │
                                             ▼
                               ┌─────────────────────────┐
                               │      ZoKrates           │
                               │                         │
                               │ 4. Compile circuits     │
                               │ 5. Setup (proving key)  │
                               │ 6. Export verifier.sol  │
                               └────────────┬────────────┘
                                            │
Step 3: Deployment Phase                    ▼
                               ┌─────────────────────────┐
                               │     Blockchain          │
                               │                         │
                               │ 7. Deploy Verifier.sol  │
                               │ 8. Deploy Model.sol     │
                               │ 9. Initialize state     │
                               └────────────┬────────────┘
                                            │
Step 4: Execution Phase                     ▼
┌──────────┐                   ┌─────────────────────────┐
│Participant│──────────────────│   For each step:        │
│          │                   │                         │
│ • Sign   │                   │ 10. Compute witness     │
│ • Prove  │                   │ 11. Generate proof      │
│ • Submit │                   │ 12. Call stepModel()    │
└──────────┘                   │ 13. Verify on-chain     │
                               └─────────────────────────┘
```

### Component Summary

| Component | Technology | Role |
|-----------|------------|------|
| **Editor** | JavaScript, bpmn-js | Visual BPMN diagram creation |
| **Generator CLI** | Kotlin, Gradle | Parse BPMN, generate ZoKrates circuits |
| **Generator GUI** | JavaFX | Visual interface for generation |
| **ZoKrates** | Rust binary | Compile circuits, create proofs |
| **pycrypto** | Python | Key generation, hashing, signatures |
| **Verifier.sol** | Solidity | SNARK proof verification |
| **Model.sol** | Solidity | Workflow state management |
| **Hardhat/Truffle** | JavaScript | Smart contract deployment |

---

## 4. Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| **Java JDK** | 21+ | Run Generator (Kotlin/JVM) |
| **Node.js** | 18+ | Run Editor, deploy contracts |
| **Python** | 3.8+ | Cryptographic utilities |
| **Git** | 2.0+ | Clone repository |

### Verify Installations

```bash
# Check Java version (need 21+)
java -version
# Expected: openjdk version "21.0.x" or higher

# Check Node.js version (need 18+)
node --version
# Expected: v18.x.x or higher

# Check npm version
npm --version
# Expected: 9.x.x or higher

# Check Python version (need 3.8+)
python3 --version
# Expected: Python 3.8.x or higher

# Check Git version
git --version
# Expected: git version 2.x.x
```

### Installation Steps

#### Step 1: Clone the Repository

```bash
git clone https://github.com/mediatechnologycenter/zkWF.git
cd zkWF
```

#### Step 2: Install Python Dependencies

```bash
cd pycrypto
pip3 install -r requirements.txt
cd ..
```

#### Step 3: Build the Generator

```bash
cd generator

# Build CLI tool
./gradlew cli:shadowJar

# Build GUI tool (optional)
./gradlew gui:shadowJar

cd ..
```

#### Step 4: Install Editor Dependencies

```bash
cd editor
npm install
cd ..
```

#### Step 5: Install Verifier Dependencies

```bash
cd verifier
npm install
cd ..
```

#### Step 6: Verify ZoKrates Binary

The repository includes a pre-compiled ZoKrates binary for ARM/x86:

```bash
# Check ZoKrates works
./.zokrates/bin/zokrates --version
# Expected: ZoKrates 0.8.x
```

---

## 5. Step-by-Step Walkthrough

Let's walk through a complete example: a **Payment Approval Workflow** where:
- A **Requester** submits a payment request
- An **Approver** reviews and approves/rejects
- If approved, a **Processor** executes the payment

### Step 0: Understand the Example Workflow

```
Payment Approval Workflow:

    Requester          Approver           Processor
        │                  │                  │
        ○ Start            │                  │
        │                  │                  │
        ▼                  │                  │
   [Submit Request]────────│                  │
        │                  │                  │
        │                  ▼                  │
        │            [Review Request]         │
        │                  │                  │
        │                  ◇ Decision         │
        │                 /│\                 │
        │    Approved ───┘ │ └─── Rejected    │
        │        │         │         │        │
        │        ▼         │         ▼        │
        │   [Approve]      │    [Reject]      │
        │        │         │         │        │
        │        └────┬────┘         │        │
        │             │              │        │
        │             ▼              │        │
        │       ◇ Merge              │        │
        │             │              │        │
        │             └──────────────│────────┘
        │                            │
        │                            ▼
        │                     [Process Payment]
        │                            │
        │                            ▼
        │                            ● End
```

### Step 1: Create the BPMN Diagram

Start the BPMN Editor:

```bash
cd editor
npm run dev
```

Open your browser to `http://localhost:9000`. You'll see the BPMN editor.

Create your workflow by:
1. Adding a **Pool** with three **Lanes**: Requester, Approver, Processor
2. Adding **Start Event** in Requester lane
3. Adding **Tasks**: Submit Request, Review Request, Approve, Reject, Process Payment
4. Adding **Exclusive Gateway** for decision
5. Adding **End Event**
6. Connecting with **Sequence Flows**

**Important**: For each lane, add the participant's public key in the properties panel under `zkp:publicKey`.

Save the diagram as `payment-workflow.bpmn`.

### Step 2: Generate Participant Keys

Use pycrypto to generate EdDSA key pairs:

```bash
cd pycrypto

# Generate random keys for Requester
python3 cli.py keygen
```

**Example Output**:
```
PrivateKey PublicKey
1a2b3c4d5e6f... 7350854827252829541674033642803854801334834402587808031858165572750984534676
```

The output shows space-separated hex values:
- **First value**: Private key (keep secret!)
- **Second value**: Compressed public key

To derive the X,Y coordinates for BPMN, you can decompress the public key or use the `bpmn_to_zkwf.py` converter which auto-generates keys.

Repeat for Approver and Processor to generate unique keys for each participant.

### Step 3: Add Keys to BPMN and Convert

If you created the BPMN in another tool without zkp extensions, use the converter:

```bash
cd pycrypto

# Convert and auto-generate keys for all participants
python3 bpmn_to_zkwf.py ../models/payment-workflow.bpmn ../models/payment-workflow-zkp.bpmn

# Or validate only (no conversion)
python3 bpmn_to_zkwf.py --validate-only ../models/payment-workflow.bpmn
```

The converter automatically:
- Adds the `zkp` namespace to the BPMN
- Generates unique EdDSA public keys for each participant
- Validates the BPMN structure for zkWF compatibility

Or manually edit the BPMN XML to add `zkp:publicKey` attributes.

### Step 4: Generate ZoKrates Circuits and Run Tests

The Generator CLI takes a BPMN file and test cases file as positional arguments:

```bash
cd ../generator

# First, create a test cases JSON file (see Step 5 for format)
# Then run the generator with BPMN and test cases:
java -jar cli/build/libs/cli-all.jar \
  ../models/payment-workflow-zkp.bpmn \
  testCases.json
```

To only compile and setup without running tests:
```bash
java -jar cli/build/libs/cli-all.jar --skip-tests \
  ../models/payment-workflow-zkp.bpmn \
  testCases.json
```

**Example Response**:
```
=== zkWF Generator ===

Loading BPMN: ../models/payment-workflow-zkp.bpmn
  ✓ Found 3 participants
  ✓ Found 5 tasks
  ✓ Found 1 exclusive gateway
  ✓ State vector size: 8

Generating ZoKrates circuits...
  ✓ Generated hash.zok (state hashing)
  ✓ Generated root.zok (main circuit)
  ✓ Generated stateChange.zok (transition logic)

Compiling circuits...
  ✓ Compiled root.zok → out (R1CS: 45,231 constraints)

Running setup...
  ✓ Generated proving.key (2.3 MB)
  ✓ Generated verification.key

Exporting Solidity verifier...
  ✓ Generated verifier.sol

Output directory: ./output/payment
  - root.zok
  - hash.zok
  - stateChange.zok
  - out (compiled circuit)
  - proving.key
  - verification.key
  - verifier.sol
```

**Understanding the Response**:
- **State vector size**: Number of places in the Petri net representation
- **R1CS constraints**: Complexity of the ZK circuit (more constraints = longer proof time)
- **proving.key**: Secret key for generating proofs (can be public after trusted setup)
- **verification.key**: Key embedded in smart contract for verification
- **verifier.sol**: Solidity contract for on-chain proof verification

### Step 5: Create Test Cases

Create a JSON file describing state transitions to test:

```bash
cat > output/payment/testCases.json << 'EOF'
[
  {
    "ID": 1,
    "description": "Submit payment request",
    "initialState": {
      "stateVector": ["1", "0", "0", "0", "0", "0", "0", "0"],
      "randomness": "1675454832",
      "variables": [],
      "messages": []
    },
    "newState": {
      "stateVector": ["0", "1", "0", "0", "0", "0", "0", "0"],
      "randomness": "2834756923",
      "variables": [{"name": "amount", "value": "1000"}],
      "messages": []
    },
    "keyIndex": 0,
    "requireRedeploy": false
  },
  {
    "ID": 2,
    "description": "Approve request",
    "initialState": {
      "stateVector": ["0", "1", "0", "0", "0", "0", "0", "0"],
      "randomness": "2834756923",
      "variables": [{"name": "amount", "value": "1000"}],
      "messages": []
    },
    "newState": {
      "stateVector": ["0", "0", "1", "0", "0", "0", "0", "0"],
      "randomness": "9876543210",
      "variables": [{"name": "amount", "value": "1000"}, {"name": "approved", "value": "true"}],
      "messages": []
    },
    "keyIndex": 1,
    "requireRedeploy": false
  }
]
EOF
```

**Understanding the Test Case**:
- **stateVector**: Token positions (1 = token present, 0 = empty)
- **randomness**: Random value for hiding state hash (different each transition)
- **variables**: Workflow data (private, not revealed on-chain)
- **messages**: Inter-participant messages
- **keyIndex**: Which participant (0 = Requester, 1 = Approver, 2 = Processor)

### Step 6: Generate Zero-Knowledge Proofs

Run the generator with your BPMN and test cases to generate proofs:

```bash
java -jar cli/build/libs/cli-all.jar \
  ../models/payment-workflow-zkp.bpmn \
  testCases.json
```

To also deploy and test on a local Ethereum node (must be running at localhost:8545):
```bash
java -jar cli/build/libs/cli-all.jar --deploy \
  ../models/payment-workflow-zkp.bpmn \
  testCases.json
```

**Example Response**:
```
=== Proof Generation ===

Test Case 1: Submit payment request
  Computing current state hash...
    Hash: [0x12ab..., 0x34cd..., 0x56ef..., ...]
  Getting participant signature...
    Signer: Requester (index 0)
    Signature: (R, S) = (0x789a..., 0x0bcd...)
  Computing witness...
    ✓ Witness computed (342 variables)
  Generating proof...
    ✓ Proof generated in 4.2s

Test Case 2: Approve request
  Computing current state hash...
    Hash: [0xaabb..., 0xccdd..., 0xeeff..., ...]
  Getting participant signature...
    Signer: Approver (index 1)
    Signature: (R, S) = (0x1122..., 0x3344...)
  Computing witness...
    ✓ Witness computed (342 variables)
  Generating proof...
    ✓ Proof generated in 4.1s

=== Results ===
✓ 2/2 proofs generated successfully

Output files:
  - proof_1.json
  - proof_2.json
```

### Step 7: Deploy Smart Contracts

First, configure your network in `verifier/hardhat.config.js`:

```javascript
module.exports = {
  networks: {
    sepolia: {
      url: process.env.SEPOLIA_RPC_URL,
      accounts: [process.env.PRIVATE_KEY]
    }
  }
};
```

Set environment variables:

```bash
cd ../verifier
cp .env.example .env
# Edit .env with your RPC URL and private key
```

Copy the generated verifier and deploy:

```bash
# Copy generated verifier
cp ../generator/output/payment/verifier.sol contracts/

# Compile contracts
npx hardhat compile

# Deploy to Sepolia testnet
npx hardhat run scripts/deploy.js --network sepolia
```

**Example Response**:
```
Compiling 2 Solidity files...
✓ Compiled contracts/verifier.sol
✓ Compiled contracts/model.sol

Deploying to Sepolia...

Initial state hash: [
  0x12ab34cd56ef7890,
  0xabcdef1234567890,
  ...
]

Verifier deployed to: 0x1234...5678
Model deployed to: 0xabcd...ef01

Gas used: 2,847,293

Verify on Etherscan:
  https://sepolia.etherscan.io/address/0xabcd...ef01
```

**Understanding the Response**:
- **Verifier contract**: Contains the SNARK verification logic
- **Model contract**: Inherits from Verifier, stores workflow state
- **Gas used**: Cost of deployment (~2.8M gas for typical workflow)

### Step 8: Execute Workflow Steps On-Chain

The Generator CLI can execute workflow steps when using the `--deploy` flag. Alternatively, you can interact with the deployed contract using Hardhat console:

```bash
npx hardhat console --network sepolia
```

```javascript
// In Hardhat console
const Model = await ethers.getContractFactory("Model");
const model = await Model.attach("0xYOUR_CONTRACT_ADDRESS");

// Load proof from generator output (proof1.json)
const proof = require("../generator/proof1.json");

// Call stepModel with the proof
const tx = await model.stepModel(
  newHash,      // Hash struct with a,b,c,d,e,f,g,h
  ciphertext,   // Encrypted new state
  signature,    // Signiture struct with R[2] and S
  proof         // Proof struct with a, b, c points
);
await tx.wait();
```

The `stepModel()` function verifies the ZK proof on-chain and updates the state if valid.

**Gas cost**: ~300k gas per step for verification.

### Step 9: Query Workflow State

Query the contract to see current state using Hardhat console:

```bash
npx hardhat console --network sepolia
```

```javascript
const Model = await ethers.getContractFactory("Model");
const model = await Model.attach("0xYOUR_CONTRACT_ADDRESS");

// Get current state hash
const hash = await model.getCurrentHash();
console.log("State Hash:", hash);

// Get last signature
const sig = await model.getLastSignature();
console.log("Last Signature R:", sig[0], "S:", sig[1]);

// Get ciphertext
const ciphertext = await model.getCiphertext();
console.log("Ciphertext:", ciphertext);
```

---

## 6. CLI Reference

### Generator CLI

Usage: `java -jar cli-all.jar [OPTIONS] <bpmnFile> <testCases>`

| Option | Description |
|--------|-------------|
| `--help` or `-h` | Show help message |
| `--deploy` | Deploy smart contract to local node (requires running node at localhost:8545) |
| `--skip-setup` | Skip the trusted setup phase (use existing keys) |
| `--skip-tests` | Only compile and setup, don't run test cases |
| `--from <n>` | Start from test case number n |
| `--contract-address <addr>` | Use existing deployed contract address |

### pycrypto CLI

| Command | Description |
|---------|-------------|
| `python3 cli.py keygen` | Generate random EdDSA key pair |
| `python3 cli.py keygen -p <private_key_hex>` | Derive public key from private key |
| `python3 cli.py hash <preimage_hex> -s <size>` | Compute Pedersen hash (size in bytes) |
| `python3 cli.py batch_hasher` | Interactive batch hashing mode |
| `python3 cli.py sig-gen <private_key_hex> <message_hex>` | Generate EdDSA signature |
| `python3 cli.py sig-verify <public_key_hex> <message_hex> <sig_r_hex> <sig_s_hex>` | Verify signature |

### BPMN Converter

Usage: `python3 bpmn_to_zkwf.py [OPTIONS] <input.bpmn> [output.bpmn]`

| Option | Description |
|--------|-------------|
| `<input.bpmn>` | Input BPMN file (required) |
| `<output.bpmn>` | Output file (optional, defaults to `input_zkwf.bpmn`) |
| `--validate-only` | Only validate BPMN structure, don't convert |
| `--no-validate` | Skip validation and convert directly |

### Hardhat Commands

| Command | Description |
|---------|-------------|
| `npx hardhat compile` | Compile Solidity contracts |
| `npx hardhat test` | Run contract tests |
| `npx hardhat run scripts/deploy.js` | Deploy contracts |
| `npx hardhat run scripts/deploy.js --network sepolia` | Deploy to Sepolia |

---

## 7. Understanding Zero-Knowledge Proofs in zkWF

### What Happens Under the Hood

When you generate a proof in zkWF, here's the complete process:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Proof Generation Pipeline                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. STATE HASHING                                                    │
│     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐        │
│     │ State Vector│     │  Variables   │     │  Randomness │        │
│     │ [1,0,0,0,0] │     │ amount=1000  │     │  1675454832 │        │
│     └──────┬──────┘     └──────┬───────┘     └──────┬──────┘        │
│            │                   │                    │               │
│            └───────────────────┼────────────────────┘               │
│                                ▼                                    │
│                    ┌─────────────────────┐                          │
│                    │   Pedersen Hash     │                          │
│                    │   (SNARK-friendly)  │                          │
│                    └──────────┬──────────┘                          │
│                               ▼                                     │
│                    ┌─────────────────────┐                          │
│                    │ State Hash (256-bit)│                          │
│                    │ 0x12ab34cd56ef...   │                          │
│                    └──────────┬──────────┘                          │
│                               │                                     │
│  2. SIGNATURE                 │                                     │
│                               ▼                                     │
│     ┌─────────────┐     ┌──────────────┐                            │
│     │ Private Key │────→│   EdDSA Sign │                            │
│     │ (participant)│     └──────┬───────┘                           │
│     └─────────────┘            │                                    │
│                                ▼                                    │
│                    ┌─────────────────────┐                          │
│                    │ Signature (R, S)    │                          │
│                    │ R=(x,y), S=scalar   │                          │
│                    └──────────┬──────────┘                          │
│                               │                                     │
│  3. CIRCUIT WITNESS           │                                     │
│                               ▼                                     │
│  ┌──────────────────────────────────────────────────────┐          │
│  │                 Circuit Inputs                        │          │
│  │                                                       │          │
│  │  Public:                    Private:                  │          │
│  │  • Current hash             • Current state           │          │
│  │  • New hash                 • New state               │          │
│  │  • Signature                • Variables               │          │
│  │  • Public key               • Randomness              │          │
│  │                             • Private key (for sig)   │          │
│  └──────────────────────────────────────────────────────┘          │
│                               │                                     │
│  4. PROOF GENERATION          │                                     │
│                               ▼                                     │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              ZoKrates / Groth16 SNARK                 │          │
│  │                                                       │          │
│  │  1. Compute witness (satisfy all constraints)         │          │
│  │  2. FFT on constraint polynomials                     │          │
│  │  3. Compute quotient polynomial                       │          │
│  │  4. Commit to polynomials using elliptic curves       │          │
│  │  5. Generate proof points (a, b, c)                   │          │
│  └──────────────────────────────────────────────────────┘          │
│                               │                                     │
│                               ▼                                     │
│                    ┌─────────────────────┐                          │
│                    │    ZK Proof         │                          │
│                    │  a: G1 point        │                          │
│                    │  b: G2 point        │                          │
│                    │  c: G1 point        │                          │
│                    │  (~200 bytes total) │                          │
│                    └─────────────────────┘                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### The Circuit Logic

The ZoKrates circuit enforces these rules:

1. **Hash Consistency**: `hash(current_state, randomness) == current_hash`
2. **Transition Validity**: The state change follows BPMN rules
3. **Authorization**: Signature is valid for the transitioning participant
4. **New Hash**: `hash(new_state, new_randomness) == new_hash`

```
// Simplified circuit logic (pseudocode)
def main(
    // Public inputs (visible on-chain)
    public field[8] current_hash,
    public field[8] new_hash,
    public field[2] signature_R,
    public field signature_S,
    public field[2] public_key,

    // Private inputs (hidden)
    private field[N] current_state,
    private field[N] new_state,
    private field current_random,
    private field new_random,
    private field[M] variables
) -> bool:

    // 1. Verify current state hashes correctly
    computed_current = pedersen_hash(current_state, current_random, variables)
    assert(computed_current == current_hash)

    // 2. Verify transition is valid
    assert(is_valid_transition(current_state, new_state))

    // 3. Verify signature
    message = hash(current_hash, new_hash)
    assert(eddsa_verify(public_key, signature_R, signature_S, message))

    // 4. Verify new state hashes correctly
    computed_new = pedersen_hash(new_state, new_random, variables)
    assert(computed_new == new_hash)

    return true
```

### What the Proof Guarantees

| Guarantee | What It Means |
|-----------|---------------|
| **Completeness** | If you know a valid transition, you can always create a proof |
| **Soundness** | You cannot create a valid proof for an invalid transition |
| **Zero-Knowledge** | The proof reveals nothing about the private inputs |

### On-Chain Verification

The `Verifier.sol` contract checks the proof using elliptic curve pairings:

```solidity
function verifyTx(Proof memory proof, uint[19] memory input) public view returns (bool) {
    // Check: e(A, B) = e(alpha, beta) * e(sum(inputs*vk), gamma) * e(C, delta)
    // This is the Groth16 verification equation

    // Uses precompiled contracts:
    // - ecAdd (0x06): Add elliptic curve points
    // - ecMul (0x07): Scalar multiplication
    // - ecPairing (0x08): Pairing check

    return pairingCheck(proof.a, proof.b, vk_alpha, vk_beta, ...);
}
```

---

## 8. Troubleshooting

### 1. ZoKrates Compilation Fails

**Symptom**: Error during circuit compilation
```
Error: Undefined symbol 'pedersen_hash'
```

**Solution**: Ensure ZoKrates stdlib is in path:
```bash
export ZOKRATES_STDLIB=./.zokrates/stdlib
```

### 2. Java Version Error

**Symptom**: Gradle build fails
```
Unsupported class file major version 65
```

**Solution**: Install Java 21+:
```bash
# macOS with Homebrew
brew install openjdk@21
export JAVA_HOME=/opt/homebrew/opt/openjdk@21

# Verify
java -version
```

### 3. Proof Generation Takes Too Long

**Symptom**: Proof generation hangs or takes >30 minutes

**Solutions**:
- Reduce workflow complexity (fewer tasks/gateways)
- Use a machine with more RAM (recommend 16GB+)
- Check circuit constraint count (>100k is complex)

### 4. Smart Contract Deployment Fails

**Symptom**: Transaction reverts during deployment
```
Error: insufficient funds for gas
```

**Solution**: Ensure your wallet has enough testnet ETH:
- Sepolia faucet: https://sepoliafaucet.com
- Check balance: `npx hardhat balance --network sepolia`

### 5. Proof Verification Fails On-Chain

**Symptom**: `stepModel()` reverts
```
Error: Transaction reverted without a reason string
```

**Solutions**:
- Verify proof locally first with ZoKrates
- Check public inputs match contract state
- Ensure correct hash order (8 uint256 values)
- Verify signature format

```bash
# Local verification
./.zokrates/bin/zokrates verify
```

### 6. BPMN Parsing Error

**Symptom**: Generator cannot parse BPMN file
```
Error: Invalid BPMN structure
```

**Solutions**:
- Ensure valid XML with BPMN 2.0 namespace
- Check for required `zkp:publicKey` attributes
- Validate with BPMN editor first
- Run converter: `python3 bpmn_to_zkwf.py --validate --input file.bpmn`

### 7. EdDSA Signature Invalid

**Symptom**: Signature verification fails in circuit
```
Error: EdDSA signature verification failed
```

**Solutions**:
- Use correct message format (hash of hashes)
- Ensure private key matches public key
- Check BabyJubJub curve parameters

```bash
# Verify signature offline
python3 cli.py verify --pubkey <key> --sig <sig> --msg <msg>
```

### 8. State Hash Mismatch

**Symptom**: Current hash doesn't match expected
```
Error: State hash mismatch
```

**Solution**: Regenerate hash with same inputs:
```bash
python3 cli.py hash --state "1,0,0,0" --random "1675454832" --vars ""
```

### 9. Gas Estimation Too High

**Symptom**: Deployment costs >5M gas

**Solutions**:
- Simplify workflow (fewer states)
- Use zkSync Era for lower costs
- Optimize circuit (contact maintainers)

### 10. Resetting Everything

If things are broken, clean start:

```bash
# Clean generator
cd generator
./gradlew clean
rm -rf output/*

# Rebuild
./gradlew cli:shadowJar

# Clean verifier
cd ../verifier
rm -rf artifacts/ cache/
npm run compile
```

---

## 9. Next Steps & Resources

### What to Try Next

1. **Modify the Example Workflow**
   - Add more participants
   - Include parallel gateways
   - Add message flows between participants

2. **Integrate with Your Application**
   - Build a frontend that calls the contract
   - Create a participant wallet app
   - Implement off-chain coordination

3. **Deploy to Production**
   - Audit the smart contracts
   - Run trusted setup ceremony
   - Deploy to Ethereum mainnet or zkSync

4. **Explore Advanced Features**
   - Variable encryption/decryption
   - Multi-party computation for key management
   - Cross-workflow interactions

### External Resources

**ZoKrates**
- Documentation: https://zokrates.github.io/
- GitHub: https://github.com/Zokrates/ZoKrates
- Tutorial: https://zokrates.github.io/gettingstarted.html

**BPMN 2.0**
- Specification: https://www.omg.org/spec/BPMN/2.0/
- bpmn-js: https://bpmn.io/toolkit/bpmn-js/

**Zero-Knowledge Proofs**
- zkSNARKs Explained: https://z.cash/technology/zksnarks/
- Groth16 Paper: https://eprint.iacr.org/2016/260
- BabyJubJub: https://eips.ethereum.org/EIPS/eip-2494

**Hardhat**
- Documentation: https://hardhat.org/docs
- Testing: https://hardhat.org/hardhat-runner/docs/guides/test-contracts

**zkSync Era**
- Documentation: https://era.zksync.io/docs/
- Deployment: https://era.zksync.io/docs/tools/hardhat/

### Getting Help

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Check AGENTS.md for developer guidelines
- **Architecture**: See ARM-MIGRATION.md for platform details

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│                     zkWF Quick Reference                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  BUILD                                                               │
│  ─────                                                               │
│  cd generator && ./gradlew cli:shadowJar                            │
│  cd editor && npm install && npm run dev                            │
│  cd verifier && npm install                                         │
│                                                                      │
│  GENERATE & TEST                                                     │
│  ──────────────                                                      │
│  java -jar cli-all.jar workflow.bpmn testCases.json                 │
│  java -jar cli-all.jar --skip-tests workflow.bpmn testCases.json   │
│                                                                      │
│  DEPLOY                                                              │
│  ──────                                                              │
│  npx hardhat compile                                                 │
│  npx hardhat run scripts/deploy.js --network sepolia                │
│                                                                      │
│  CRYPTO                                                              │
│  ──────                                                              │
│  python3 cli.py keygen                                              │
│  python3 cli.py sig-gen <privkey_hex> <msg_hex>                     │
│                                                                      │
│  CONVERT BPMN                                                        │
│  ────────────                                                        │
│  python3 bpmn_to_zkwf.py input.bpmn output.bpmn                     │
│                                                                      │
│  VERIFY                                                              │
│  ──────                                                              │
│  ./.zokrates/bin/zokrates verify                                    │
│                                                                      │
│  FILES                                                               │
│  ─────                                                               │
│  Circuit:    generator/root.zok                                     │
│  Compiled:   generator/out                                          │
│  Verifier:   verifier/contracts/verifier.sol                        │
│  State:      verifier/contracts/model.sol                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

**Congratulations!** You now understand how zkWF enables privacy-preserving workflow verification on blockchain. The combination of BPMN modeling, zero-knowledge proofs, and smart contracts creates a powerful system for multi-party collaboration without sacrificing confidentiality.

Happy building!
