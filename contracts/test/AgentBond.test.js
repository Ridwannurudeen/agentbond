const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AgentBond Contracts", function () {
  let owner, operator, user, resolver;
  let agentRegistry, policyRegistry, warrantyPool, claimManager;

  beforeEach(async function () {
    [owner, operator, user, resolver] = await ethers.getSigners();

    // Deploy AgentRegistry
    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    agentRegistry = await AgentRegistry.deploy(resolver.address);

    // Deploy PolicyRegistry
    const PolicyRegistry = await ethers.getContractFactory("PolicyRegistry");
    policyRegistry = await PolicyRegistry.deploy(await agentRegistry.getAddress());

    // Deploy WarrantyPool
    const WarrantyPool = await ethers.getContractFactory("WarrantyPool");
    warrantyPool = await WarrantyPool.deploy(await agentRegistry.getAddress());

    // Deploy ClaimManager
    const ClaimManager = await ethers.getContractFactory("ClaimManager");
    claimManager = await ClaimManager.deploy(
      await warrantyPool.getAddress(),
      resolver.address
    );

    // Configure
    await warrantyPool.setClaimManager(await claimManager.getAddress());
  });

  describe("AgentRegistry", function () {
    it("should register an agent", async function () {
      const tx = await agentRegistry.connect(operator).registerAgent("ipfs://test");
      const receipt = await tx.wait();
      const agent = await agentRegistry.getAgent(1);
      expect(agent.operator).to.equal(operator.address);
      expect(agent.metadataURI).to.equal("ipfs://test");
      expect(agent.trustScore).to.equal(100);
    });

    it("should emit AgentRegistered event", async function () {
      await expect(agentRegistry.connect(operator).registerAgent("ipfs://test"))
        .to.emit(agentRegistry, "AgentRegistered")
        .withArgs(1, operator.address);
    });

    it("should publish a version", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      const hash = ethers.keccak256(ethers.toUtf8Bytes("v1"));
      await agentRegistry.connect(operator).publishVersion(1, hash, 0);
      const version = await agentRegistry.getVersion(1, 0);
      expect(version.versionHash).to.equal(hash);
    });

    it("should revert if non-operator publishes version", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      const hash = ethers.keccak256(ethers.toUtf8Bytes("v1"));
      await expect(
        agentRegistry.connect(user).publishVersion(1, hash, 0)
      ).to.be.revertedWith("Not operator");
    });

    it("should set status", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await agentRegistry.connect(operator).setStatus(1, 1); // Paused
      const agent = await agentRegistry.getAgent(1);
      expect(agent.status).to.equal(1);
    });

    it("should update score (resolver only)", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await agentRegistry.connect(resolver).updateScore(1, 85, 10, 2);
      const [score, runs, violations] = await agentRegistry.getScore(1);
      expect(score).to.equal(85);
      expect(runs).to.equal(10);
      expect(violations).to.equal(2);
    });

    it("should revert updateScore from non-resolver", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await expect(
        agentRegistry.connect(user).updateScore(1, 50, 5, 1)
      ).to.be.revertedWith("Not resolver");
    });

    it("should pause agent (resolver)", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await agentRegistry.connect(resolver).pauseAgent(1);
      const agent = await agentRegistry.getAgent(1);
      expect(agent.status).to.equal(1); // Paused
    });
  });

  describe("WarrantyPool", function () {
    beforeEach(async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
    });

    it("should accept stake", async function () {
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("0.1"),
      });
      const health = await warrantyPool.getCollateralHealth(1);
      expect(health.staked).to.equal(ethers.parseEther("0.1"));
    });

    it("should emit Staked event", async function () {
      await expect(
        warrantyPool.connect(operator).stake(1, {
          value: ethers.parseEther("0.1"),
        })
      )
        .to.emit(warrantyPool, "Staked")
        .withArgs(1, ethers.parseEther("0.1"));
    });

    it("should reject stake from non-operator", async function () {
      await expect(
        warrantyPool.connect(user).stake(1, {
          value: ethers.parseEther("0.1"),
        })
      ).to.be.revertedWith("Not agent operator");
    });

    it("should reject zero stake", async function () {
      await expect(
        warrantyPool.connect(operator).stake(1, { value: 0 })
      ).to.be.revertedWith("Must stake > 0");
    });

    it("should request unstake", async function () {
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("0.1"),
      });
      await warrantyPool.connect(operator).requestUnstake(1, ethers.parseEther("0.05"));
      const health = await warrantyPool.getCollateralHealth(1);
      expect(health.staked).to.equal(ethers.parseEther("0.05"));
    });
  });

  describe("ClaimManager", function () {
    beforeEach(async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("1"),
      });
    });

    it("should submit a claim", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run1"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      const claim = await claimManager.getClaim(1);
      expect(claim.claimant).to.equal(user.address);
      expect(claim.status).to.equal(0); // Submitted
    });

    it("should reject duplicate claim for same run", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run1"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("ev1"))
      );
      await expect(
        claimManager.connect(user).submitClaim(
          runId, 1, "VALUE_LIMIT_EXCEEDED",
          ethers.keccak256(ethers.toUtf8Bytes("ev2"))
        )
      ).to.be.revertedWith("Claim already exists for this run");
    });

    it("should verify and approve claim", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run2"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await claimManager.connect(resolver).verifyClaim(1, true);
      const claim = await claimManager.getClaim(1);
      expect(claim.status).to.equal(2); // Approved
    });

    it("should verify and reject claim", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run3"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await claimManager.connect(resolver).verifyClaim(1, false);
      const claim = await claimManager.getClaim(1);
      expect(claim.status).to.equal(3); // Rejected
    });

    it("should execute payout after approval", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run4"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await claimManager.connect(resolver).verifyClaim(1, true);

      // Fund the warranty pool for payout
      await owner.sendTransaction({
        to: await warrantyPool.getAddress(),
        value: ethers.parseEther("0.1"),
      });

      const balanceBefore = await ethers.provider.getBalance(user.address);
      await claimManager.connect(resolver).executePayout(1);
      const balanceAfter = await ethers.provider.getBalance(user.address);

      const claim = await claimManager.getClaim(1);
      expect(claim.status).to.equal(4); // Paid
      expect(balanceAfter).to.be.gt(balanceBefore);
    });

    it("should revert payout on non-approved claim", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run5"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await expect(
        claimManager.connect(resolver).executePayout(1)
      ).to.be.revertedWith("Claim not approved");
    });

    it("should revert verify from non-resolver", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run6"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await expect(
        claimManager.connect(user).verifyClaim(1, true)
      ).to.be.revertedWith("Not resolver");
    });
  });
});
