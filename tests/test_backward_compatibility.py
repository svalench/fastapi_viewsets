"""Tests for backward compatibility with existing code."""

import pytest
from fastapi_viewsets.utils import (
    get_list_queryset,
    get_element_by_id,
    create_element,
    update_element,
    delete_element
)
from fastapi_viewsets.async_utils import (
    get_list_queryset as async_get_list_queryset,
    get_element_by_id as async_get_element_by_id,
    create_element as async_create_element,
    update_element as async_update_element,
    delete_element as async_delete_element
)


@pytest.mark.unit
class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with existing code."""
    
    def test_utils_work_without_adapter(self, test_model, db_session_factory, sample_user_data):
        """Test that utils functions work without explicitly passing adapter."""
        session = db_session_factory()
        try:
            # Create test data
            user = test_model(**sample_user_data)
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id
        finally:
            session.close()
        
        # Test that functions work without orm_adapter parameter
        # They should use default adapter from configuration
        result = get_list_queryset(test_model, db_session_factory, limit=10)
        assert len(result) >= 1
        
        result = get_element_by_id(test_model, db_session_factory, user_id)
        assert result.id == user_id
        
        # Test create
        new_data = {
            "username": "newuser",
            "email": "new@example.com",
            "is_active": True,
            "age": 30
        }
        created = create_element(test_model, db_session_factory, new_data)
        assert created.id is not None
        
        # Test update
        updated = update_element(
            test_model,
            db_session_factory,
            created.id,
            {"username": "updateduser"},
            partial=True
        )
        assert updated.username == "updateduser"
        
        # Test delete
        result = delete_element(test_model, db_session_factory, created.id)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_async_utils_work_without_adapter(
        self, test_model, async_db_session_factory, sample_user_data
    ):
        """Test that async utils functions work without explicitly passing adapter."""
        # Create test data
        async with async_db_session_factory() as session:
            user = test_model(**sample_user_data)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id
        
        # Test that functions work without orm_adapter parameter
        result = await async_get_list_queryset(test_model, async_db_session_factory, limit=10)
        assert len(result) >= 1
        
        result = await async_get_element_by_id(test_model, async_db_session_factory, user_id)
        assert result.id == user_id
        
        # Test create
        new_data = {
            "username": "newuser",
            "email": "new@example.com",
            "is_active": True,
            "age": 30
        }
        created = await async_create_element(test_model, async_db_session_factory, new_data)
        assert created.id is not None
        
        # Test update
        updated = await async_update_element(
            test_model,
            async_db_session_factory,
            created.id,
            {"username": "updateduser"},
            partial=True
        )
        assert updated.username == "updateduser"
        
        # Test delete
        result = await async_delete_element(test_model, async_db_session_factory, created.id)
        assert result is True
    
    def test_viewset_works_with_old_api(self, test_model, test_schema, db_session_factory):
        """Test that viewset works with old API (without orm_adapter parameter)."""
        from fastapi_viewsets import BaseViewset
        
        # Old way of creating viewset (should still work)
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        # Should have default adapter
        assert viewset.orm_adapter is not None
        
        # Should work normally
        viewset.register()
        assert len(viewset.routes) > 0
    
    @pytest.mark.asyncio
    async def test_async_viewset_works_with_old_api(
        self, test_model, test_schema, async_db_session_factory
    ):
        """Test that async viewset works with old API (without orm_adapter parameter)."""
        from fastapi_viewsets import AsyncBaseViewset
        
        # Old way of creating viewset (should still work)
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=async_db_session_factory,
            tags=['Test']
        )
        
        # Should have default adapter
        assert viewset.orm_adapter is not None
        
        # Should work normally
        viewset.register()
        assert len(viewset.routes) > 0

