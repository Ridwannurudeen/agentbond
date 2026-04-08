// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IAgentRegistryHeartbeat {
    function agents(uint256 agentId) external view returns (
        address operator, string memory metadataURI, uint256 activeVersion,
        uint8 status, uint256 trustScore, uint256 totalRuns, uint256 violations,
        uint256 createdAt
    );
}

/**
 * @title Heartbeat
 * @notice On-chain liveness proof for agents.
 * Only the agent's operator can ping to prove liveness.
 */
contract Heartbeat {
    // agentId => last ping timestamp
    mapping(uint256 => uint256) public lastPing;

    // agentId => operator who pinged
    mapping(uint256 => address) public lastPinger;

    uint256 public constant LIVENESS_THRESHOLD = 1 hours;

    IAgentRegistryHeartbeat public agentRegistry;

    event Ping(uint256 indexed agentId, address indexed operator, uint256 timestamp);

    constructor(address _agentRegistry) {
        require(_agentRegistry != address(0), "Zero address");
        agentRegistry = IAgentRegistryHeartbeat(_agentRegistry);
    }

    function ping(uint256 agentId) external {
        (address operator, , , , , , , ) = agentRegistry.agents(agentId);
        require(operator != address(0), "Agent does not exist");
        require(operator == msg.sender, "Not agent operator");

        lastPing[agentId] = block.timestamp;
        lastPinger[agentId] = msg.sender;
        emit Ping(agentId, msg.sender, block.timestamp);
    }

    function isAlive(uint256 agentId) external view returns (bool) {
        if (lastPing[agentId] == 0) return false;
        return (block.timestamp - lastPing[agentId]) <= LIVENESS_THRESHOLD;
    }

    function getStatus(uint256 agentId) external view returns (
        bool alive,
        uint256 lastPingTime,
        address pinger,
        uint256 age
    ) {
        lastPingTime = lastPing[agentId];
        pinger = lastPinger[agentId];
        alive = lastPingTime > 0 && (block.timestamp - lastPingTime) <= LIVENESS_THRESHOLD;
        age = lastPingTime > 0 ? block.timestamp - lastPingTime : type(uint256).max;
    }
}
