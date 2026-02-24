// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

interface IWarrantyPool {
    function slash(uint256 agentId, uint256 amount, uint256 claimId) external;
    function payout(address recipient, uint256 amount, uint256 claimId) external;
    function reserveCollateral(uint256 agentId, uint256 amount) external;
    function releaseCollateral(uint256 agentId, uint256 amount) external;
}

contract ClaimManager is Ownable {
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

    uint256 public nextClaimId = 1;
    mapping(uint256 => Claim) public claims;
    mapping(bytes32 => uint256) public claimsByRun; // runId => claimId (one claim per run)
    mapping(uint256 => uint256) public dailyClaimCount; // agentId => count
    mapping(uint256 => uint256) public dailyClaimDay; // agentId => day number

    uint256 public constant MAX_CLAIMS_PER_DAY = 10;
    uint256 public constant DEFAULT_CLAIM_AMOUNT = 0.01 ether;

    IWarrantyPool public warrantyPool;
    address public resolver;

    event ClaimSubmitted(uint256 indexed claimId, bytes32 indexed runId, address indexed claimant);
    event ClaimResolved(uint256 indexed claimId, bool approved);
    event ClaimPaid(uint256 indexed claimId, uint256 amount);

    modifier onlyResolver() {
        require(msg.sender == resolver, "Not resolver");
        _;
    }

    constructor(address _warrantyPool, address _resolver) Ownable(msg.sender) {
        warrantyPool = IWarrantyPool(_warrantyPool);
        resolver = _resolver;
    }

    function setResolver(address _resolver) external onlyOwner {
        resolver = _resolver;
    }

    function submitClaim(
        bytes32 runId,
        uint256 agentId,
        string calldata reasonCode,
        bytes32 evidenceHash
    ) external returns (uint256) {
        require(claimsByRun[runId] == 0, "Claim already exists for this run");

        // Rate limiting per agent per day
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

        // Reserve collateral for potential payout
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
            // Release reserved collateral
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
