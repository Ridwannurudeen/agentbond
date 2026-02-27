import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WalletProvider, useWallet } from "../context/WalletContext";

// ---------------------------------------------------------------------------
// Top-level ethers mock — must be hoisted, must use a real constructor
// ---------------------------------------------------------------------------

const mockSend = vi.fn();
const mockGetNetwork = vi.fn();

vi.mock("ethers", () => ({
  BrowserProvider: function (this: unknown) {
    return { send: mockSend, getNetwork: mockGetNetwork };
  },
}));

// ---------------------------------------------------------------------------
// Minimal test consumer
// ---------------------------------------------------------------------------

function WalletDisplay() {
  const { address, chainId, isConnecting, connect, disconnect } = useWallet();
  return (
    <div>
      <div data-testid="address">{address ?? "none"}</div>
      <div data-testid="chainId">{chainId ?? "none"}</div>
      <div data-testid="connecting">{String(isConnecting)}</div>
      <button onClick={connect}>Connect</button>
      <button onClick={disconnect}>Disconnect</button>
    </div>
  );
}

function renderWallet() {
  return render(
    <WalletProvider>
      <WalletDisplay />
    </WalletProvider>
  );
}

function makeEthereumStub(accounts: string[] = []) {
  return {
    request: vi.fn(),
    on: vi.fn(),
    removeListener: vi.fn(),
    _accounts: accounts,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default: BrowserProvider.send returns empty accounts (no prior connection)
  mockSend.mockResolvedValue([]);
  mockGetNetwork.mockResolvedValue({ chainId: BigInt(1) });

  Object.defineProperty(window, "ethereum", {
    value: undefined,
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------

describe("WalletContext — initial state (no MetaMask)", () => {
  it("address is null", () => {
    renderWallet();
    expect(screen.getByTestId("address").textContent).toBe("none");
  });

  it("chainId is null", () => {
    renderWallet();
    expect(screen.getByTestId("chainId").textContent).toBe("none");
  });

  it("isConnecting is false", () => {
    renderWallet();
    expect(screen.getByTestId("connecting").textContent).toBe("false");
  });
});

describe("WalletContext — connect without MetaMask", () => {
  it("shows alert when window.ethereum is undefined", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    renderWallet();

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    });

    expect(alertSpy).toHaveBeenCalledWith(
      "MetaMask not detected. Please install MetaMask."
    );
    expect(screen.getByTestId("address").textContent).toBe("none");
  });
});

describe("WalletContext — connect with MetaMask", () => {
  const ADDR = "0xUserAddress1234567890123456789012345678";

  beforeEach(() => {
    // Set up ethereum stub so the useEffect re-hydration finds it
    const eth = makeEthereumStub([ADDR]);
    Object.defineProperty(window, "ethereum", {
      value: eth,
      writable: true,
      configurable: true,
    });
    // eth_accounts for re-hydration returns ADDR; eth_requestAccounts for connect also returns ADDR
    mockSend.mockImplementation((method: string) => {
      if (method === "eth_accounts" || method === "eth_requestAccounts")
        return Promise.resolve([ADDR]);
      return Promise.resolve([]);
    });
  });

  it("sets address after successful connect", async () => {
    renderWallet();

    // Wait for re-hydration to settle
    await waitFor(() =>
      expect(screen.getByTestId("address").textContent).toBe(ADDR)
    );
  });

  it("sets chainId after connect", async () => {
    mockGetNetwork.mockResolvedValue({ chainId: BigInt(84532) });
    renderWallet();

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    });

    await waitFor(() =>
      expect(screen.getByTestId("chainId").textContent).toBe("84532")
    );
  });
});

describe("WalletContext — disconnect", () => {
  const ADDR = "0xUserAddress1234567890123456789012345678";

  beforeEach(() => {
    const eth = makeEthereumStub([ADDR]);
    Object.defineProperty(window, "ethereum", {
      value: eth,
      writable: true,
      configurable: true,
    });
    mockSend.mockImplementation((method: string) => {
      if (method === "eth_accounts" || method === "eth_requestAccounts")
        return Promise.resolve([ADDR]);
      return Promise.resolve([]);
    });
  });

  it("clears address and chainId after disconnect", async () => {
    renderWallet();

    // Let re-hydration set address
    await waitFor(() =>
      expect(screen.getByTestId("address").textContent).toBe(ADDR)
    );

    await act(async () => {
      await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    });

    expect(screen.getByTestId("address").textContent).toBe("none");
    expect(screen.getByTestId("chainId").textContent).toBe("none");
  });
});
