// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";

/**
 * @title CarbonCreditToken
 * @dev ERC20 token representing carbon credits with minting controls
 */
contract CarbonCreditToken is ERC20, Ownable, Pausable, ERC20Burnable {
    
    // Events
    event CreditsMinted(address indexed to, uint256 amount, uint256 projectId, string projectName);
    event CreditsTransferred(address indexed from, address indexed to, uint256 amount, uint256 projectId);
    event ProjectRegistered(uint256 indexed projectId, string name, address ngo, uint256 estimatedCredits);
    
    // Structs
    struct Project {
        uint256 id;
        string name;
        address ngo;
        uint256 totalCreditsIssued;
        uint256 estimatedCredits;
        bool isActive;
        uint256 createdAt;
    }
    
    // State variables
    mapping(uint256 => Project) public projects;
    mapping(address => uint256[]) public userProjects;
    mapping(address => mapping(uint256 => uint256)) public userProjectCredits;
    uint256 public nextProjectId = 1;
    uint256 public totalProjectsRegistered;
    
    // Price per credit in wei (can be updated by owner)
    uint256 public pricePerCredit = 0.001 ether; // 0.001 ETH per credit
    
    constructor() ERC20("Carbon Credit Token", "CCT") Ownable(msg.sender) {}
    
    /**
     * @dev Register a new carbon credit project
     */
    function registerProject(
        string memory _name,
        address _ngo,
        uint256 _estimatedCredits
    ) external onlyOwner returns (uint256) {
        uint256 projectId = nextProjectId++;
        
        projects[projectId] = Project({
            id: projectId,
            name: _name,
            ngo: _ngo,
            totalCreditsIssued: 0,
            estimatedCredits: _estimatedCredits,
            isActive: true,
            createdAt: block.timestamp
        });
        
        userProjects[_ngo].push(projectId);
        totalProjectsRegistered++;
        
        emit ProjectRegistered(projectId, _name, _ngo, _estimatedCredits);
        return projectId;
    }
    
    /**
     * @dev Mint carbon credits for a specific project
     */
    function mintCredits(
        address _to,
        uint256 _amount,
        uint256 _projectId
    ) external onlyOwner whenNotPaused {
        require(projects[_projectId].isActive, "Project is not active");
        require(_amount > 0, "Amount must be greater than 0");
        
        _mint(_to, _amount);
        
        projects[_projectId].totalCreditsIssued += _amount;
        userProjectCredits[_to][_projectId] += _amount;
        
        emit CreditsMinted(_to, _amount, _projectId, projects[_projectId].name);
    }
    
    /**
     * @dev Transfer credits with project tracking (internal use by marketplace)
     */
    function transferCredits(
        address _to,
        uint256 _amount,
        uint256 _projectId
    ) external whenNotPaused returns (bool) {
        require(userProjectCredits[msg.sender][_projectId] >= _amount, "Insufficient project credits");
        require(_amount > 0, "Amount must be greater than 0");
        
        _transfer(msg.sender, _to, _amount);
        
        userProjectCredits[msg.sender][_projectId] -= _amount;
        userProjectCredits[_to][_projectId] += _amount;
        
        emit CreditsTransferred(msg.sender, _to, _amount, _projectId);
        return true;
    }
    
    /**
     * @dev Transfer credits from one address to another (for marketplace)
     */
    function transferCreditsFrom(
        address _from,
        address _to,
        uint256 _amount,
        uint256 _projectId
    ) external whenNotPaused returns (bool) {
        require(userProjectCredits[_from][_projectId] >= _amount, "Insufficient project credits");
        require(_amount > 0, "Amount must be greater than 0");
        
        _transfer(_from, _to, _amount);
        
        userProjectCredits[_from][_projectId] -= _amount;
        userProjectCredits[_to][_projectId] += _amount;
        
        emit CreditsTransferred(_from, _to, _amount, _projectId);
        return true;
    }
    
    /**
     * @dev Purchase credits with ETH
     */
    function purchaseCredits(uint256 _projectId) external payable whenNotPaused {
        require(projects[_projectId].isActive, "Project is not active");
        require(msg.value > 0, "Must send ETH to purchase credits");
        
        uint256 creditsAmount = msg.value / pricePerCredit;
        require(creditsAmount > 0, "Insufficient ETH for minimum credit purchase");
        
        _mint(msg.sender, creditsAmount);
        userProjectCredits[msg.sender][_projectId] += creditsAmount;
        projects[_projectId].totalCreditsIssued += creditsAmount;
        
        emit CreditsMinted(msg.sender, creditsAmount, _projectId, projects[_projectId].name);
    }
    
    /**
     * @dev Get project details
     */
    function getProject(uint256 _projectId) external view returns (Project memory) {
        return projects[_projectId];
    }
    
    /**
     * @dev Get user's projects
     */
    function getUserProjects(address _user) external view returns (uint256[] memory) {
        return userProjects[_user];
    }
    
    /**
     * @dev Get user's credits for a specific project
     */
    function getUserProjectCredits(address _user, uint256 _projectId) external view returns (uint256) {
        return userProjectCredits[_user][_projectId];
    }
    
    /**
     * @dev Update price per credit (only owner)
     */
    function updatePricePerCredit(uint256 _newPrice) external onlyOwner {
        pricePerCredit = _newPrice;
    }
    
    /**
     * @dev Deactivate a project
     */
    function deactivateProject(uint256 _projectId) external onlyOwner {
        projects[_projectId].isActive = false;
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
    
    /**
     * @dev Withdraw contract balance (only owner)
     */
    function withdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No funds to withdraw");
        payable(owner()).transfer(balance);
    }
    
    /**
     * @dev Override update to include pause functionality
     */
    function _update(
        address from,
        address to,
        uint256 amount
    ) internal override whenNotPaused {
        super._update(from, to, amount);
    }
}