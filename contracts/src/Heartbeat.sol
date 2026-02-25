// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Heartbeat
 * @notice Simple on-chain liveness proof for agents.
 * Operators call `ping` to prove their agent is alive.
 * Anyone can query `lastPing` to check liveness.
 */
contract Heartbeat {
    // agentId => last ping timestamp
    mapping(uint256 => uint256) public lastPing;

    // agentId => operator who pinged
    mapping(uint256 => address) public lastPinger;

    uint256 public constant LIVENESS_THRESHOLD = 1 hours;

    event Ping(uint256 indexed agentId, address indexed operator, uint256 timestamp);

    function ping(uint256 agentId) external {
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
