const { expect } = require("chai");
const { ethers, upgrades } = require("hardhat");

describe("AgentBond Contracts", function () {
  let owner, operator, user, resolver;
  let agentRegistry, policyRegistry, warrantyPool, claimManager;

  beforeEach(async function () {
    [owner, operator, user, resolver] = await ethers.getSigners();

    // Deploy AgentRegistry (UUPS proxy)
    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    agentRegistry = await upgrades.deployProxy(AgentRegistry, [resolver.address], {
      kind: "uups",
    });

    // Deploy PolicyRegistry (UUPS proxy)
    const PolicyRegistry = await ethers.getContractFactory("PolicyRegistry");
    policyRegistry = await upgrades.deployProxy(PolicyRegistry, [await agentRegistry.getAddress()], {
      kind: "uups",
    });

    // Deploy WarrantyPool (UUPS proxy)
    const WarrantyPool = await ethers.getContractFactory("WarrantyPool");
    warrantyPool = await upgrades.deployProxy(WarrantyPool, [await agentRegistry.getAddress()], {
      kind: "uups",
    });

    // Deploy ClaimManager (UUPS proxy)
    const ClaimManager = await ethers.getContractFactory("ClaimManager");
    claimManager = await upgrades.deployProxy(
      ClaimManager,
      [await warrantyPool.getAddress(), await agentRegistry.getAddress(), resolver.address],
      { kind: "uups" }
    );

    // Cross-contract wiring
    await warrantyPool.setClaimManager(await claimManager.getAddress());
    await agentRegistry.setWarrantyPool(await warrantyPool.getAddress());
  });

  describe("AgentRegistry", function () {
    it("should register an agent", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
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
      expect(agent.status).to.equal(1);
    });

    it("should pause agent (warranty pool)", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      const wpAddr = await warrantyPool.getAddress();
      await ethers.provider.send("hardhat_impersonateAccount", [wpAddr]);
      await owner.sendTransaction({ to: wpAddr, value: ethers.parseEther("1") });
      const wpSigner = await ethers.getSigner(wpAddr);
      await agentRegistry.connect(wpSigner).pauseAgent(1);
      const agent = await agentRegistry.getAgent(1);
      expect(agent.status).to.equal(1);
      await ethers.provider.send("hardhat_stopImpersonatingAccount", [wpAddr]);
    });

    it("should prevent operator from unpausing after resolver pause", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await agentRegistry.connect(resolver).pauseAgent(1);
      await expect(
        agentRegistry.connect(operator).setStatus(1, 0)
      ).to.be.revertedWith("Only resolver can unpause");
    });

    it("should allow resolver to unpause", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await agentRegistry.connect(resolver).pauseAgent(1);
      await agentRegistry.connect(resolver).unpauseAgent(1);
      const agent = await agentRegistry.getAgent(1);
      expect(agent.status).to.equal(0);
    });

    it("should allow operator to unpause self-initiated pause", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await agentRegistry.connect(operator).pauseAgent(1);
      await agentRegistry.connect(operator).setStatus(1, 0);
      const agent = await agentRegistry.getAgent(1);
      expect(agent.status).to.equal(0);
    });

    it("should emit ResolverUpdated event", async function () {
      await expect(agentRegistry.connect(owner).setResolver(user.address))
        .to.emit(agentRegistry, "ResolverUpdated")
        .withArgs(resolver.address, user.address);
    });

    it("should reject zero address for resolver", async function () {
      await expect(
        agentRegistry.connect(owner).setResolver(ethers.ZeroAddress)
      ).to.be.revertedWith("Zero address");
    });

    it("should be upgradeable by owner", async function () {
      const AgentRegistryV2 = await ethers.getContractFactory("AgentRegistry");
      const upgraded = await upgrades.upgradeProxy(await agentRegistry.getAddress(), AgentRegistryV2, {
        kind: "uups",
      });
      // State preserved after upgrade
      await agentRegistry.connect(operator).registerAgent("ipfs://before-upgrade");
      const agent = await upgraded.getAgent(1);
      expect(agent.operator).to.equal(operator.address);
    });

    it("should reject upgrade from non-owner", async function () {
      const AgentRegistryV2 = await ethers.getContractFactory("AgentRegistry", user);
      await expect(
        upgrades.upgradeProxy(await agentRegistry.getAddress(), AgentRegistryV2, {
          kind: "uups",
        })
      ).to.be.reverted;
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

    it("should request unstake without deducting from amount", async function () {
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("0.1"),
      });
      await warrantyPool.connect(operator).requestUnstake(1, ethers.parseEther("0.05"));
      const health = await warrantyPool.getCollateralHealth(1);
      expect(health.staked).to.equal(ethers.parseEther("0.1"));
      expect(health.free).to.equal(ethers.parseEther("0.05"));
    });

    it("should finalize unstake and deduct from amount", async function () {
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("0.1"),
      });
      await warrantyPool.connect(operator).requestUnstake(1, ethers.parseEther("0.05"));

      await ethers.provider.send("evm_increaseTime", [7 * 24 * 3600 + 1]);
      await ethers.provider.send("evm_mine");

      const balBefore = await ethers.provider.getBalance(operator.address);
      await warrantyPool.connect(operator).finalizeUnstake(1);
      const balAfter = await ethers.provider.getBalance(operator.address);

      expect(balAfter).to.be.gt(balBefore);
      const health = await warrantyPool.getCollateralHealth(1);
      expect(health.staked).to.equal(ethers.parseEther("0.05"));
    });

    it("should prevent unstake during cooldown", async function () {
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("0.1"),
      });
      await warrantyPool.connect(operator).requestUnstake(1, ethers.parseEther("0.05"));
      await expect(
        warrantyPool.connect(operator).finalizeUnstake(1)
      ).to.be.revertedWith("Cooldown not elapsed");
    });

    it("should allow slash during pending unstake", async function () {
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("0.1"),
      });
      await warrantyPool.connect(operator).requestUnstake(1, ethers.parseEther("0.05"));

      const runId = ethers.keccak256(ethers.toUtf8Bytes("run-slash"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await claimManager.connect(resolver).verifyClaim(1, true);
      await owner.sendTransaction({
        to: await warrantyPool.getAddress(),
        value: ethers.parseEther("0.1"),
      });
      await claimManager.connect(resolver).executePayout(1);

      const health = await warrantyPool.getCollateralHealth(1);
      expect(health.staked).to.equal(ethers.parseEther("0.09"));
      expect(health.free).to.equal(ethers.parseEther("0.04"));
    });

    it("should emit ClaimManagerUpdated event", async function () {
      await expect(warrantyPool.connect(owner).setClaimManager(user.address))
        .to.emit(warrantyPool, "ClaimManagerUpdated");
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
      expect(claim.status).to.equal(0);
    });

    it("should reject claim with zero runId", async function () {
      await expect(
        claimManager.connect(user).submitClaim(
          ethers.ZeroHash, 1, "TOOL_WHITELIST_VIOLATION",
          ethers.keccak256(ethers.toUtf8Bytes("evidence"))
        )
      ).to.be.revertedWith("Invalid runId");
    });

    it("should reject claim for non-existent agent", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run-fake"));
      await expect(
        claimManager.connect(user).submitClaim(
          runId, 999, "TOOL_WHITELIST_VIOLATION",
          ethers.keccak256(ethers.toUtf8Bytes("evidence"))
        )
      ).to.be.revertedWith("Agent does not exist");
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
      expect(claim.status).to.equal(2);
    });

    it("should verify and reject claim", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run3"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await claimManager.connect(resolver).verifyClaim(1, false);
      const claim = await claimManager.getClaim(1);
      expect(claim.status).to.equal(3);
    });

    it("should execute payout after approval", async function () {
      const runId = ethers.keccak256(ethers.toUtf8Bytes("run4"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );
      await claimManager.connect(resolver).verifyClaim(1, true);

      await owner.sendTransaction({
        to: await warrantyPool.getAddress(),
        value: ethers.parseEther("0.1"),
      });

      const balanceBefore = await ethers.provider.getBalance(user.address);
      await claimManager.connect(resolver).executePayout(1);
      const balanceAfter = await ethers.provider.getBalance(user.address);

      const claim = await claimManager.getClaim(1);
      expect(claim.status).to.equal(4);
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

    it("should emit ResolverUpdated event", async function () {
      await expect(claimManager.connect(owner).setResolver(user.address))
        .to.emit(claimManager, "ResolverUpdated");
    });
  });

  describe("Heartbeat", function () {
    let heartbeat;

    beforeEach(async function () {
      const Heartbeat = await ethers.getContractFactory("Heartbeat");
      heartbeat = await Heartbeat.deploy(await agentRegistry.getAddress());
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
    });

    it("should record a ping from operator", async function () {
      await heartbeat.connect(operator).ping(1);
      const status = await heartbeat.getStatus(1);
      expect(status.alive).to.be.true;
      expect(status.pinger).to.equal(operator.address);
    });

    it("should reject ping from non-operator", async function () {
      await expect(
        heartbeat.connect(user).ping(1)
      ).to.be.revertedWith("Not agent operator");
    });

    it("should reject ping for non-existent agent", async function () {
      await expect(
        heartbeat.connect(operator).ping(999)
      ).to.be.revertedWith("Agent does not exist");
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
      await ethers.provider.send("evm_increaseTime", [3601]);
      await ethers.provider.send("evm_mine");
      expect(await heartbeat.isAlive(1)).to.be.false;
    });

    it("should update lastPing on re-ping", async function () {
      await heartbeat.connect(operator).ping(1);
      const status1 = await heartbeat.getStatus(1);

      await ethers.provider.send("evm_increaseTime", [600]);
      await ethers.provider.send("evm_mine");

      await heartbeat.connect(operator).ping(1);
      const status2 = await heartbeat.getStatus(1);

      expect(status2.lastPingTime).to.be.gt(status1.lastPingTime);
      expect(status2.alive).to.be.true;
    });
  });

  describe("Upgradeability", function () {
    it("should preserve WarrantyPool state after upgrade", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await warrantyPool.connect(operator).stake(1, {
        value: ethers.parseEther("0.5"),
      });

      const WarrantyPoolV2 = await ethers.getContractFactory("WarrantyPool");
      const upgraded = await upgrades.upgradeProxy(await warrantyPool.getAddress(), WarrantyPoolV2, {
        kind: "uups",
      });

      const health = await upgraded.getCollateralHealth(1);
      expect(health.staked).to.equal(ethers.parseEther("0.5"));
    });

    it("should preserve ClaimManager state after upgrade", async function () {
      await agentRegistry.connect(operator).registerAgent("ipfs://test");
      await warrantyPool.connect(operator).stake(1, { value: ethers.parseEther("1") });

      const runId = ethers.keccak256(ethers.toUtf8Bytes("run-upgrade"));
      await claimManager.connect(user).submitClaim(
        runId, 1, "TOOL_WHITELIST_VIOLATION",
        ethers.keccak256(ethers.toUtf8Bytes("evidence"))
      );

      const ClaimManagerV2 = await ethers.getContractFactory("ClaimManager");
      const upgraded = await upgrades.upgradeProxy(await claimManager.getAddress(), ClaimManagerV2, {
        kind: "uups",
      });

      const claim = await upgraded.getClaim(1);
      expect(claim.claimant).to.equal(user.address);
    });
  });
});
