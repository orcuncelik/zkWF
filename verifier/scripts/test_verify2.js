const hre = require("hardhat");
const fs = require("fs"), path = require("path");
async function main() {
  const Model = await hre.ethers.getContractFactory("Model");
  const model = await Model.deploy({a:0,b:0,c:0,d:0,e:0,f:0,g:0,h:0}, "");
  await model.waitForDeployment();

  for (const name of ["proof1.json", "proof2.json"]) {
    const raw = JSON.parse(fs.readFileSync(path.join(__dirname, "../../generator", name)));
    const proof = { a: raw.proof.a, b: raw.proof.b, c: raw.proof.c };
    const inputs = raw.inputs.map(v => BigInt(v));
    const result = await model.verifyTx(proof, inputs.slice(0, 19));
    console.log(`verifyTx(${name}): ${result}`);
  }
}
main().then(()=>process.exit(0)).catch(e=>{console.error(e.message);process.exit(1);});
