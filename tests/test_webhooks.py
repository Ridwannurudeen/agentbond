"""Tests for webhook notification service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.db import Base
from backend.models.schema import Operator, Agent
from backend.services.webhooks import (
    notify_operator,
    notify_claim_submitted,
    notify_claim_resolved,
    notify_score_changed,
)


TEST_DB_URL = "sqlite+aiosqlite:///test_webhooks.db"


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Create operator with webhook
        op = Operator(wallet_address="0xwebhooktest0000000000000000000000000001")
        op.webhook_url = "https://example.com/webhook"
        op.api_key = "test-key-123"
        session.add(op)
        await session.flush()

        agent = Agent(
            operator_id=op.id,
            metadata_uri="ipfs://QmWebhookTest",
            status="active",
            trust_score=100,
        )
        session.add(agent)
        await session.flush()

        yield session, op.id, agent.id

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session_no_webhook():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        op = Operator(wallet_address="0xnowebhook000000000000000000000000000001")
        session.add(op)
        await session.flush()

        agent = Agent(
            operator_id=op.id,
            metadata_uri="ipfs://QmNoWebhook",
            status="active",
            trust_score=100,
        )
        session.add(agent)
        await session.flush()

        yield session, op.id, agent.id

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


class TestNotifyOperator:
    @pytest.mark.asyncio
    async def test_successful_delivery(self, db_session):
        session, op_id, agent_id = db_session

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("backend.services.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await notify_operator(
                session, agent_id, "test.event", {"key": "value"}
            )
            assert result is True
            mock_client.post.assert_called_once()

            # Verify the URL and payload
            call_args = mock_client.post.call_args
            assert call_args.args[0] == "https://example.com/webhook"
            payload = call_args.kwargs["json"]
            assert payload["event"] == "test.event"
            assert payload["agent_id"] == agent_id
            assert payload["data"] == {"key": "value"}

            # Verify signature header is set
            headers = call_args.kwargs["headers"]
            assert headers["X-AgentBond-Signature"] == "test-key-123"

    @pytest.mark.asyncio
    async def test_failed_delivery(self, db_session):
        session, op_id, agent_id = db_session

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("backend.services.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await notify_operator(
                session, agent_id, "test.event", {"key": "value"}
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_network_error(self, db_session):
        session, op_id, agent_id = db_session

        with patch("backend.services.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await notify_operator(
                session, agent_id, "test.event", {"key": "value"}
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_no_webhook_url(self, db_session_no_webhook):
        session, op_id, agent_id = db_session_no_webhook

        result = await notify_operator(
            session, agent_id, "test.event", {"key": "value"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_agent_not_found(self, db_session):
        session, op_id, agent_id = db_session

        result = await notify_operator(
            session, 99999, "test.event", {"key": "value"}
        )
        assert result is False


class TestWebhookHelpers:
    @pytest.mark.asyncio
    async def test_notify_claim_submitted(self, db_session):
        session, op_id, agent_id = db_session

        with patch("backend.services.webhooks.notify_operator", new_callable=AsyncMock) as mock:
            mock.return_value = True
            await notify_claim_submitted(session, agent_id, 1, "TOOL_WHITELIST_VIOLATION", "run-123")
            mock.assert_called_once_with(
                session, agent_id, "claim.submitted",
                {"claim_id": 1, "reason_code": "TOOL_WHITELIST_VIOLATION", "run_id": "run-123"},
            )

    @pytest.mark.asyncio
    async def test_notify_claim_resolved(self, db_session):
        session, op_id, agent_id = db_session

        with patch("backend.services.webhooks.notify_operator", new_callable=AsyncMock) as mock:
            mock.return_value = True
            await notify_claim_resolved(session, agent_id, 1, True, "Violation confirmed")
            mock.assert_called_once_with(
                session, agent_id, "claim.resolved",
                {"claim_id": 1, "approved": True, "reason": "Violation confirmed"},
            )

    @pytest.mark.asyncio
    async def test_notify_score_changed(self, db_session):
        session, op_id, agent_id = db_session

        with patch("backend.services.webhooks.notify_operator", new_callable=AsyncMock) as mock:
            mock.return_value = True
            await notify_score_changed(session, agent_id, 100, 85)
            mock.assert_called_once_with(
                session, agent_id, "score.changed",
                {"old_score": 100, "new_score": 85},
            )
