const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const Model = await hre.ethers.getContractFactory("Model");
  const model = await Model.deploy({a:0,b:0,c:0,d:0,e:0,f:0,g:0,h:0}, "");
  await model.waitForDeployment();

  const raw = JSON.parse(fs.readFileSync(path.join(__dirname, "../../generator/proof1.json"), "utf8"));
  const { inputs, proof } = raw;

  const proofStruct = { a: proof.a, b: proof.b, c: proof.c };
  const inputsBI = inputs.map(v => BigInt(v));

  console.log("inputs[0]:", "0x"+inputsBI[0].toString(16));
  console.log("proof.a:", proof.a);
  console.log("proof.b:", JSON.stringify(proof.b));
  console.log("proof.c:", proof.c);

  const result = await model.verifyTx(proofStruct, inputsBI.slice(0, 19));
  console.log("verifyTx result:", result);
}
main().then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1);});
