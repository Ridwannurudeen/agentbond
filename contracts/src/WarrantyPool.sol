// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
interface IAgentRegistry {
    function pauseAgent(uint256 agentId) external;
    function agents(uint256 agentId) external view returns (
        address operator, string memory metadataURI, uint256 activeVersion,
        uint8 status, uint256 trustScore, uint256 totalRuns, uint256 violations,
        uint256 createdAt
    );
}

contract WarrantyPool is Initializable, OwnableUpgradeable, UUPSUpgradeable {
    // Manual reentrancy guard (upgrade-safe, no constructor)
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _reentrancyStatus;

    modifier nonReentrant() {
        require(_reentrancyStatus != _ENTERED, "ReentrancyGuard: reentrant call");
        _reentrancyStatus = _ENTERED;
        _;
        _reentrancyStatus = _NOT_ENTERED;
    }

    struct Stake {
        uint256 amount;
        uint256 lockedUntil;
        uint256 reserved;
        uint256 pendingUnstake;
    }

    struct UnstakeRequest {
        address operator;
        uint256 agentId;
        uint256 amount;
        uint256 unlockTime;
        bool executed;
    }

    uint256 public constant COOLDOWN_PERIOD = 7 days;
    uint256 public constant MIN_COLLATERAL_RATIO_BPS = 15000;

    mapping(uint256 => Stake) public stakes;
    mapping(uint256 => UnstakeRequest) public unstakeRequests;
    uint256 public nextUnstakeId;

    IAgentRegistry public agentRegistry;
    address public claimManager;

    event Staked(uint256 indexed agentId, uint256 amount);
    event UnstakeRequested(uint256 indexed requestId, uint256 indexed agentId, uint256 amount);
    event UnstakeFinalized(uint256 indexed requestId);
    event SlashExecuted(uint256 indexed agentId, uint256 amount, uint256 indexed claimId);
    event PayoutSent(address indexed recipient, uint256 amount, uint256 indexed claimId);
    event ClaimManagerUpdated(address indexed oldManager, address indexed newManager);

    modifier onlyClaimManager() {
        require(msg.sender == claimManager, "Not claim manager");
        _;
    }

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address _agentRegistry) public initializer {
        require(_agentRegistry != address(0), "Zero address");
        __Ownable_init(msg.sender);
        // UUPSUpgradeable is stateless in OZ v5 — no init needed
        _reentrancyStatus = _NOT_ENTERED;
        agentRegistry = IAgentRegistry(_agentRegistry);
        nextUnstakeId = 1;
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    function setClaimManager(address _claimManager) external onlyOwner {
        require(_claimManager != address(0), "Zero address");
        address old = claimManager;
        claimManager = _claimManager;
        emit ClaimManagerUpdated(old, _claimManager);
    }

    function stake(uint256 agentId) external payable {
        (address operator, , , , , , , ) = agentRegistry.agents(agentId);
        require(operator == msg.sender, "Not agent operator");
        require(msg.value > 0, "Must stake > 0");

        stakes[agentId].amount += msg.value;
        emit Staked(agentId, msg.value);
    }

    function requestUnstake(uint256 agentId, uint256 amount) external returns (uint256) {
        (address operator, , , , , , , ) = agentRegistry.agents(agentId);
        require(operator == msg.sender, "Not agent operator");

        Stake storage s = stakes[agentId];
        uint256 free = s.amount - s.reserved - s.pendingUnstake;
        require(amount <= free, "Insufficient free collateral");

        uint256 requestId = nextUnstakeId++;
        unstakeRequests[requestId] = UnstakeRequest({
            operator: msg.sender,
            agentId: agentId,
            amount: amount,
            unlockTime: block.timestamp + COOLDOWN_PERIOD,
            executed: false
        });

        s.pendingUnstake += amount;
        emit UnstakeRequested(requestId, agentId, amount);
        return requestId;
    }

    function finalizeUnstake(uint256 requestId) external nonReentrant {
        UnstakeRequest storage req = unstakeRequests[requestId];
        require(req.operator == msg.sender, "Not request owner");
        require(block.timestamp >= req.unlockTime, "Cooldown not elapsed");
        require(!req.executed, "Already executed");

        req.executed = true;
        Stake storage s = stakes[req.agentId];
        s.amount -= req.amount;
        s.pendingUnstake -= req.amount;

        (bool sent, ) = payable(msg.sender).call{value: req.amount}("");
        require(sent, "Transfer failed");

        emit UnstakeFinalized(requestId);
    }

    function slash(
        uint256 agentId,
        uint256 amount,
        uint256 claimId
    ) external onlyClaimManager {
        Stake storage s = stakes[agentId];
        require(s.amount >= amount, "Insufficient stake");
        s.amount -= amount;
        if (s.reserved >= amount) {
            s.reserved -= amount;
        } else {
            s.reserved = 0;
        }
        emit SlashExecuted(agentId, amount, claimId);

        if (s.amount == 0) {
            try agentRegistry.pauseAgent(agentId) {} catch {}
        }
    }

    function payout(
        address recipient,
        uint256 amount,
        uint256 claimId
    ) external onlyClaimManager nonReentrant {
        require(address(this).balance >= amount, "Insufficient pool balance");
        (bool sent, ) = payable(recipient).call{value: amount}("");
        require(sent, "Payout transfer failed");
        emit PayoutSent(recipient, amount, claimId);
    }

    function reserveCollateral(uint256 agentId, uint256 amount) external onlyClaimManager {
        Stake storage s = stakes[agentId];
        require(s.amount - s.reserved - s.pendingUnstake >= amount, "Insufficient free collateral");
        s.reserved += amount;
    }

    function releaseCollateral(uint256 agentId, uint256 amount) external onlyClaimManager {
        Stake storage s = stakes[agentId];
        if (s.reserved >= amount) {
            s.reserved -= amount;
        } else {
            s.reserved = 0;
        }
    }

    function getCollateralHealth(uint256 agentId) external view returns (
        uint256 staked, uint256 reserved, uint256 free, uint256 ratioBps
    ) {
        Stake storage s = stakes[agentId];
        staked = s.amount;
        reserved = s.reserved;
        free = staked > reserved + s.pendingUnstake ? staked - reserved - s.pendingUnstake : 0;
        ratioBps = reserved > 0 ? (staked * 10000) / reserved : type(uint256).max;
    }

    receive() external payable {}
}
