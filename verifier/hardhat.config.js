require("@nomicfoundation/hardhat-toolbox");
require("@matterlabs/hardhat-zksync-deploy");
require("@matterlabs/hardhat-zksync-solc");
require("@matterlabs/hardhat-zksync-verify");
require("@matterlabs/hardhat-zksync-node");

// Load environment variables if .env file exists
const dotenv = require("dotenv");
dotenv.config();

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x0000000000000000000000000000000000000000000000000000000000000001";
const INFURA_PROJECT_ID = process.env.INFURA_PROJECT_ID || "";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  // Default network for standard EVM chains
  defaultNetwork: "hardhat",

  networks: {
    // Local development (Hardhat's built-in network)
    hardhat: {
      chainId: 31337,
    },

    // Local Ganache (for backward compatibility with Truffle)
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,
    },

    // Ethereum Sepolia testnet
    sepolia: {
      url: `https://sepolia.infura.io/v3/${INFURA_PROJECT_ID}`,
      accounts: [PRIVATE_KEY],
      chainId: 11155111,
    },

    // Ethereum mainnet
    mainnet: {
      url: `https://mainnet.infura.io/v3/${INFURA_PROJECT_ID}`,
      accounts: [PRIVATE_KEY],
      chainId: 1,
    },

    // ================================
    // zkSync Networks
    // ================================

    // zkSync Era Mainnet
    zkSyncMainnet: {
      url: "https://mainnet.era.zksync.io",
      ethNetwork: "mainnet",
      zksync: true,
      verifyURL: "https://zksync2-mainnet-explorer.zksync.io/contract_verification",
      accounts: [PRIVATE_KEY],
    },

    // zkSync Era Testnet (Sepolia)
    zkSyncTestnet: {
      url: "https://sepolia.era.zksync.dev",
      ethNetwork: "sepolia",
      zksync: true,
      verifyURL: "https://explorer.sepolia.era.zksync.dev/contract_verification",
      accounts: [PRIVATE_KEY],
    },

    // zkSync Era Local (for local testing with dockerized zkSync)
    zkSyncLocal: {
      url: "http://localhost:3050",
      ethNetwork: "http://localhost:8545",
      zksync: true,
      accounts: [PRIVATE_KEY],
    },

    // Local anvil-zksync node (for benchmarking with real zkSync gas)
    anvilZkSync: {
      url: "http://127.0.0.1:8011",
      ethNetwork: "",
      zksync: true,
      // Rich wallet #0 from anvil-zksync default accounts
      accounts: [
        "0x7726827caac94a7f9e1b160f7ea819f172f7b6f9d2a97f992c38edeab82d4110",
      ],
    },
  },

  // Solidity compiler settings (for standard EVM)
  solidity: {
    version: "0.8.0",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },

  // zkSolc compiler settings (for zkSync)
  zksolc: {
    version: "1.5.0",
    settings: {
      // Enable optimization for smaller bytecode
      optimizer: {
        enabled: true,
        mode: "3",
      },
    },
  },

  // Path configuration
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache-hardhat",
    artifacts: "./artifacts-hardhat",
    // zkSync specific paths
    zksync: {
      artifacts: "./artifacts-zk",
      cache: "./cache-zk",
    },
  },

  // Etherscan verification (for standard EVM chains)
  etherscan: {
    apiKey: {
      sepolia: process.env.ETHERSCAN_API_KEY || "",
      mainnet: process.env.ETHERSCAN_API_KEY || "",
    },
  },
};
