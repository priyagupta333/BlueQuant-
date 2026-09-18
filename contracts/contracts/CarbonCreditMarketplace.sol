// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "./CarbonCreditToken.sol";

/**
 * @title CarbonCreditMarketplace
 * @dev Marketplace for trading carbon credits with tender system
 */
contract CarbonCreditMarketplace is Ownable, Pausable, ReentrancyGuard {
    
    CarbonCreditToken public carbonToken;
    
    // Events
    event TenderCreated(uint256 indexed tenderId, address indexed corporate, uint256 creditsRequired, uint256 maxPrice);
    event ProposalSubmitted(uint256 indexed tenderId, uint256 indexed proposalId, address indexed ngo, uint256 creditsOffered, uint256 pricePerCredit);
    event TenderAwarded(uint256 indexed tenderId, uint256 indexed proposalId, address indexed winner);
    event CreditsTraded(address indexed seller, address indexed buyer, uint256 amount, uint256 totalPrice, uint256 projectId);
    event MarketplaceFeeUpdated(uint256 newFee);
    
    // Structs
    struct Tender {
        uint256 id;
        address corporate;
        string title;
        string description;
        uint256 creditsRequired;
        uint256 maxPricePerCredit;
        uint256 deadline;
        TenderStatus status;
        uint256 createdAt;
        uint256 winningProposalId;
    }
    
    struct Proposal {
        uint256 id;
        uint256 tenderId;
        address ngo;
        uint256 creditsOffered;
        uint256 pricePerCredit;
        uint256 projectId;
        string projectDescription;
        ProposalStatus status;
        uint256 submittedAt;
    }
    
    struct DirectListing {
        uint256 id;
        address seller;
        uint256 projectId;
        uint256 creditsAmount;
        uint256 pricePerCredit;
        bool isActive;
        uint256 createdAt;
    }
    
    enum TenderStatus { Open, UnderReview, Awarded, Cancelled }
    enum ProposalStatus { Pending, Accepted, Rejected }
    
    // State variables
    mapping(uint256 => Tender) public tenders;
    mapping(uint256 => Proposal) public proposals;
    mapping(uint256 => DirectListing) public directListings;
    mapping(uint256 => uint256[]) public tenderProposals; // tenderId => proposalIds[]
    mapping(address => uint256[]) public userTenders;
    mapping(address => uint256[]) public userProposals;
    
    uint256 public nextTenderId = 1;
    uint256 public nextProposalId = 1;
    uint256 public nextListingId = 1;
    uint256 public marketplaceFeePercent = 250; // 2.5% fee (250 basis points)
    
    constructor(address _carbonTokenAddress) Ownable(msg.sender) {
        carbonToken = CarbonCreditToken(_carbonTokenAddress);
    }
    
    /**
     * @dev Create a new tender for carbon credits
     */
    function createTender(
        string memory _title,
        string memory _description,
        uint256 _creditsRequired,
        uint256 _maxPricePerCredit,
        uint256 _durationDays
    ) external whenNotPaused returns (uint256) {
        require(_creditsRequired > 0, "Credits required must be greater than 0");
        require(_maxPricePerCredit > 0, "Max price must be greater than 0");
        require(_durationDays > 0, "Duration must be greater than 0");
        
        uint256 tenderId = nextTenderId++;
        uint256 deadline = block.timestamp + (_durationDays * 1 days);
        
        tenders[tenderId] = Tender({
            id: tenderId,
            corporate: msg.sender,
            title: _title,
            description: _description,
            creditsRequired: _creditsRequired,
            maxPricePerCredit: _maxPricePerCredit,
            deadline: deadline,
            status: TenderStatus.Open,
            createdAt: block.timestamp,
            winningProposalId: 0
        });
        
        userTenders[msg.sender].push(tenderId);
        
        emit TenderCreated(tenderId, msg.sender, _creditsRequired, _maxPricePerCredit);
        return tenderId;
    }
    
    /**
     * @dev Submit a proposal for a tender
     */
    function submitProposal(
        uint256 _tenderId,
        uint256 _creditsOffered,
        uint256 _pricePerCredit,
        uint256 _projectId,
        string memory _projectDescription
    ) external whenNotPaused returns (uint256) {
        Tender storage tender = tenders[_tenderId];
        require(tender.status == TenderStatus.Open, "Tender is not open");
        require(block.timestamp < tender.deadline, "Tender deadline has passed");
        require(_creditsOffered >= tender.creditsRequired, "Insufficient credits offered");
        require(_pricePerCredit <= tender.maxPricePerCredit, "Price exceeds maximum");
        require(carbonToken.getUserProjectCredits(msg.sender, _projectId) >= _creditsOffered, "Insufficient project credits");
        
        uint256 proposalId = nextProposalId++;
        
        proposals[proposalId] = Proposal({
            id: proposalId,
            tenderId: _tenderId,
            ngo: msg.sender,
            creditsOffered: _creditsOffered,
            pricePerCredit: _pricePerCredit,
            projectId: _projectId,
            projectDescription: _projectDescription,
            status: ProposalStatus.Pending,
            submittedAt: block.timestamp
        });
        
        tenderProposals[_tenderId].push(proposalId);
        userProposals[msg.sender].push(proposalId);
        
        emit ProposalSubmitted(_tenderId, proposalId, msg.sender, _creditsOffered, _pricePerCredit);
        return proposalId;
    }
    
    /**
     * @dev Award a tender to a specific proposal
     */
    function awardTender(uint256 _tenderId, uint256 _proposalId) external whenNotPaused nonReentrant {
        Tender storage tender = tenders[_tenderId];
        Proposal storage proposal = proposals[_proposalId];
        
        require(tender.corporate == msg.sender, "Only tender creator can award");
        require(tender.status == TenderStatus.Open, "Tender is not open");
        require(proposal.tenderId == _tenderId, "Proposal does not belong to this tender");
        require(proposal.status == ProposalStatus.Pending, "Proposal is not pending");
        
        // Calculate total cost and marketplace fee
        uint256 totalCost = proposal.creditsOffered * proposal.pricePerCredit;
        uint256 marketplaceFee = (totalCost * marketplaceFeePercent) / 10000;
        uint256 sellerAmount = totalCost - marketplaceFee;
        
        // Transfer payment from corporate to NGO
        require(msg.sender.balance >= totalCost, "Insufficient funds");
        payable(proposal.ngo).transfer(sellerAmount);
        
        // Transfer credits from NGO to corporate
        require(
            carbonToken.transferCreditsFrom(proposal.ngo, msg.sender, proposal.creditsOffered, proposal.projectId),
            "Credit transfer failed"
        );
        
        // Update tender and proposal status
        tender.status = TenderStatus.Awarded;
        tender.winningProposalId = _proposalId;
        proposal.status = ProposalStatus.Accepted;
        
        // Reject other proposals
        uint256[] memory proposalIds = tenderProposals[_tenderId];
        for (uint256 i = 0; i < proposalIds.length; i++) {
            if (proposalIds[i] != _proposalId) {
                proposals[proposalIds[i]].status = ProposalStatus.Rejected;
            }
        }
        
        emit TenderAwarded(_tenderId, _proposalId, proposal.ngo);
        emit CreditsTraded(proposal.ngo, msg.sender, proposal.creditsOffered, totalCost, proposal.projectId);
    }
    
    /**
     * @dev Create a direct listing for carbon credits
     */
    function createDirectListing(
        uint256 _projectId,
        uint256 _creditsAmount,
        uint256 _pricePerCredit
    ) external whenNotPaused returns (uint256) {
        require(_creditsAmount > 0, "Credits amount must be greater than 0");
        require(_pricePerCredit > 0, "Price must be greater than 0");
        require(carbonToken.getUserProjectCredits(msg.sender, _projectId) >= _creditsAmount, "Insufficient project credits");
        
        uint256 listingId = nextListingId++;
        
        directListings[listingId] = DirectListing({
            id: listingId,
            seller: msg.sender,
            projectId: _projectId,
            creditsAmount: _creditsAmount,
            pricePerCredit: _pricePerCredit,
            isActive: true,
            createdAt: block.timestamp
        });
        
        return listingId;
    }
    
    /**
     * @dev Purchase credits from a direct listing
     */
    function purchaseFromListing(uint256 _listingId, uint256 _creditsAmount) external payable whenNotPaused nonReentrant {
        DirectListing storage listing = directListings[_listingId];
        require(listing.isActive, "Listing is not active");
        require(_creditsAmount > 0 && _creditsAmount <= listing.creditsAmount, "Invalid credits amount");
        
        uint256 totalCost = _creditsAmount * listing.pricePerCredit;
        require(msg.value >= totalCost, "Insufficient payment");
        
        uint256 marketplaceFee = (totalCost * marketplaceFeePercent) / 10000;
        uint256 sellerAmount = totalCost - marketplaceFee;
        
        // Transfer payment to seller
        payable(listing.seller).transfer(sellerAmount);
        
        // Transfer credits to buyer
        require(
            carbonToken.transferCreditsFrom(listing.seller, msg.sender, _creditsAmount, listing.projectId),
            "Credit transfer failed"
        );
        
        // Update listing
        listing.creditsAmount -= _creditsAmount;
        if (listing.creditsAmount == 0) {
            listing.isActive = false;
        }
        
        // Refund excess payment
        if (msg.value > totalCost) {
            payable(msg.sender).transfer(msg.value - totalCost);
        }
        
        emit CreditsTraded(listing.seller, msg.sender, _creditsAmount, totalCost, listing.projectId);
    }
    
    /**
     * @dev Get tender proposals
     */
    function getTenderProposals(uint256 _tenderId) external view returns (uint256[] memory) {
        return tenderProposals[_tenderId];
    }
    
    /**
     * @dev Get user's tenders
     */
    function getUserTenders(address _user) external view returns (uint256[] memory) {
        return userTenders[_user];
    }
    
    /**
     * @dev Get user's proposals
     */
    function getUserProposals(address _user) external view returns (uint256[] memory) {
        return userProposals[_user];
    }
    
    /**
     * @dev Update marketplace fee (only owner)
     */
    function updateMarketplaceFee(uint256 _newFeePercent) external onlyOwner {
        require(_newFeePercent <= 1000, "Fee cannot exceed 10%"); // Max 10%
        marketplaceFeePercent = _newFeePercent;
        emit MarketplaceFeeUpdated(_newFeePercent);
    }
    
    /**
     * @dev Cancel a tender (only tender creator)
     */
    function cancelTender(uint256 _tenderId) external {
        Tender storage tender = tenders[_tenderId];
        require(tender.corporate == msg.sender, "Only tender creator can cancel");
        require(tender.status == TenderStatus.Open, "Tender is not open");
        
        tender.status = TenderStatus.Cancelled;
        
        // Reject all proposals
        uint256[] memory proposalIds = tenderProposals[_tenderId];
        for (uint256 i = 0; i < proposalIds.length; i++) {
            proposals[proposalIds[i]].status = ProposalStatus.Rejected;
        }
    }
    
    /**
     * @dev Withdraw marketplace fees (only owner)
     */
    function withdrawFees() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No fees to withdraw");
        payable(owner()).transfer(balance);
    }
    
    /**
     * @dev Pause contract
     */
    function pause() external onlyOwner {
        _pause();
    }
    
    /**
     * @dev Unpause contract
     */
    function unpause() external onlyOwner {
        _unpause();
    }
}