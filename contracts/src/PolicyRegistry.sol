// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract PolicyRegistry {
    enum PolicyStatus { Active, Deprecated }

    struct Policy {
        uint256 agentId;
        bytes32 policyHash;
        string rulesURI;
        PolicyStatus status;
        uint256 createdAt;
    }

    uint256 public nextPolicyId = 1;
    mapping(uint256 => Policy) public policies;
    mapping(uint256 => uint256) public activePolicy; // agentId => policyId

    address public agentRegistry;

    event PolicyRegistered(uint256 indexed policyId, uint256 indexed agentId);
    event PolicyActivated(uint256 indexed agentId, uint256 indexed policyId);
    event PolicyDeprecated(uint256 indexed policyId);

    modifier onlyAgentOperator(uint256 agentId) {
        (bool success, bytes memory data) = agentRegistry.staticcall(
            abi.encodeWithSignature("agents(uint256)", agentId)
        );
        require(success, "Registry call failed");
        (address operator, , , , , , , ) = abi.decode(
            data, (address, string, uint256, uint8, uint256, uint256, uint256, uint256)
        );
        require(operator == msg.sender, "Not agent operator");
        _;
    }

    constructor(address _agentRegistry) {
        agentRegistry = _agentRegistry;
    }

    function registerPolicy(
        uint256 agentId,
        bytes32 policyHash,
        string calldata rulesURI
    ) external onlyAgentOperator(agentId) returns (uint256) {
        uint256 policyId = nextPolicyId++;
        policies[policyId] = Policy({
            agentId: agentId,
            policyHash: policyHash,
            rulesURI: rulesURI,
            status: PolicyStatus.Active,
            createdAt: block.timestamp
        });
        emit PolicyRegistered(policyId, agentId);
        return policyId;
    }

    function activatePolicy(
        uint256 agentId,
        uint256 policyId
    ) external onlyAgentOperator(agentId) {
        require(policies[policyId].agentId == agentId, "Policy not for this agent");
        require(policies[policyId].status == PolicyStatus.Active, "Policy deprecated");
        activePolicy[agentId] = policyId;
        emit PolicyActivated(agentId, policyId);
    }

    function deprecatePolicy(uint256 policyId) external {
        Policy storage policy = policies[policyId];
        (bool success, bytes memory data) = agentRegistry.staticcall(
            abi.encodeWithSignature("agents(uint256)", policy.agentId)
        );
        require(success, "Registry call failed");
        (address operator, , , , , , , ) = abi.decode(
            data, (address, string, uint256, uint8, uint256, uint256, uint256, uint256)
        );
        require(operator == msg.sender, "Not agent operator");
        policy.status = PolicyStatus.Deprecated;
        emit PolicyDeprecated(policyId);
    }

    function getPolicy(uint256 policyId) external view returns (Policy memory) {
        return policies[policyId];
    }

    function getActivePolicy(uint256 agentId) external view returns (uint256) {
        return activePolicy[agentId];
    }
}
