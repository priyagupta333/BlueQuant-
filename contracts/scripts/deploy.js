const { ethers } = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
  console.log("Deploying Carbon Credit contracts...");

  // Get the deployer account
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);
  console.log("Account balance:", (await ethers.provider.getBalance(deployer.address)).toString());

  // Deploy CarbonCreditToken
  console.log("\nDeploying CarbonCreditToken...");
  const CarbonCreditToken = await ethers.getContractFactory("CarbonCreditToken");
  const carbonToken = await CarbonCreditToken.deploy();
  await carbonToken.waitForDeployment();
  const carbonTokenAddress = await carbonToken.getAddress();
  console.log("CarbonCreditToken deployed to:", carbonTokenAddress);

  // Deploy CarbonCreditMarketplace
  console.log("\nDeploying CarbonCreditMarketplace...");
  const CarbonCreditMarketplace = await ethers.getContractFactory("CarbonCreditMarketplace");
  const marketplace = await CarbonCreditMarketplace.deploy(carbonTokenAddress);
  await marketplace.waitForDeployment();
  const marketplaceAddress = await marketplace.getAddress();
  console.log("CarbonCreditMarketplace deployed to:", marketplaceAddress);

  // Save deployment addresses
  const deploymentInfo = {
    network: hre.network.name,
    carbonToken: carbonTokenAddress,
    marketplace: marketplaceAddress,
    deployer: deployer.address,
    deployedAt: new Date().toISOString()
  };

  console.log("\n=== Deployment Summary ===");
  console.log(JSON.stringify(deploymentInfo, null, 2));

  // Ensure deployments directory exists
  const deploymentsDir = path.join(__dirname, '..', 'deployments');
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  // Save to file
  const deploymentFile = path.join(deploymentsDir, `${hre.network.name}.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));

  console.log(`\nDeployment info saved to deployments/${hre.network.name}.json`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });