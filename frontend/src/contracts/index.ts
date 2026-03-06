import { Contract, JsonRpcSigner, getAddress } from "ethers";

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

function requireAddress(envKey: string, raw: string | undefined): string {
  if (!raw) throw new Error(`Contract address not configured: ${envKey} is empty/undefined`);
  try {
    return getAddress(raw.trim()); // checksums + validates; also strips accidental whitespace
  } catch {
    throw new Error(`Invalid contract address in ${envKey}: "${raw}"`);
  }
}

export function getAgentRegistry(signer: JsonRpcSigner) {
  const addr = requireAddress("VITE_AGENT_REGISTRY_ADDRESS", import.meta.env.VITE_AGENT_REGISTRY_ADDRESS);
  return new Contract(addr, AGENT_REGISTRY_ABI, signer);
}

export function getWarrantyPool(signer: JsonRpcSigner) {
  const addr = requireAddress("VITE_WARRANTY_POOL_ADDRESS", import.meta.env.VITE_WARRANTY_POOL_ADDRESS);
  return new Contract(addr, WARRANTY_POOL_ABI, signer);
}

export function getPolicyRegistry(signer: JsonRpcSigner) {
  const addr = requireAddress("VITE_POLICY_REGISTRY_ADDRESS", import.meta.env.VITE_POLICY_REGISTRY_ADDRESS);
  return new Contract(addr, POLICY_REGISTRY_ABI, signer);
}
