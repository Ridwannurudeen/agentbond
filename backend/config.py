from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///agentbond.db"
    database_url_sync: str = "sqlite:///agentbond.db"

    og_private_key: str = ""
    og_rpc_url: str = "https://ogevmdevnet.opengradient.ai"
    chain_id: int = 10740

    # Contract network (may differ from OG inference network)
    contract_rpc_url: str = "https://sepolia.base.org"
    contract_chain_id: int = 84532

    # Deployed contract addresses (set after deployment)
    agent_registry_address: str = ""
    policy_registry_address: str = ""
    warranty_pool_address: str = ""
    claim_manager_address: str = ""

    resolver_address: str = ""
    deployer_private_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
