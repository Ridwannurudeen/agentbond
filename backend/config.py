from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://agentbond:agentbond@localhost:5432/agentbond"
    database_url_sync: str = "postgresql://agentbond:agentbond@localhost:5432/agentbond"

    og_private_key: str = ""
    og_rpc_url: str = "https://testnet-rpc.opengradient.ai"
    chain_id: int = 131072

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
