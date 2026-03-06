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
  connect: () => Promise<void>;
  disconnect: () => void;
}

const WalletContext = createContext<WalletContextValue>({
  address: null,
  chainId: null,
  isConnecting: false,
  signer: null,
  connect: async () => {},
  disconnect: () => {},
});

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [address, setAddress] = useState<string | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [signer, setSigner] = useState<JsonRpcSigner | null>(null);

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
        setChainId(Number(network.chainId));
        const s = await provider.getSigner();
        setSigner(s);
      }
    } catch (err) {
      console.error("Wallet connect failed:", err);
    } finally {
      setIsConnecting(false);
    }
  }, []);

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
        setAddress(accounts[0]);
        const network = await provider.getNetwork();
        setChainId(Number(network.chainId));
        try {
          const s = await provider.getSigner();
          setSigner(s);
        } catch { /* signer not available */ }
      }
    });

    // Listen for account / chain changes
    const onAccountsChanged = (...args: unknown[]) => {
      const accounts = args[0] as string[];
      if (accounts.length > 0) {
        setAddress(accounts[0]);
      } else {
        setAddress(null);
        setSigner(null);
      }
    };
    const onChainChanged = (...args: unknown[]) => {
      setChainId(parseInt(args[0] as string, 16));
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
    <WalletContext.Provider value={{ address, chainId, isConnecting, signer, connect, disconnect }}>
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet() {
  return useContext(WalletContext);
}
