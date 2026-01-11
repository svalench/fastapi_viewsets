import pytest
from fastapi import HTTPException
from starlette import status
from sqlalchemy.exc import IntegrityError

from fastapi_viewsets.async_utils import (
    get_list_queryset,
    get_element_by_id,
    create_element,
    update_element,
    delete_element
)


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncGetListQueryset:
    """Tests for async get_list_queryset function."""

    @pytest.mark.asyncio
    async def test_get_all_items(self, test_model, async_db_session_factory, sample_users_data):
        """Test getting all items without pagination (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()

        # Get all items
        result = await get_list_queryset(test_model, session_factory)
        assert len(result) == 10
        assert all(isinstance(item, test_model) for item in result)

    @pytest.mark.asyncio
    async def test_get_items_with_limit(self, test_model, async_db_session_factory, sample_users_data):
        """Test getting items with limit (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()

        # Get items with limit
        result = await get_list_queryset(test_model, session_factory, limit=5)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_items_with_offset(self, test_model, async_db_session_factory, sample_users_data):
        """Test getting items with offset (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()

        # Get items with offset
        result = await get_list_queryset(test_model, session_factory, offset=5)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_items_with_limit_and_offset(self, test_model, async_db_session_factory, sample_users_data):
        """Test getting items with both limit and offset (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()

        # Get items with limit and offset
        result = await get_list_queryset(test_model, session_factory, limit=3, offset=2)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_empty_list(self, test_model, async_db_session_factory):
        """Test getting items from empty database (async)."""
        session_factory = async_db_session_factory
        result = await get_list_queryset(test_model, session_factory)
        assert len(result) == 0
        assert result == []


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncGetElementById:
    """Tests for async get_element_by_id function."""

    @pytest.mark.asyncio
    async def test_get_existing_element(self, test_model, async_db_session_factory, sample_user_data):
        """Test getting an existing element by ID (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            user = test_model(**sample_user_data)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id

        # Get element by ID
        result = await get_element_by_id(test_model, session_factory, user_id)
        assert result is not None
        assert result.id == user_id
        assert result.username == sample_user_data["username"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_element(self, test_model, async_db_session_factory):
        """Test getting a non-existent element raises 404 (async)."""
        session_factory = async_db_session_factory
        
        with pytest.raises(HTTPException) as exc_info:
            await get_element_by_id(test_model, session_factory, 999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_element_with_string_id(self, test_model, async_db_session_factory, sample_user_data):
        """Test getting element with string ID (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            user = test_model(**sample_user_data)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id

        # Get element by ID as string
        result = await get_element_by_id(test_model, session_factory, str(user_id))
        assert result.id == user_id


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncCreateElement:
    """Tests for async create_element function."""

    @pytest.mark.asyncio
    async def test_create_element_success(self, test_model, async_db_session_factory, sample_user_data):
        """Test successful element creation (async)."""
        session_factory = async_db_session_factory
        result = await create_element(test_model, session_factory, sample_user_data)
        
        assert result is not None
        assert result.id is not None
        assert result.username == sample_user_data["username"]
        assert result.email == sample_user_data["email"]

    @pytest.mark.asyncio
    async def test_create_element_with_optional_fields(self, test_model, async_db_session_factory):
        """Test creating element with optional fields (async)."""
        session_factory = async_db_session_factory
        data = {
            "username": "testuser",
            "email": "test@example.com"
        }
        result = await create_element(test_model, session_factory, data)
        
        assert result is not None
        assert result.is_active is True  # default value
        assert result.age is None

    @pytest.mark.asyncio
    async def test_create_element_integrity_error(self, test_model, async_db_session_factory, sample_user_data):
        """Test creating element with duplicate unique field raises IntegrityError (async)."""
        session_factory = async_db_session_factory
        
        # Create first element
        await create_element(test_model, session_factory, sample_user_data)
        
        # Try to create duplicate
        with pytest.raises(HTTPException) as exc_info:
            await create_element(test_model, session_factory, sample_user_data)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "integrity" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_element_with_none_values(self, test_model, async_db_session_factory):
        """Test creating element with None values for nullable fields (async)."""
        session_factory = async_db_session_factory
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "age": None
        }
        result = await create_element(test_model, session_factory, data)
        assert result.age is None


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncUpdateElement:
    """Tests for async update_element function."""

    @pytest.mark.asyncio
    async def test_update_element_put_full_replace(self, test_model, async_db_session_factory, sample_user_data):
        """Test PUT update (full replacement) (async)."""
        session_factory = async_db_session_factory
        
        # Create element
        created = await create_element(test_model, session_factory, sample_user_data)
        
        # Update with PUT (partial=False)
        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "is_active": False,
            "age": 30
        }
        result = await update_element(test_model, session_factory, created.id, update_data, partial=False)
        
        assert result.username == "updateduser"
        assert result.email == "updated@example.com"
        assert result.is_active is False
        assert result.age == 30

    @pytest.mark.asyncio
    async def test_update_element_patch_partial(self, test_model, async_db_session_factory, sample_user_data):
        """Test PATCH update (partial update) (async)."""
        session_factory = async_db_session_factory
        
        # Create element
        created = await create_element(test_model, session_factory, sample_user_data)
        
        # Update with PATCH (partial=True)
        update_data = {
            "username": "patcheduser"
        }
        result = await update_element(test_model, session_factory, created.id, update_data, partial=True)
        
        assert result.username == "patcheduser"
        assert result.email == sample_user_data["email"]  # unchanged
        assert result.is_active == sample_user_data["is_active"]  # unchanged

    @pytest.mark.asyncio
    async def test_update_element_patch_skip_none(self, test_model, async_db_session_factory, sample_user_data):
        """Test PATCH update skips None values (async)."""
        session_factory = async_db_session_factory
        
        # Create element
        created = await create_element(test_model, session_factory, sample_user_data)
        
        # Update with PATCH including None
        update_data = {
            "username": "patcheduser",
            "age": None
        }
        result = await update_element(test_model, session_factory, created.id, update_data, partial=True)
        
        assert result.username == "patcheduser"
        # age should remain unchanged (not set to None in PATCH)
        assert result.age == sample_user_data.get("age")

    @pytest.mark.asyncio
    async def test_update_nonexistent_element(self, test_model, async_db_session_factory):
        """Test updating non-existent element raises 404 (async)."""
        session_factory = async_db_session_factory
        update_data = {"username": "newuser"}
        
        with pytest.raises(HTTPException) as exc_info:
            await update_element(test_model, session_factory, 999, update_data, partial=True)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_element_integrity_error(self, test_model, async_db_session_factory, sample_users_data):
        """Test updating element with duplicate unique field raises IntegrityError (async)."""
        session_factory = async_db_session_factory
        
        # Create two elements
        user1 = await create_element(test_model, session_factory, sample_users_data[0])
        user2 = await create_element(test_model, session_factory, sample_users_data[1])
        
        # Try to update user2 with user1's email
        update_data = {"email": sample_users_data[0]["email"]}
        
        with pytest.raises(HTTPException) as exc_info:
            await update_element(test_model, session_factory, user2.id, update_data, partial=True)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "integrity" in exc_info.value.detail.lower()


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncDeleteElement:
    """Tests for async delete_element function."""

    @pytest.mark.asyncio
    async def test_delete_element_success(self, test_model, async_db_session_factory, sample_user_data):
        """Test successful element deletion (async)."""
        session_factory = async_db_session_factory
        
        # Create element
        created = await create_element(test_model, session_factory, sample_user_data)
        element_id = created.id
        
        # Delete element
        result = await delete_element(test_model, session_factory, element_id)
        assert result is True
        
        # Verify element is deleted
        with pytest.raises(HTTPException) as exc_info:
            await get_element_by_id(test_model, session_factory, element_id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_nonexistent_element(self, test_model, async_db_session_factory):
        """Test deleting non-existent element raises 404 (async)."""
        session_factory = async_db_session_factory
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_element(test_model, session_factory, 999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_element_with_string_id(self, test_model, async_db_session_factory, sample_user_data):
        """Test deleting element with string ID (async)."""
        session_factory = async_db_session_factory
        
        # Create element
        created = await create_element(test_model, session_factory, sample_user_data)
        
        # Delete with string ID
        result = await delete_element(test_model, session_factory, str(created.id))
        assert result is True

