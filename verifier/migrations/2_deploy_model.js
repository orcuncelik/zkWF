const Model = artifacts.require("Model");

module.exports = function (deployer) {
  // Deploy with initial hash (8 values) and empty ciphertext
  const initialHash = {
    a: 0,
    b: 0,
    c: 0,
    d: 0,
    e: 0,
    f: 0,
    g: 0,
    h: 0
  };
  const initialCiphertext = "";

  deployer.deploy(Model, initialHash, initialCiphertext);
};
