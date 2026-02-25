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

  describe("Heartbeat", function () {
    let heartbeat;

    beforeEach(async function () {
      const Heartbeat = await ethers.getContractFactory("Heartbeat");
      heartbeat = await Heartbeat.deploy();
    });

    it("should record a ping", async function () {
      await heartbeat.connect(operator).ping(1);
      const status = await heartbeat.getStatus(1);
      expect(status.alive).to.be.true;
      expect(status.pinger).to.equal(operator.address);
    });

    it("should emit Ping event", async function () {
      const tx = await heartbeat.connect(operator).ping(1);
      const receipt = await tx.wait();
      const block = await ethers.provider.getBlock(receipt.blockNumber);

      await expect(tx)
        .to.emit(heartbeat, "Ping")
        .withArgs(1, operator.address, block.timestamp);
    });

    it("should report not alive for unpinged agent", async function () {
      expect(await heartbeat.isAlive(999)).to.be.false;
    });

    it("should report alive within threshold", async function () {
      await heartbeat.connect(operator).ping(1);
      expect(await heartbeat.isAlive(1)).to.be.true;
    });

    it("should report not alive after threshold", async function () {
      await heartbeat.connect(operator).ping(1);

      // Advance time by 1 hour + 1 second
      await ethers.provider.send("evm_increaseTime", [3601]);
      await ethers.provider.send("evm_mine");

      expect(await heartbeat.isAlive(1)).to.be.false;
    });

    it("should track multiple agents independently", async function () {
      await heartbeat.connect(operator).ping(1);
      await heartbeat.connect(user).ping(2);

      const status1 = await heartbeat.getStatus(1);
      const status2 = await heartbeat.getStatus(2);

      expect(status1.pinger).to.equal(operator.address);
      expect(status2.pinger).to.equal(user.address);
      expect(status1.alive).to.be.true;
      expect(status2.alive).to.be.true;
    });

    it("should return max age for unpinged agent", async function () {
      const status = await heartbeat.getStatus(999);
      expect(status.alive).to.be.false;
      expect(status.lastPingTime).to.equal(0);
      // age should be type(uint256).max
      expect(status.age).to.equal(ethers.MaxUint256);
    });

    it("should update lastPing on re-ping", async function () {
      await heartbeat.connect(operator).ping(1);
      const status1 = await heartbeat.getStatus(1);

      // Advance time
      await ethers.provider.send("evm_increaseTime", [600]);
      await ethers.provider.send("evm_mine");

      await heartbeat.connect(operator).ping(1);
      const status2 = await heartbeat.getStatus(1);

      expect(status2.lastPingTime).to.be.gt(status1.lastPingTime);
      expect(status2.alive).to.be.true;
    });
  });
});
