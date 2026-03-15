/**
 * Deploy and execute t4_zkp workflow on Hardhat local network.
 * Deploys Model contract, then submits both ZK proofs via stepModel().
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

function loadProof(filename) {
  const raw = JSON.parse(fs.readFileSync(path.join(__dirname, "../../generator", filename), "utf8"));
  const { inputs, proof } = raw.proof;
  return {
    inputs,
    a: proof.a,
    b: proof.b,
    c: proof.c,
    newState: raw.state,
  };
}

function inputsToHash(inputs, offset) {
  // inputs[offset..offset+7] are the 8 uint32 hash words, zero-padded to 32 bytes
  return {
    a: BigInt(inputs[offset + 0]),
    b: BigInt(inputs[offset + 1]),
    c: BigInt(inputs[offset + 2]),
    d: BigInt(inputs[offset + 3]),
    e: BigInt(inputs[offset + 4]),
    f: BigInt(inputs[offset + 5]),
    g: BigInt(inputs[offset + 6]),
    h: BigInt(inputs[offset + 7]),
  };
}

function inputsToSig(inputs) {
  // inputs[8], inputs[9] = R[0], R[1]; inputs[10] = S
  return {
    R: [BigInt(inputs[8]), BigInt(inputs[9])],
    S: BigInt(inputs[10]),
  };
}

function formatHash(hash) {
  return [hash.a, hash.b, hash.c, hash.d, hash.e, hash.f, hash.g, hash.h]
    .map(v => "0x" + v.toString(16).padStart(8, "0"))
    .join(" ");
}

async function main() {
  const [deployer] = await hre.ethers.getSigners();

  console.log("============================================================");
  console.log("  zkWF t4_zkp.bpmn — Deploy & Execute on Hardhat Network");
  console.log("============================================================");
  console.log(`Network      : ${hre.network.name} (chainId ${hre.network.config.chainId})`);
  console.log(`Deployer     : ${deployer.address}`);
  const balanceBefore = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`Balance      : ${hre.ethers.formatEther(balanceBefore)} ETH`);
  console.log();

  // Load both proof files
  const proof1 = loadProof("stateProof1.json");
  const proof2 = loadProof("stateProof2.json");

  // Initial hash = inputs[0..7] of proof1 (what was on-chain before step 1)
  const initialHash = inputsToHash(proof1.inputs, 0);

  console.log("--- Initial State ---");
  const rawTestCases = fs.readFileSync(
    path.join(__dirname, "../../models/unit_tests/t4_zkp.json"), "utf8"
  ).replace(/,\s*([}\]])/g, "$1"); // strip trailing commas
  console.log(`State vector : [${JSON.parse(rawTestCases)[0].initialState.stateVector.join(", ")}]`);
  console.log(`Initial hash : ${formatHash(initialHash)}`);
  console.log();

  // ── Deploy ──────────────────────────────────────────────────────────────
  console.log(">>> Deploying Model contract...");
  const t0 = Date.now();
  const Model = await hre.ethers.getContractFactory("Model");
  const model = await Model.deploy(initialHash, "");
  await model.waitForDeployment();
  const deployReceipt = await model.deploymentTransaction().wait();
  const contractAddress = await model.getAddress();
  console.log(`    Contract address : ${contractAddress}`);
  console.log(`    Gas used         : ${deployReceipt.gasUsed.toLocaleString()}`);
  console.log(`    Deploy time      : ${((Date.now() - t0) / 1000).toFixed(2)}s`);
  console.log();

  // ── Step 1 ───────────────────────────────────────────────────────────────
  const newHash1  = inputsToHash(proof1.inputs, 11);
  const sig1      = inputsToSig(proof1.inputs);
  const zkProof1  = { a: proof1.a, b: proof1.b, c: proof1.c };

  console.log("--- Step 1: Task1 fires → parallel split → [2,1] ---");
  console.log(`  New state vector   : [${proof1.newState.stateVector.join(", ")}]`);
  console.log(`  New hash           : ${formatHash(newHash1)}`);
  console.log(`  Sig R              : [${sig1.R.map(v => "0x" + v.toString(16).slice(0, 12) + "...").join(", ")}]`);
  console.log(`  Sig S              : 0x${sig1.S.toString(16).slice(0, 12)}...`);
  console.log(`  Proof a            : [${proof1.a.map(v => v.slice(0, 10) + "...").join(", ")}]`);
  console.log(`  Proof b[0]         : [${proof1.b[0].map(v => v.slice(0, 10) + "...").join(", ")}]`);
  console.log(`  Proof c            : [${proof1.c.map(v => v.slice(0, 10) + "...").join(", ")}]`);

  const t1 = Date.now();
  const tx1 = await model.stepModel(newHash1, "", sig1, zkProof1);
  const receipt1 = await tx1.wait();
  console.log(`  ✅ stepModel() OK — gas: ${receipt1.gasUsed.toLocaleString()}, time: ${((Date.now() - t1) / 1000).toFixed(2)}s`);
  console.log();

  // Query on-chain state after step 1
  const onChainHash1 = await model.getCurrentHash();
  const onChainSig1  = await model.getLastSignature();
  const onChainCt1   = await model.getCiphertext();
  console.log("  On-chain state after step 1:");
  console.log(`    getCurrentHash() : [${[...onChainHash1].map(v => "0x" + v.toString(16).padStart(8,"0")).join(" ")}]`);
  console.log(`    getLastSignature(): R=[${onChainSig1[0].map(v => "0x" + v.toString(16).slice(0,12)+"...").join(", ")}], S=0x${onChainSig1[1].toString(16).slice(0,12)}...`);
  console.log(`    getCiphertext()  : "${onChainCt1}"`);
  console.log();

  // ── Step 2 ───────────────────────────────────────────────────────────────
  const newHash2  = inputsToHash(proof2.inputs, 11);
  const sig2      = inputsToSig(proof2.inputs);
  const zkProof2  = { a: proof2.a, b: proof2.b, c: proof2.c };

  console.log("--- Step 2: Task2 completes → [2,2] ---");
  console.log(`  New state vector   : [${proof2.newState.stateVector.join(", ")}]`);
  console.log(`  New hash           : ${formatHash(newHash2)}`);
  console.log(`  Sig R              : [${sig2.R.map(v => "0x" + v.toString(16).slice(0, 12) + "...").join(", ")}]`);
  console.log(`  Sig S              : 0x${sig2.S.toString(16).slice(0, 12)}...`);
  console.log(`  Proof a            : [${proof2.a.map(v => v.slice(0, 10) + "...").join(", ")}]`);
  console.log(`  Proof b[0]         : [${proof2.b[0].map(v => v.slice(0, 10) + "...").join(", ")}]`);
  console.log(`  Proof c            : [${proof2.c.map(v => v.slice(0, 10) + "...").join(", ")}]`);

  const t2 = Date.now();
  const tx2 = await model.stepModel(newHash2, "", sig2, zkProof2);
  const receipt2 = await tx2.wait();
  console.log(`  ✅ stepModel() OK — gas: ${receipt2.gasUsed.toLocaleString()}, time: ${((Date.now() - t2) / 1000).toFixed(2)}s`);
  console.log();

  // Query final on-chain state
  const onChainHash2 = await model.getCurrentHash();
  const onChainSig2  = await model.getLastSignature();
  const onChainCt2   = await model.getCiphertext();
  console.log("  On-chain state after step 2 (final):");
  console.log(`    getCurrentHash() : [${[...onChainHash2].map(v => "0x" + v.toString(16).padStart(8,"0")).join(" ")}]`);
  console.log(`    getLastSignature(): R=[${onChainSig2[0].map(v => "0x" + v.toString(16).slice(0,12)+"...").join(", ")}], S=0x${onChainSig2[1].toString(16).slice(0,12)}...`);
  console.log(`    getCiphertext()  : "${onChainCt2}"`);
  console.log();

  // ── Summary ──────────────────────────────────────────────────────────────
  const balanceAfter = await hre.ethers.provider.getBalance(deployer.address);
  const totalGas = deployReceipt.gasUsed + receipt1.gasUsed + receipt2.gasUsed;

  console.log("============================================================");
  console.log("  Summary");
  console.log("============================================================");
  console.log(`  Contract address   : ${contractAddress}`);
  console.log(`  Workflow           : t4_zkp.bpmn`);
  console.log(`  Steps executed     : 2 / 2`);
  console.log(`  Gas — deploy       : ${deployReceipt.gasUsed.toLocaleString()}`);
  console.log(`  Gas — step 1       : ${receipt1.gasUsed.toLocaleString()}`);
  console.log(`  Gas — step 2       : ${receipt2.gasUsed.toLocaleString()}`);
  console.log(`  Gas — total        : ${totalGas.toLocaleString()}`);
  console.log(`  ETH spent          : ${hre.ethers.formatEther(balanceBefore - balanceAfter)} ETH`);
  console.log(`  Final state vector : [2, 2]  (both end-events reached)`);
  console.log(`  Final hash         : ${formatHash(newHash2)}`);
  console.log("============================================================");
  console.log("  All ZK proofs verified on-chain ✅");
  console.log("============================================================");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
