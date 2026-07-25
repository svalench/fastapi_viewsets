"""Tests for TortoiseAdapter public lifecycle methods (initialize/close).

These tests use mocking so they run even when tortoise-orm is not installed
(which is the case in CI — only the [test] extra is installed there).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi_viewsets.orm import tortoise_adapter as ta_module
from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter


@pytest.fixture
def adapter():
    """Create a TortoiseAdapter for testing, mocking TORTOISE_AVAILABLE."""
    with patch.object(ta_module, "TORTOISE_AVAILABLE", True):
        adapter = TortoiseAdapter(
            database_url="sqlite://:memory:",
            models=["tests.models"],
            app_label="models",
        )
    return adapter


def _mock_tortoise():
    """Create a MagicMock that simulates the Tortoise class."""
    mock = MagicMock()
    mock.generate_schemas = AsyncMock()
    mock.close_connections = AsyncMock()
    mock.init = AsyncMock()
    return mock


@pytest.mark.unit
class TestTortoiseAdapterLifecycle:
    """Tests for initialize() and close() public methods."""

    @pytest.mark.async_test
    async def test_initialize_without_schemas(self, adapter):
        """initialize() calls _ensure_initialized but not generate_schemas."""
        mock_tortoise = _mock_tortoise()
        with patch.object(
            adapter, "_ensure_initialized", new=AsyncMock()
        ) as mock_init, patch.object(
            ta_module, "Tortoise", mock_tortoise, create=True
        ):
            await adapter.initialize(generate_schemas=False)
            mock_init.assert_awaited_once()
            mock_tortoise.generate_schemas.assert_not_awaited()

    @pytest.mark.async_test
    async def test_initialize_with_schemas(self, adapter):
        """initialize(generate_schemas=True) calls both init and generate_schemas."""
        mock_tortoise = _mock_tortoise()
        with patch.object(
            adapter, "_ensure_initialized", new=AsyncMock()
        ) as mock_init, patch.object(
            ta_module, "Tortoise", mock_tortoise, create=True
        ):
            await adapter.initialize(generate_schemas=True)
            mock_init.assert_awaited_once()
            mock_tortoise.generate_schemas.assert_awaited_once_with(safe=True)

    @pytest.mark.async_test
    async def test_close_calls_tortoise_close(self, adapter):
        """close() calls Tortoise.close_connections() and resets _initialized."""
        mock_tortoise = _mock_tortoise()
        adapter._initialized = True
        with patch.object(
            ta_module, "Tortoise", mock_tortoise, create=True
        ):
            await adapter.close()
            mock_tortoise.close_connections.assert_awaited_once()
            assert adapter._initialized is False

    @pytest.mark.async_test
    async def test_close_resets_initialized_even_if_already_false(self, adapter):
        """close() works even when adapter was never initialized."""
        mock_tortoise = _mock_tortoise()
        assert adapter._initialized is False
        with patch.object(
            ta_module, "Tortoise", mock_tortoise, create=True
        ):
            await adapter.close()
            mock_tortoise.close_connections.assert_awaited_once()
            assert adapter._initialized is False

    @pytest.mark.async_test
    async def test_initialize_is_idempotent(self, adapter):
        """Calling initialize() twice does not error."""
        mock_tortoise = _mock_tortoise()
        with patch.object(
            adapter, "_ensure_initialized", new=AsyncMock()
        ) as mock_init, patch.object(
            ta_module, "Tortoise", mock_tortoise, create=True
        ):
            await adapter.initialize()
            await adapter.initialize()
            assert mock_init.await_count == 2
