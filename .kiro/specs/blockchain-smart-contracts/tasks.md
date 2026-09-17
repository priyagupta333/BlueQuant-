# Implementation Plan: Blockchain Smart Contracts

## Overview

This implementation plan breaks down the Blockchain Smart Contracts module into discrete, manageable tasks. The system will be built using Solidity 0.8.20 with Hardhat for development, testing, and deployment. The Django backend integrates via Web3.py through a service layer. Tasks are organized to build core token functionality first, then add marketplace features and backend integration.

## Tasks

- [x] 1. Set up Hardhat project structure and configuration
  - Create Hardhat project with proper folder structure
  - Configure Solidity compiler version 0.8.20 with optimizer
  - Set up network configurations for localhost, testnet, and mainnet
  - Install OpenZeppelin contracts dependency
  - Create package.json with build and deploy scripts
  - _Requirements: 14.1, 14.5_

- [x] 1.1 Write configuration tests
  - **Test 1: Hardhat Configuration**
  - **Validates: Requirements 14.1**

- [x] 2. Implement CarbonCreditToken contract
  - [x] 2.1 Create ERC20 token with base functionality
    - Implement ERC20 inheritance with name "Carbon Credit Token" and symbol "CCT"
    - Add Ownable for access control
    - Add Pausable for emergency stops
    - Add ERC20Burnable for token burning
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [x] 2.2 Write unit tests for ERC20 base functionality
    - **Test 2: Token Name and Symbol**
    - **Test 3: Pause and Unpause**
    - **Validates: Requirements 1.1, 1.6**

  - [x] 2.3 Implement project registration system
    - Create Project struct with id, name, ngo, credits, status
    - Implement registerProject function (owner only)
    - Add project tracking mappings (projects, userProjects)
    - Emit ProjectRegistered event
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.4 Write unit tests for project registration
    - **Test 4: Project Registration**
    - **Test 5: Project ID Uniqueness**
    - **Validates: Requirements 2.1, 2.5**

  - [x] 2.5 Implement credit minting with project tracking
    - Create mintCredits function (owner only)
    - Update project-specific balances (userProjectCredits)
    - Update project totalCreditsIssued
    - Emit CreditsMinted event
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 2.6 Write unit tests for credit minting
    - **Test 6: Mint Credits Success**
    - **Test 7: Mint Rejects Inactive Project**
    - **Test 8: Mint Rejects Zero Amount**
    - **Validates: Requirements 3.1, 3.5, 3.6**

  - [x] 2.7 Implement credit transfer with project tracking
    - Create transferCredits function for self-transfers
    - Create transferCreditsFrom for owner-initiated transfers
    - Update sender and recipient project balances
    - Emit CreditsTransferred event
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 2.8 Write unit tests for credit transfers
    - **Test 9: Transfer Credits Success**
    - **Test 10: Transfer Rejects Insufficient Balance**
    - **Test 11: TransferFrom by Owner**
    - **Validates: Requirements 4.1, 4.4, 4.5**

  - [x] 2.9 Implement direct credit purchase
    - Create purchaseCredits payable function
    - Calculate credits based on pricePerCredit
    - Implement updatePricePerCredit (owner only)
    - Implement withdraw function (owner only)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 2.10 Write unit tests for direct purchase
    - **Test 12: Purchase Credits with ETH**
    - **Test 13: Purchase Rejects Insufficient ETH**
    - **Test 14: Owner Withdraw**
    - **Validates: Requirements 5.1, 5.4, 5.7**

- [x] 3. Checkpoint - Ensure CarbonCreditToken contract is complete
  - Compile contract without errors
  - Run all unit tests
  - Verify gas usage is reasonable

- [x] 4. Implement CarbonCreditMarketplace contract
  - [x] 4.1 Create marketplace base with security features
    - Implement Ownable, Pausable, ReentrancyGuard inheritance
    - Add reference to CarbonCreditToken contract
    - Set up marketplace fee configuration
    - _Requirements: 11.1, 11.2, 11.3, 12.1, 12.2, 12.3_

  - [x] 4.2 Write unit tests for marketplace base
    - **Test 15: Marketplace Initialization**
    - **Test 16: Fee Configuration**
    - **Validates: Requirements 11.1, 11.2**

  - [x] 4.3 Implement tender creation system
    - Create Tender struct with all required fields
    - Implement createTender function
    - Add tender tracking mappings
    - Emit TenderCreated event
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 4.4 Write unit tests for tender creation
    - **Test 17: Create Tender Success**
    - **Test 18: Tender Rejects Zero Credits**
    - **Test 19: Tender Deadline Calculation**
    - **Validates: Requirements 6.1, 6.6, 6.7**

  - [x] 4.5 Implement proposal submission system
    - Create Proposal struct with all required fields
    - Implement submitProposal function with validations
    - Add proposal tracking mappings
    - Emit ProposalSubmitted event
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x] 4.6 Write unit tests for proposal submission
    - **Test 20: Submit Proposal Success**
    - **Test 21: Proposal Rejects Closed Tender**
    - **Test 22: Proposal Rejects Expired Tender**
    - **Test 23: Proposal Rejects Insufficient Credits**
    - **Validates: Requirements 7.1, 7.2, 7.5**

  - [x] 4.7 Implement tender award and settlement
    - Implement awardTender function with validations
    - Transfer credits from NGO to corporate
    - Transfer payment (minus fee) to NGO
    - Update tender and proposal statuses
    - Reject other proposals
    - Emit TenderAwarded and CreditsTraded events
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [x] 4.8 Write unit tests for tender award
    - **Test 24: Award Tender Success**
    - **Test 25: Award Rejects Non-Creator**
    - **Test 26: Award Transfers Credits and Payment**
    - **Test 27: Award Rejects Other Proposals**
    - **Validates: Requirements 8.1, 8.4, 8.5, 8.7**

  - [x] 4.9 Implement direct listing system
    - Create DirectListing struct
    - Implement createDirectListing function
    - Validate seller has sufficient credits
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 4.10 Write unit tests for direct listings
    - **Test 28: Create Listing Success**
    - **Test 29: Listing Rejects Insufficient Credits**
    - **Validates: Requirements 9.1, 9.5**

  - [x] 4.11 Implement listing purchase
    - Implement purchaseFromListing payable function
    - Transfer credits and payment
    - Handle partial purchases
    - Refund excess payment
    - Emit CreditsTraded event
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x] 4.12 Write unit tests for listing purchase
    - **Test 30: Purchase from Listing Success**
    - **Test 31: Partial Purchase Updates Listing**
    - **Test 32: Purchase Refunds Excess**
    - **Validates: Requirements 10.3, 10.6, 10.7**

  - [x] 4.13 Implement fee management and admin functions
    - Implement updateMarketplaceFee (owner only)
    - Implement withdrawFees (owner only)
    - Implement cancelTender function
    - Add pause/unpause functions
    - _Requirements: 11.4, 11.5, 11.6, 12.4, 12.5, 12.6_

  - [x] 4.14 Write unit tests for admin functions
    - **Test 33: Update Fee Success**
    - **Test 34: Fee Rejects Over 10%**
    - **Test 35: Cancel Tender**
    - **Validates: Requirements 11.3, 11.4**

- [x] 5. Checkpoint - Ensure CarbonCreditMarketplace contract is complete
  - Compile contract without errors
  - Run all unit tests
  - Verify gas usage is reasonable

- [x] 6. Implement deployment scripts and configuration
  - [x] 6.1 Create deployment script
    - Deploy CarbonCreditToken first
    - Deploy CarbonCreditMarketplace with token address
    - Save deployment addresses to file
    - Support multiple networks
    - _Requirements: 14.2, 14.3, 14.4, 14.5_

  - [x] 6.2 Write deployment tests
    - **Test 36: Deployment Script Execution**
    - **Test 37: Contract Addresses Saved**
    - **Validates: Requirements 14.2, 14.4**

  - [x] 6.3 Create local development setup
    - Create start_hardhat.bat for Windows
    - Configure Hardhat network with chainId 1337
    - Set up test accounts with ETH
    - _Requirements: 14.1, 14.5_

  - [x] 6.4 Write integration tests for deployment
    - **Test 38: Full Deployment Flow**
    - **Test 39: Contract Interaction After Deploy**
    - **Validates: Requirements 14.2, 14.3**

- [x] 7. Implement Django Web3 integration
  - [x] 7.1 Create Web3BlockchainManager class
    - Initialize Web3 connection from config
    - Load contract ABIs from artifacts
    - Set up account from private key
    - Handle connection errors gracefully
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 7.2 Write unit tests for Web3 manager
    - **Test 40: Web3 Connection**
    - **Test 41: Contract Loading**
    - **Validates: Requirements 13.1, 13.2**

  - [x] 7.3 Implement blockchain operations
    - Implement register_project_on_chain
    - Implement mint_credits_on_chain
    - Implement transfer_credits_on_chain
    - Implement get_balance
    - _Requirements: 13.4, 13.5_

  - [x] 7.4 Write integration tests for blockchain operations
    - **Test 42: Register Project on Chain**
    - **Test 43: Mint Credits on Chain**
    - **Test 44: Transfer Credits on Chain**
    - **Validates: Requirements 13.4**

  - [x] 7.5 Create BlockchainService layer
    - Implement mint_credits_for_project
    - Implement transfer_credits
    - Implement get_user_balance
    - Implement get_blockchain_status
    - _Requirements: 13.4, 13.6_

  - [x] 7.6 Write unit tests for BlockchainService
    - **Test 45: Service Mint Credits**
    - **Test 46: Service Transfer Credits**
    - **Test 47: Service Get Status**
    - **Validates: Requirements 13.4, 13.6**

  - [x] 7.7 Implement BlockchainConfig model
    - Create model with network settings
    - Store contract addresses
    - Support multiple configurations
    - Implement get_active_config
    - _Requirements: 13.6_

  - [x] 7.8 Write tests for configuration management
    - **Test 48: Config Creation**
    - **Test 49: Active Config Selection**
    - **Validates: Requirements 13.6**

- [x] 8. Implement event logging and monitoring
  - [x] 8.1 Create ChainTransaction model
    - Store sender, recipient, amount, project_id
    - Store transaction hash and timestamp
    - Store transaction kind and metadata
    - _Requirements: 15.1, 15.5_

  - [x] 8.2 Write tests for transaction logging
    - **Test 50: Transaction Record Creation**
    - **Test 51: Transaction Query**
    - **Validates: Requirements 15.5, 15.7**

  - [x] 8.3 Implement blockchain explorer functionality
    - Create get_chain function for transaction history
    - Support filtering by address and project
    - Provide transaction status tracking
    - _Requirements: 15.4, 15.6, 15.7_

  - [x] 8.4 Write tests for explorer functionality
    - **Test 52: Chain History Query**
    - **Test 53: Transaction Filtering**
    - **Validates: Requirements 15.4, 15.7**

- [x] 9. Checkpoint - Ensure backend integration is complete
  - Run all Django tests
  - Verify blockchain operations work end-to-end
  - Test with local Hardhat network

- [x] 10. Implement automatic blockchain setup
  - [x] 10.1 Create blockchain auto-setup module
    - Detect if Hardhat node is running
    - Start Hardhat node if needed
    - Deploy contracts automatically
    - Update BlockchainConfig with addresses
    - _Requirements: 14.1, 14.2, 14.4_

  - [x] 10.2 Write tests for auto-setup
    - **Test 54: Auto-Setup Detection**
    - **Test 55: Auto-Deploy Contracts**
    - **Validates: Requirements 14.2, 14.4**

  - [x] 10.3 Create fallback simple blockchain
    - Implement SimpleBlockchain class
    - Support basic issue and transfer operations
    - Persist to database models
    - Use when contracts unavailable
    - _Requirements: 13.7_

  - [x] 10.4 Write tests for fallback blockchain
    - **Test 56: Simple Blockchain Operations**
    - **Test 57: Fallback Activation**
    - **Validates: Requirements 13.7**

- [x] 11. Implement security features and validation
  - [x] 11.1 Add input validation
    - Validate Ethereum addresses
    - Validate amounts and project IDs
    - Sanitize string inputs
    - _Requirements: 12.7_

  - [x] 11.2 Write security tests
    - **Test 58: Address Validation**
    - **Test 59: Input Sanitization**
    - **Validates: Requirements 12.7**

  - [x] 11.3 Implement access control checks
    - Verify user permissions for operations
    - Check wallet ownership
    - Validate project ownership
    - _Requirements: 12.4, 12.5, 12.6_

  - [x] 11.4 Write access control tests
    - **Test 60: Permission Checks**
    - **Test 61: Wallet Ownership**
    - **Validates: Requirements 12.4**

- [x] 12. Create comprehensive test suite
  - [x] 12.1 Expand Hardhat test coverage
    - Achieve 90%+ coverage for contracts
    - Test all edge cases and error conditions
    - Test gas optimization
    - _Requirements: All contract requirements_

  - [x] 12.2 Create integration test suite
    - Test full tender lifecycle
    - Test credit flow end-to-end
    - Test Django-blockchain integration
    - _Requirements: All requirements_

  - [x] 12.3 Add property-based tests
    - Test balance consistency properties
    - Test fee calculation accuracy
    - Test state machine transitions
    - _Requirements: Design properties_

  - [x] 12.4 Set up continuous integration
    - Configure automated test execution
    - Add coverage reporting
    - Implement quality gates
    - _Requirements: 14.1_

- [x] 13. Final integration and documentation
  - [x] 13.1 Create deployment documentation
    - Document deployment process
    - Document configuration options
    - Document troubleshooting steps
    - _Requirements: 14.5, 14.6_

  - [x] 13.2 Verify contract security
    - Run Slither static analysis
    - Review access control patterns
    - Verify reentrancy protection
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 13.3 Optimize gas usage
    - Profile gas usage for all functions
    - Optimize storage patterns
    - Reduce unnecessary operations
    - _Requirements: 14.1_

- [x] 14. Final checkpoint - Complete blockchain module validation
  - Ensure all tests pass
  - Verify contracts compile and deploy
  - Confirm Django integration works
  - Validate security measures

## Notes

- Tasks are organized to build core token functionality first, then marketplace features
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation and allow for user feedback
- Smart contract tests use Hardhat/Chai framework
- Backend tests use Django TestCase with mocking for blockchain calls
- Security is built-in from the start with OpenZeppelin contracts
- Gas optimization is considered throughout development
- The fallback simple blockchain ensures functionality when contracts unavailable
- All contract functions emit events for monitoring and auditing
- Private keys should never be committed to version control
