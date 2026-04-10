import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { BrowserProvider, JsonRpcSigner } from "ethers";

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      on: (event: string, handler: (...args: unknown[]) => void) => void;
      removeListener: (event: string, handler: (...args: unknown[]) => void) => void;
    };
  }
}

interface WalletContextValue {
  address: string | null;
  chainId: number | null;
  isConnecting: boolean;
  signer: JsonRpcSigner | null;
  wrongChain: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  switchToBaseSepolia: () => Promise<void>;
}

const BASE_SEPOLIA_CHAIN_ID = 84532;

const WalletContext = createContext<WalletContextValue>({
  address: null,
  chainId: null,
  isConnecting: false,
  signer: null,
  wrongChain: false,
  connect: async () => {},
  disconnect: () => {},
  switchToBaseSepolia: async () => {},
});

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [address, setAddress] = useState<string | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [signer, setSigner] = useState<JsonRpcSigner | null>(null);

  const switchToBaseSepolia = useCallback(async () => {
    if (!window.ethereum) return;
    try {
      await window.ethereum.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: "0x14a34" }],
      });
    } catch (err: unknown) {
      if ((err as { code: number }).code === 4902) {
        await window.ethereum.request({
          method: "wallet_addEthereumChain",
          params: [{
            chainId: "0x14a34",
            chainName: "Base Sepolia",
            rpcUrls: ["https://sepolia.base.org"],
            blockExplorerUrls: ["https://sepolia.basescan.org"],
            nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
          }],
        });
      }
    }
  }, []);

  const connect = useCallback(async () => {
    if (!window.ethereum) {
      alert("MetaMask not detected. Please install MetaMask.");
      return;
    }
    setIsConnecting(true);
    try {
      const provider = new BrowserProvider(window.ethereum);
      const accounts: string[] = await provider.send("eth_requestAccounts", []);
      if (accounts.length > 0) {
        setAddress(accounts[0]);
        const network = await provider.getNetwork();
        const currentChainId = Number(network.chainId);
        setChainId(currentChainId);
        if (currentChainId !== BASE_SEPOLIA_CHAIN_ID) {
          await switchToBaseSepolia();
        } else {
          const s = await provider.getSigner();
          setSigner(s);
        }
      }
    } catch (err) {
      console.error("Wallet connect failed:", err);
    } finally {
      setIsConnecting(false);
    }
  }, [switchToBaseSepolia]);

  const disconnect = useCallback(() => {
    setAddress(null);
    setChainId(null);
    setSigner(null);
  }, []);

  // Re-hydrate on page load if wallet was previously connected
  useEffect(() => {
    if (!window.ethereum) return;
    const provider = new BrowserProvider(window.ethereum);
    provider.send("eth_accounts", []).then(async (accounts: string[]) => {
      if (accounts.length > 0) {
        try {
          const s = await provider.getSigner();
          const network = await provider.getNetwork();
          setAddress(accounts[0]);
          setChainId(Number(network.chainId));
          setSigner(s);
        } catch {
          // getSigner failed — leave as disconnected, user must click Connect Wallet
        }
      }
    });

    // Listen for account / chain changes
    const onAccountsChanged = (...args: unknown[]) => {
      const accounts = args[0] as string[];
      if (accounts.length > 0) {
        const p = new BrowserProvider(window.ethereum!);
        p.getSigner()
          .then((s) => { setAddress(accounts[0]); setSigner(s); })
          .catch(() => { setAddress(null); setSigner(null); });
      } else {
        setAddress(null);
        setSigner(null);
      }
    };
    const onChainChanged = () => {
      const p = new BrowserProvider(window.ethereum!);
      Promise.all([p.getSigner(), p.getNetwork()])
        .then(([s, n]) => { setSigner(s); setChainId(Number(n.chainId)); })
        .catch(() => { setSigner(null); });
    };
    const eth = window.ethereum;
    eth.on("accountsChanged", onAccountsChanged);
    eth.on("chainChanged", onChainChanged);
    return () => {
      eth.removeListener("accountsChanged", onAccountsChanged);
      eth.removeListener("chainChanged", onChainChanged);
    };
  }, []);

  return (
    <WalletContext.Provider value={{ address, chainId, isConnecting, signer, wrongChain: chainId !== null && chainId !== BASE_SEPOLIA_CHAIN_ID, connect, disconnect, switchToBaseSepolia }}>
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet() {
  return useContext(WalletContext);
}
