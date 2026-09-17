# Requirements Document

## Introduction

The Blockchain Smart Contracts module provides the decentralized infrastructure for the Carbon Credit Marketplace. Built on Ethereum using Solidity and Hardhat, this module implements ERC20-based carbon credit tokens and a marketplace contract for trading credits through tenders and direct listings. The system integrates with the Django backend via Web3.py for seamless blockchain operations.

## Glossary

- **Smart Contract**: Self-executing code deployed on the Ethereum blockchain
- **ERC20**: Standard interface for fungible tokens on Ethereum
- **CCT (Carbon Credit Token)**: The ERC20 token representing carbon credits
- **Hardhat**: Ethereum development environment for compiling, testing, and deploying contracts
- **Web3.py**: Python library for interacting with Ethereum blockchain
- **Tender**: A request for carbon credit proposals from corporates
- **Proposal**: An NGO's response to a tender offering credits at a specific price
- **Direct Listing**: A marketplace listing for immediate credit purchase
- **Gas**: Transaction fee paid for blockchain operations
- **Minting**: Creating new tokens and assigning them to an address
- **Burning**: Permanently destroying tokens to reduce supply

## Requirements

### Requirement 1: Carbon Credit Token (ERC20)

**User Story:** As the system, I want to issue carbon credits as ERC20 tokens, so that credits can be tracked, transferred, and traded on the blockchain.

#### Acceptance Criteria

1. THE Contract SHALL implement the ERC20 standard interface with name "Carbon Credit Token" and symbol "CCT"
2. THE Contract SHALL support minting of new tokens by the contract owner only
3. THE Contract SHALL support burning of tokens by token holders
4. THE Contract SHALL track project-specific credit balances for each user
5. THE Contract SHALL emit events for all minting, burning, and transfer operations
6. THE Contract SHALL support pausing and unpausing of all token operations
7. THE Contract SHALL maintain a configurable price per credit for direct purchases

### Requirement 2: Project Registration

**User Story:** As an admin, I want to register carbon credit projects on the blockchain, so that credits can be associated with verified projects.

#### Acceptance Criteria

1. WHEN a project is registered, THE Contract SHALL assign a unique project ID
2. THE Contract SHALL store project name, NGO address, and estimated credits
3. THE Contract SHALL track total credits issued per project
4. THE Contract SHALL maintain a list of projects associated with each NGO address
5. THE Contract SHALL emit a ProjectRegistered event with project details
6. THE Contract SHALL support project deactivation by the owner
7. THE Contract SHALL prevent minting credits for inactive projects

### Requirement 3: Credit Minting and Issuance

**User Story:** As the system, I want to mint carbon credits for approved projects, so that NGOs receive tokens representing their verified carbon sequestration.

#### Acceptance Criteria

1. WHEN credits are minted, THE Contract SHALL require a valid active project ID
2. THE Contract SHALL update the recipient's total balance and project-specific balance
3. THE Contract SHALL update the project's total credits issued count
4. THE Contract SHALL emit a CreditsMinted event with recipient, amount, and project details
5. THE Contract SHALL only allow the contract owner to mint credits
6. THE Contract SHALL reject minting requests with zero amount
7. THE Contract SHALL support minting to any valid Ethereum address

### Requirement 4: Credit Transfer with Project Tracking

**User Story:** As a credit holder, I want to transfer credits to other users while maintaining project association, so that credit provenance is preserved.

#### Acceptance Criteria

1. WHEN credits are transferred, THE Contract SHALL verify sufficient project-specific balance
2. THE Contract SHALL update both sender and recipient project-specific balances
3. THE Contract SHALL emit a CreditsTransferred event with transfer details
4. THE Contract SHALL support owner-initiated transfers (transferCreditsFrom)
5. THE Contract SHALL reject transfers with zero amount
6. THE Contract SHALL maintain accurate total balances after transfers
7. THE Contract SHALL work correctly when contract is not paused

### Requirement 5: Direct Credit Purchase

**User Story:** As a buyer, I want to purchase carbon credits directly with ETH, so that I can acquire credits without going through the tender process.

#### Acceptance Criteria

1. WHEN ETH is sent to purchaseCredits, THE Contract SHALL calculate credits based on pricePerCredit
2. THE Contract SHALL mint credits to the buyer's address
3. THE Contract SHALL update project-specific balances for the buyer
4. THE Contract SHALL reject purchases with insufficient ETH for minimum credits
5. THE Contract SHALL only allow purchases for active projects
6. THE Contract SHALL allow the owner to update the price per credit
7. THE Contract SHALL allow the owner to withdraw accumulated ETH

### Requirement 6: Marketplace Tender System

**User Story:** As a corporate user, I want to create tenders for carbon credits, so that NGOs can compete to provide the best offers.

#### Acceptance Criteria

1. WHEN a tender is created, THE Contract SHALL assign a unique tender ID
2. THE Contract SHALL store title, description, credits required, max price, and deadline
3. THE Contract SHALL set initial tender status to Open
4. THE Contract SHALL track tenders created by each corporate address
5. THE Contract SHALL emit a TenderCreated event with tender details
6. THE Contract SHALL calculate deadline based on duration in days
7. THE Contract SHALL reject tenders with zero credits or zero max price

### Requirement 7: Proposal Submission

**User Story:** As an NGO, I want to submit proposals for open tenders, so that I can offer my carbon credits to corporate buyers.

#### Acceptance Criteria

1. WHEN a proposal is submitted, THE Contract SHALL verify the tender is open
2. THE Contract SHALL verify the tender deadline has not passed
3. THE Contract SHALL verify offered credits meet or exceed tender requirements
4. THE Contract SHALL verify price per credit does not exceed tender maximum
5. THE Contract SHALL verify the NGO has sufficient project credits
6. THE Contract SHALL emit a ProposalSubmitted event with proposal details
7. THE Contract SHALL track proposals for each tender and each NGO

### Requirement 8: Tender Award and Settlement

**User Story:** As a corporate user, I want to award a tender to a winning proposal, so that credits are transferred and payment is made.

#### Acceptance Criteria

1. WHEN a tender is awarded, THE Contract SHALL verify the caller is the tender creator
2. THE Contract SHALL verify the tender is still open
3. THE Contract SHALL verify the proposal belongs to the tender
4. THE Contract SHALL transfer credits from NGO to corporate
5. THE Contract SHALL transfer payment (minus marketplace fee) to NGO
6. THE Contract SHALL update tender status to Awarded
7. THE Contract SHALL reject all other proposals for the tender
8. THE Contract SHALL emit TenderAwarded and CreditsTraded events

### Requirement 9: Direct Marketplace Listings

**User Story:** As an NGO, I want to create direct listings for my carbon credits, so that buyers can purchase immediately without tenders.

#### Acceptance Criteria

1. WHEN a listing is created, THE Contract SHALL verify sufficient project credits
2. THE Contract SHALL store seller, project ID, credits amount, and price
3. THE Contract SHALL set listing as active
4. THE Contract SHALL assign a unique listing ID
5. THE Contract SHALL reject listings with zero credits or zero price
6. THE Contract SHALL allow partial purchases from listings
7. THE Contract SHALL deactivate listings when all credits are sold

### Requirement 10: Listing Purchase

**User Story:** As a buyer, I want to purchase credits from direct listings, so that I can acquire specific project credits immediately.

#### Acceptance Criteria

1. WHEN purchasing from a listing, THE Contract SHALL verify the listing is active
2. THE Contract SHALL verify sufficient payment is provided
3. THE Contract SHALL transfer credits from seller to buyer
4. THE Contract SHALL transfer payment (minus fee) to seller
5. THE Contract SHALL update listing credits amount
6. THE Contract SHALL refund excess payment to buyer
7. THE Contract SHALL emit CreditsTraded event with transaction details

### Requirement 11: Marketplace Fee Management

**User Story:** As the platform owner, I want to collect marketplace fees on transactions, so that the platform can sustain operations.

#### Acceptance Criteria

1. THE Contract SHALL apply a configurable fee percentage to all trades
2. THE Contract SHALL default to 2.5% (250 basis points) marketplace fee
3. THE Contract SHALL cap maximum fee at 10% (1000 basis points)
4. THE Contract SHALL allow owner to update fee percentage
5. THE Contract SHALL emit MarketplaceFeeUpdated event on fee changes
6. THE Contract SHALL allow owner to withdraw accumulated fees
7. THE Contract SHALL calculate fees correctly for all transaction types

### Requirement 12: Contract Security and Access Control

**User Story:** As the platform, I want robust security controls, so that the contracts are protected from unauthorized access and attacks.

#### Acceptance Criteria

1. THE Contract SHALL implement Ownable pattern for administrative functions
2. THE Contract SHALL implement Pausable pattern for emergency stops
3. THE Contract SHALL implement ReentrancyGuard for payment functions
4. THE Contract SHALL restrict minting to owner only
5. THE Contract SHALL restrict fee updates to owner only
6. THE Contract SHALL restrict pause/unpause to owner only
7. THE Contract SHALL validate all inputs and reject invalid data

### Requirement 13: Web3 Backend Integration

**User Story:** As the Django backend, I want to interact with smart contracts via Web3.py, so that blockchain operations are seamless.

#### Acceptance Criteria

1. THE System SHALL connect to local Hardhat network or configured RPC endpoint
2. THE System SHALL load contract ABIs from compiled artifacts
3. THE System SHALL sign transactions with configured private key
4. THE System SHALL handle transaction receipts and parse events
5. THE System SHALL support automatic gas estimation
6. THE System SHALL persist blockchain configuration in database
7. THE System SHALL provide fallback to simple blockchain when contracts unavailable

### Requirement 14: Contract Deployment and Configuration

**User Story:** As a developer, I want automated contract deployment, so that the system can be set up quickly in different environments.

#### Acceptance Criteria

1. THE System SHALL compile contracts with Hardhat and Solidity 0.8.20
2. THE System SHALL deploy CarbonCreditToken contract first
3. THE System SHALL deploy CarbonCreditMarketplace with token address
4. THE System SHALL save deployment addresses to configuration
5. THE System SHALL support deployment to localhost, testnet, and mainnet
6. THE System SHALL generate deployment artifacts with ABIs
7. THE System SHALL support contract verification on Etherscan

### Requirement 15: Event Logging and Monitoring

**User Story:** As an administrator, I want comprehensive event logging, so that all blockchain activities can be monitored and audited.

#### Acceptance Criteria

1. THE Contract SHALL emit events for all state-changing operations
2. THE Contract SHALL include indexed parameters for efficient filtering
3. THE System SHALL parse and store events in database
4. THE System SHALL provide blockchain explorer functionality
5. THE System SHALL log transaction hashes for all operations
6. THE System SHALL track transaction status (pending, confirmed, failed)
7. THE System SHALL support querying historical transactions
