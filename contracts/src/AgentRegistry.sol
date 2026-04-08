// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

contract AgentRegistry is Initializable, OwnableUpgradeable, UUPSUpgradeable {
    enum Status { Active, Paused, Retired }

    struct AgentInfo {
        address operator;
        string metadataURI;
        uint256 activeVersion;
        Status status;
        uint256 trustScore;
        uint256 totalRuns;
        uint256 violations;
        uint256 createdAt;
    }

    struct Version {
        bytes32 versionHash;
        uint256 policyId;
        uint256 timestamp;
    }

    uint256 public nextAgentId;
    mapping(uint256 => AgentInfo) public agents;
    mapping(uint256 => mapping(uint256 => Version)) public versions;
    mapping(uint256 => uint256) public nextVersionId;
    mapping(uint256 => bool) public pausedByResolver;

    address public resolver;
    address public warrantyPool;

    event AgentRegistered(uint256 indexed agentId, address indexed operator);
    event VersionPublished(uint256 indexed agentId, uint256 indexed versionId);
    event ScoreUpdated(uint256 indexed agentId, uint256 newScore);
    event StatusChanged(uint256 indexed agentId, Status status);
    event ResolverUpdated(address indexed oldResolver, address indexed newResolver);
    event WarrantyPoolUpdated(address indexed oldPool, address indexed newPool);

    modifier onlyOperator(uint256 agentId) {
        require(agents[agentId].operator == msg.sender, "Not operator");
        _;
    }

    modifier onlyResolver() {
        require(msg.sender == resolver, "Not resolver");
        _;
    }

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address _resolver) public initializer {
        require(_resolver != address(0), "Zero address");
        __Ownable_init(msg.sender);
        // UUPSUpgradeable is stateless in OZ v5 — no init needed
        resolver = _resolver;
        nextAgentId = 1;
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    function setResolver(address _resolver) external onlyOwner {
        require(_resolver != address(0), "Zero address");
        address old = resolver;
        resolver = _resolver;
        emit ResolverUpdated(old, _resolver);
    }

    function setWarrantyPool(address _warrantyPool) external onlyOwner {
        require(_warrantyPool != address(0), "Zero address");
        address old = warrantyPool;
        warrantyPool = _warrantyPool;
        emit WarrantyPoolUpdated(old, _warrantyPool);
    }

    function registerAgent(string calldata metadataURI) external returns (uint256) {
        uint256 agentId = nextAgentId++;
        agents[agentId] = AgentInfo({
            operator: msg.sender,
            metadataURI: metadataURI,
            activeVersion: 0,
            status: Status.Active,
            trustScore: 100,
            totalRuns: 0,
            violations: 0,
            createdAt: block.timestamp
        });
        emit AgentRegistered(agentId, msg.sender);
        return agentId;
    }

    function publishVersion(
        uint256 agentId,
        bytes32 versionHash,
        uint256 policyId
    ) external onlyOperator(agentId) returns (uint256) {
        uint256 versionId = nextVersionId[agentId]++;
        versions[agentId][versionId] = Version({
            versionHash: versionHash,
            policyId: policyId,
            timestamp: block.timestamp
        });
        agents[agentId].activeVersion = versionId;
        emit VersionPublished(agentId, versionId);
        return versionId;
    }

    function setStatus(uint256 agentId, Status status) external onlyOperator(agentId) {
        if (agents[agentId].status == Status.Paused && status == Status.Active) {
            require(!pausedByResolver[agentId], "Only resolver can unpause");
        }
        agents[agentId].status = status;
        emit StatusChanged(agentId, status);
    }

    function pauseAgent(uint256 agentId) external {
        require(
            msg.sender == resolver
            || msg.sender == warrantyPool
            || msg.sender == agents[agentId].operator,
            "Not authorized"
        );
        agents[agentId].status = Status.Paused;
        if (msg.sender == resolver || msg.sender == warrantyPool) {
            pausedByResolver[agentId] = true;
        }
        emit StatusChanged(agentId, Status.Paused);
    }

    function unpauseAgent(uint256 agentId) external onlyResolver {
        agents[agentId].status = Status.Active;
        pausedByResolver[agentId] = false;
        emit StatusChanged(agentId, Status.Active);
    }

    function updateScore(
        uint256 agentId,
        uint256 newScore,
        uint256 totalRuns,
        uint256 violationCount
    ) external onlyResolver {
        AgentInfo storage agent = agents[agentId];
        agent.trustScore = newScore;
        agent.totalRuns = totalRuns;
        agent.violations = violationCount;
        emit ScoreUpdated(agentId, newScore);
    }

    function getAgent(uint256 agentId) external view returns (AgentInfo memory) {
        return agents[agentId];
    }

    function getScore(uint256 agentId) external view returns (uint256, uint256, uint256) {
        AgentInfo storage agent = agents[agentId];
        return (agent.trustScore, agent.totalRuns, agent.violations);
    }

    function getVersion(uint256 agentId, uint256 versionId) external view returns (Version memory) {
        return versions[agentId][versionId];
    }
}
