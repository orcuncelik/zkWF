const hre = require("hardhat");
const fs = require("fs"), path = require("path");
async function main() {
  const code = `pragma solidity ^0.8.0;
contract PairingTest {
    function testTrivial() public view returns (bool) {
        uint[12] memory input;
        input[0] = 1; input[1] = 2;
        input[2] = 11559732032986387107991004021392285783925812861821192530917403151452391805634;
        input[3] = 10857046999023057135944570762232829481370756359578518086990519993285655852781;
        input[4] = 4082367875863433681332203403145435568316851327593401208105741076214120093531;
        input[5] = 8495653923123431417604973247489272438418190587263600148770280649306958101930;
        input[6] = 1;
        input[7] = 21888242871839275222246405745257275088696311157297823662689037894645226208581;
        input[8] = 11559732032986387107991004021392285783925812861821192530917403151452391805634;
        input[9] = 10857046999023057135944570762232829481370756359578518086990519993285655852781;
        input[10] = 4082367875863433681332203403145435568316851327593401208105741076214120093531;
        input[11] = 8495653923123431417604973247489272438418190587263600148770280649306958101930;
        uint[1] memory out;
        assembly {
            let ok := staticcall(gas(), 8, input, 0x180, out, 0x20)
            if iszero(ok) { revert(0, 0) }
        }
        return out[0] == 1;
    }
}`;
  fs.writeFileSync(path.join(__dirname, "../contracts/PairingTest.sol"), code);
  await hre.run("compile", { quiet: true });
  const PT = await hre.ethers.getContractFactory("PairingTest");
  const pt = await PT.deploy();
  await pt.waitForDeployment();
  const result = await pt.testTrivial();
  console.log("Trivial ecPairing precompile test (should be true):", result);
}
main().then(()=>process.exit(0)).catch(e=>{console.error(e.message||e);process.exit(1);});
