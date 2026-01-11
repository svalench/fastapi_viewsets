import pytest
from fastapi import HTTPException
from starlette import status

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
class TestEdgeCasesSync:
    """Edge case tests for synchronous utilities."""

    def test_get_list_with_zero_limit(self, test_model, db_session_factory, sample_users_data):
        """Test getting list with limit=0."""
        session = db_session_factory()
        try:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()
        finally:
            session.close()
        
        # limit=0 should return empty list (now that we check limit > 0)
        result = get_list_queryset(test_model, db_session_factory, limit=0)
        assert len(result) == 0

    def test_get_list_with_negative_limit(self, test_model, db_session_factory, sample_users_data):
        """Test getting list with negative limit."""
        session = db_session_factory()
        try:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()
        finally:
            session.close()
        
        # Negative limit should be treated as no limit
        result = get_list_queryset(test_model, db_session_factory, limit=-1)
        assert len(result) == 10

    def test_get_list_with_large_offset(self, test_model, db_session_factory, sample_users_data):
        """Test getting list with offset larger than total items."""
        session = db_session_factory()
        try:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()
        finally:
            session.close()
        
        result = get_list_queryset(test_model, db_session_factory, offset=100)
        assert len(result) == 0

    def test_get_element_with_zero_id(self, test_model, db_session_factory):
        """Test getting element with ID=0."""
        with pytest.raises(HTTPException) as exc_info:
            get_element_by_id(test_model, db_session_factory, 0)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_element_with_negative_id(self, test_model, db_session_factory):
        """Test getting element with negative ID."""
        with pytest.raises(HTTPException) as exc_info:
            get_element_by_id(test_model, db_session_factory, -1)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_create_element_with_empty_string(self, test_model, db_session_factory):
        """Test creating element with empty string (should fail if field is required)."""
        # Empty string for required field should cause error
        data = {
            "username": "",  # Empty string
            "email": "test@example.com"
        }
        
        # This might raise an error depending on model constraints
        # SQLAlchemy might allow it, but it's an edge case to test
        try:
            result = create_element(test_model, db_session_factory, data)
            # If it succeeds, verify the empty string was stored
            assert result.username == ""
        except HTTPException:
            # If it fails, that's also acceptable behavior
            pass

    def test_create_element_with_none_for_required_field(self, test_model, db_session_factory):
        """Test creating element with None for required field."""
        data = {
            "username": None,  # None for required field
            "email": "test@example.com"
        }
        
        # This should raise an error
        with pytest.raises(HTTPException) as exc_info:
            create_element(test_model, db_session_factory, data)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_element_with_empty_dict(self, test_model, db_session_factory, sample_user_data):
        """Test updating element with empty dictionary."""
        # Create element
        created = create_element(test_model, db_session_factory, sample_user_data)
        
        # Update with empty dict (PATCH) - should return unchanged element
        result = update_element(test_model, db_session_factory, created.id, {}, partial=True)
        assert result.username == sample_user_data["username"]
        assert result.email == sample_user_data["email"]

    def test_update_element_put_with_missing_fields(self, test_model, db_session_factory, sample_user_data):
        """Test PUT update with missing required fields (should raise error)."""
        # Create element
        created = create_element(test_model, db_session_factory, sample_user_data)
        
        # Update with PUT but missing required fields (email is required)
        update_data = {
            "username": "updated"
            # Missing email, is_active, age
        }
        
        # PUT with missing required fields should raise IntegrityError
        with pytest.raises(HTTPException) as exc_info:
            update_element(test_model, db_session_factory, created.id, update_data, partial=False)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "integrity" in exc_info.value.detail.lower() or "NOT NULL" in exc_info.value.detail

    def test_delete_element_with_zero_id(self, test_model, db_session_factory):
        """Test deleting element with ID=0."""
        with pytest.raises(HTTPException) as exc_info:
            delete_element(test_model, db_session_factory, 0)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.async_test
@pytest.mark.unit
class TestEdgeCasesAsync:
    """Edge case tests for asynchronous utilities."""

    @pytest.mark.asyncio
    async def test_get_list_with_zero_limit(self, test_model, async_db_session_factory, sample_users_data):
        """Test getting list with limit=0 (async)."""
        session_factory = async_db_session_factory
        
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()
        
        # limit=0 should return empty list (now that we check limit > 0)
        result = await async_get_list_queryset(test_model, session_factory, limit=0)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_list_with_negative_limit(self, test_model, async_db_session_factory, sample_users_data):
        """Test getting list with negative limit (async)."""
        session_factory = async_db_session_factory
        
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()
        
        result = await async_get_list_queryset(test_model, session_factory, limit=-1)
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_get_element_with_zero_id(self, test_model, async_db_session_factory):
        """Test getting element with ID=0 (async)."""
        session_factory = async_db_session_factory
        
        with pytest.raises(HTTPException) as exc_info:
            await async_get_element_by_id(test_model, session_factory, 0)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_element_with_empty_string(self, test_model, async_db_session_factory):
        """Test creating element with empty string (async)."""
        session_factory = async_db_session_factory
        data = {
            "username": "",
            "email": "test@example.com"
        }
        
        try:
            result = await async_create_element(test_model, session_factory, data)
            assert result.username == ""
        except HTTPException:
            pass

    @pytest.mark.asyncio
    async def test_update_element_with_empty_dict(self, test_model, async_db_session_factory, sample_user_data):
        """Test updating element with empty dictionary (async)."""
        session_factory = async_db_session_factory
        
        created = await async_create_element(test_model, session_factory, sample_user_data)
        result = await async_update_element(test_model, session_factory, created.id, {}, partial=True)
        assert result.username == sample_user_data["username"]


@pytest.mark.unit
class TestValidationEdgeCases:
    """Tests for validation edge cases."""

    def test_create_with_very_long_string(self, test_model, db_session_factory):
        """Test creating element with very long string."""
        data = {
            "username": "a" * 1000,  # Very long string
            "email": "test@example.com"
        }
        
        # Should either succeed or fail gracefully
        try:
            result = create_element(test_model, db_session_factory, data)
            assert len(result.username) == 1000
        except HTTPException:
            # If it fails due to length constraints, that's acceptable
            pass

    def test_create_with_special_characters(self, test_model, db_session_factory):
        """Test creating element with special characters."""
        data = {
            "username": "user@#$%^&*()",
            "email": "test+tag@example.com"
        }
        
        result = create_element(test_model, db_session_factory, data)
        assert result.username == "user@#$%^&*()"
        assert result.email == "test+tag@example.com"

    def test_update_with_unicode_characters(self, test_model, db_session_factory, sample_user_data):
        """Test updating element with unicode characters."""
        created = create_element(test_model, db_session_factory, sample_user_data)
        
        update_data = {
            "username": "пользователь"  # Unicode characters
        }
        
        result = update_element(test_model, db_session_factory, created.id, update_data, partial=True)
        assert result.username == "пользователь"


@pytest.mark.unit
class TestDatabaseErrorHandling:
    """Tests for database error handling."""

    def test_create_duplicate_unique_field(self, test_model, db_session_factory, sample_user_data):
        """Test creating element with duplicate unique field."""
        # Create first element
        create_element(test_model, db_session_factory, sample_user_data)
        
        # Try to create duplicate
        with pytest.raises(HTTPException) as exc_info:
            create_element(test_model, db_session_factory, sample_user_data)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "integrity" in exc_info.value.detail.lower()

    def test_update_to_duplicate_unique_field(self, test_model, db_session_factory, sample_users_data):
        """Test updating element to duplicate unique field value."""
        # Create two elements
        user1 = create_element(test_model, db_session_factory, sample_users_data[0])
        user2 = create_element(test_model, db_session_factory, sample_users_data[1])
        
        # Try to update user2 with user1's email
        update_data = {"email": sample_users_data[0]["email"]}
        
        with pytest.raises(HTTPException) as exc_info:
            update_element(test_model, db_session_factory, user2.id, update_data, partial=True)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "integrity" in exc_info.value.detail.lower()

