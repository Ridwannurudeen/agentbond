import { Contract, JsonRpcSigner } from "ethers";

const AGENT_REGISTRY_ABI = [
  "function registerAgent(string metadataURI) returns (uint256)",
  "event AgentRegistered(uint256 indexed agentId, address indexed operator)",
];

const WARRANTY_POOL_ABI = [
  "function stake(uint256 agentId) payable",
];

const POLICY_REGISTRY_ABI = [
  "function registerPolicy(uint256 agentId, bytes32 policyHash, string rulesURI) returns (uint256)",
  "event PolicyRegistered(uint256 indexed policyId, uint256 indexed agentId)",
];

const AGENT_REGISTRY_ADDRESS = import.meta.env.VITE_AGENT_REGISTRY_ADDRESS as string;
const WARRANTY_POOL_ADDRESS = import.meta.env.VITE_WARRANTY_POOL_ADDRESS as string;
const POLICY_REGISTRY_ADDRESS = import.meta.env.VITE_POLICY_REGISTRY_ADDRESS as string;

export function getAgentRegistry(signer: JsonRpcSigner) {
  return new Contract(AGENT_REGISTRY_ADDRESS, AGENT_REGISTRY_ABI, signer);
}

export function getWarrantyPool(signer: JsonRpcSigner) {
  return new Contract(WARRANTY_POOL_ADDRESS, WARRANTY_POOL_ABI, signer);
}

export function getPolicyRegistry(signer: JsonRpcSigner) {
  return new Contract(POLICY_REGISTRY_ADDRESS, POLICY_REGISTRY_ABI, signer);
}
