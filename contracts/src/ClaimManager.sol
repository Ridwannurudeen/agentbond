// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

interface IWarrantyPool {
    function slash(uint256 agentId, uint256 amount, uint256 claimId) external;
    function payout(address recipient, uint256 amount, uint256 claimId) external;
    function reserveCollateral(uint256 agentId, uint256 amount) external;
    function releaseCollateral(uint256 agentId, uint256 amount) external;
}

interface IAgentRegistryClaims {
    function agents(uint256 agentId) external view returns (
        address operator, string memory metadataURI, uint256 activeVersion,
        uint8 status, uint256 trustScore, uint256 totalRuns, uint256 violations,
        uint256 createdAt
    );
}

contract ClaimManager is Initializable, OwnableUpgradeable, UUPSUpgradeable {
    enum ClaimStatus { Submitted, Verified, Approved, Rejected, Paid }

    struct Claim {
        bytes32 runId;
        address claimant;
        uint256 agentId;
        string reasonCode;
        bytes32 evidenceHash;
        ClaimStatus status;
        uint256 amount;
        uint256 createdAt;
        uint256 resolvedAt;
    }

    uint256 public nextClaimId;
    mapping(uint256 => Claim) public claims;
    mapping(bytes32 => uint256) public claimsByRun;
    mapping(uint256 => uint256) public dailyClaimCount;
    mapping(uint256 => uint256) public dailyClaimDay;

    uint256 public constant MAX_CLAIMS_PER_DAY = 10;
    uint256 public constant DEFAULT_CLAIM_AMOUNT = 0.01 ether;

    IWarrantyPool public warrantyPool;
    IAgentRegistryClaims public agentRegistry;
    address public resolver;

    event ClaimSubmitted(uint256 indexed claimId, bytes32 indexed runId, address indexed claimant);
    event ClaimResolved(uint256 indexed claimId, bool approved);
    event ClaimPaid(uint256 indexed claimId, uint256 amount);
    event ResolverUpdated(address indexed oldResolver, address indexed newResolver);

    modifier onlyResolver() {
        require(msg.sender == resolver, "Not resolver");
        _;
    }

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address _warrantyPool, address _agentRegistry, address _resolver) public initializer {
        require(_warrantyPool != address(0), "Zero address");
        require(_agentRegistry != address(0), "Zero address");
        require(_resolver != address(0), "Zero address");
        __Ownable_init(msg.sender);
        // UUPSUpgradeable is stateless in OZ v5 — no init needed
        warrantyPool = IWarrantyPool(_warrantyPool);
        agentRegistry = IAgentRegistryClaims(_agentRegistry);
        resolver = _resolver;
        nextClaimId = 1;
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    function setResolver(address _resolver) external onlyOwner {
        require(_resolver != address(0), "Zero address");
        address old = resolver;
        resolver = _resolver;
        emit ResolverUpdated(old, _resolver);
    }

    function submitClaim(
        bytes32 runId,
        uint256 agentId,
        string calldata reasonCode,
        bytes32 evidenceHash
    ) external returns (uint256) {
        require(runId != bytes32(0), "Invalid runId");
        require(claimsByRun[runId] == 0, "Claim already exists for this run");

        (address operator, , , , , , , ) = agentRegistry.agents(agentId);
        require(operator != address(0), "Agent does not exist");

        uint256 today = block.timestamp / 1 days;
        if (dailyClaimDay[agentId] != today) {
            dailyClaimDay[agentId] = today;
            dailyClaimCount[agentId] = 0;
        }
        require(dailyClaimCount[agentId] < MAX_CLAIMS_PER_DAY, "Daily claim limit reached");
        dailyClaimCount[agentId]++;

        uint256 claimId = nextClaimId++;
        claims[claimId] = Claim({
            runId: runId,
            claimant: msg.sender,
            agentId: agentId,
            reasonCode: reasonCode,
            evidenceHash: evidenceHash,
            status: ClaimStatus.Submitted,
            amount: DEFAULT_CLAIM_AMOUNT,
            createdAt: block.timestamp,
            resolvedAt: 0
        });
        claimsByRun[runId] = claimId;

        warrantyPool.reserveCollateral(agentId, DEFAULT_CLAIM_AMOUNT);

        emit ClaimSubmitted(claimId, runId, msg.sender);
        return claimId;
    }

    function verifyClaim(
        uint256 claimId,
        bool approved
    ) external onlyResolver {
        Claim storage claim = claims[claimId];
        require(claim.status == ClaimStatus.Submitted, "Invalid claim status");

        if (approved) {
            claim.status = ClaimStatus.Approved;
        } else {
            claim.status = ClaimStatus.Rejected;
            claim.resolvedAt = block.timestamp;
            warrantyPool.releaseCollateral(claim.agentId, claim.amount);
        }
        emit ClaimResolved(claimId, approved);
    }

    function executePayout(uint256 claimId) external onlyResolver {
        Claim storage claim = claims[claimId];
        require(claim.status == ClaimStatus.Approved, "Claim not approved");

        claim.status = ClaimStatus.Paid;
        claim.resolvedAt = block.timestamp;

        warrantyPool.slash(claim.agentId, claim.amount, claimId);
        warrantyPool.payout(claim.claimant, claim.amount, claimId);

        emit ClaimPaid(claimId, claim.amount);
    }

    function getClaim(uint256 claimId) external view returns (Claim memory) {
        return claims[claimId];
    }
}
