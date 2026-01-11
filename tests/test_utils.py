import pytest
from fastapi import HTTPException
from starlette import status
from sqlalchemy.exc import IntegrityError

from fastapi_viewsets.utils import (
    get_list_queryset,
    get_element_by_id,
    create_element,
    update_element,
    delete_element
)


@pytest.mark.unit
class TestGetListQueryset:
    """Tests for get_list_queryset function."""

    def test_get_all_items(self, test_model, db_session_factory, sample_users_data):
        """Test getting all items without pagination."""
        session = db_session_factory()
        try:
            # Create test data
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()

            # Get all items
            result = get_list_queryset(test_model, db_session_factory)
            assert len(result) == 10
            assert all(isinstance(item, test_model) for item in result)
        finally:
            session.close()

    def test_get_items_with_limit(self, test_model, db_session_factory, sample_users_data):
        """Test getting items with limit."""
        session = db_session_factory()
        try:
            # Create test data
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()

            # Get items with limit
            result = get_list_queryset(test_model, db_session_factory, limit=5)
            assert len(result) == 5
        finally:
            session.close()

    def test_get_items_with_offset(self, test_model, db_session_factory, sample_users_data):
        """Test getting items with offset."""
        session = db_session_factory()
        try:
            # Create test data
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()

            # Get items with offset
            result = get_list_queryset(test_model, db_session_factory, offset=5)
            assert len(result) == 5
        finally:
            session.close()

    def test_get_items_with_limit_and_offset(self, test_model, db_session_factory, sample_users_data):
        """Test getting items with both limit and offset."""
        session = db_session_factory()
        try:
            # Create test data
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()

            # Get items with limit and offset
            result = get_list_queryset(test_model, db_session_factory, limit=3, offset=2)
            assert len(result) == 3
        finally:
            session.close()

    def test_get_empty_list(self, test_model, db_session_factory):
        """Test getting items from empty database."""
        result = get_list_queryset(test_model, db_session_factory)
        assert len(result) == 0
        assert result == []


@pytest.mark.unit
class TestGetElementById:
    """Tests for get_element_by_id function."""

    def test_get_existing_element(self, test_model, db_session_factory, sample_user_data):
        """Test getting an existing element by ID."""
        session = db_session_factory()
        try:
            # Create test data
            user = test_model(**sample_user_data)
            session.add(user)
            session.commit()
            session.refresh(user)

            # Get element by ID
            result = get_element_by_id(test_model, db_session_factory, user.id)
            assert result is not None
            assert result.id == user.id
            assert result.username == sample_user_data["username"]
        finally:
            session.close()

    def test_get_nonexistent_element(self, test_model, db_session_factory):
        """Test getting a non-existent element raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            get_element_by_id(test_model, db_session_factory, 999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()

    def test_get_element_with_string_id(self, test_model, db_session_factory, sample_user_data):
        """Test getting element with string ID (if supported)."""
        session = db_session_factory()
        try:
            # Create test data
            user = test_model(**sample_user_data)
            session.add(user)
            session.commit()
            session.refresh(user)

            # Get element by ID as string
            result = get_element_by_id(test_model, db_session_factory, str(user.id))
            assert result.id == user.id
        finally:
            session.close()


@pytest.mark.unit
class TestCreateElement:
    """Tests for create_element function."""

    def test_create_element_success(self, test_model, db_session_factory, sample_user_data):
        """Test successful element creation."""
        result = create_element(test_model, db_session_factory, sample_user_data)
        
        assert result is not None
        assert result.id is not None
        assert result.username == sample_user_data["username"]
        assert result.email == sample_user_data["email"]

    def test_create_element_with_optional_fields(self, test_model, db_session_factory):
        """Test creating element with optional fields."""
        data = {
            "username": "testuser",
            "email": "test@example.com"
        }
        result = create_element(test_model, db_session_factory, data)
        
        assert result is not None
        assert result.is_active is True  # default value
        assert result.age is None

    def test_create_element_integrity_error(self, test_model, db_session_factory, sample_user_data):
        """Test creating element with duplicate unique field raises IntegrityError."""
        # Create first element
        create_element(test_model, db_session_factory, sample_user_data)
        
        # Try to create duplicate
        with pytest.raises(HTTPException) as exc_info:
            create_element(test_model, db_session_factory, sample_user_data)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "integrity" in exc_info.value.detail.lower()

    def test_create_element_with_none_values(self, test_model, db_session_factory):
        """Test creating element with None values for nullable fields."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "age": None
        }
        result = create_element(test_model, db_session_factory, data)
        assert result.age is None


@pytest.mark.unit
class TestUpdateElement:
    """Tests for update_element function."""

    def test_update_element_put_full_replace(self, test_model, db_session_factory, sample_user_data):
        """Test PUT update (full replacement)."""
        # Create element
        created = create_element(test_model, db_session_factory, sample_user_data)
        
        # Update with PUT (partial=False)
        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "is_active": False,
            "age": 30
        }
        result = update_element(test_model, db_session_factory, created.id, update_data, partial=False)
        
        assert result.username == "updateduser"
        assert result.email == "updated@example.com"
        assert result.is_active is False
        assert result.age == 30

    def test_update_element_patch_partial(self, test_model, db_session_factory, sample_user_data):
        """Test PATCH update (partial update)."""
        # Create element
        created = create_element(test_model, db_session_factory, sample_user_data)
        
        # Update with PATCH (partial=True)
        update_data = {
            "username": "patcheduser"
        }
        result = update_element(test_model, db_session_factory, created.id, update_data, partial=True)
        
        assert result.username == "patcheduser"
        assert result.email == sample_user_data["email"]  # unchanged
        assert result.is_active == sample_user_data["is_active"]  # unchanged

    def test_update_element_patch_skip_none(self, test_model, db_session_factory, sample_user_data):
        """Test PATCH update skips None values."""
        # Create element
        created = create_element(test_model, db_session_factory, sample_user_data)
        
        # Update with PATCH including None
        update_data = {
            "username": "patcheduser",
            "age": None
        }
        result = update_element(test_model, db_session_factory, created.id, update_data, partial=True)
        
        assert result.username == "patcheduser"
        # age should remain unchanged (not set to None in PATCH)
        assert result.age == sample_user_data.get("age")

    def test_update_nonexistent_element(self, test_model, db_session_factory):
        """Test updating non-existent element raises 404."""
        update_data = {"username": "newuser"}
        
        with pytest.raises(HTTPException) as exc_info:
            update_element(test_model, db_session_factory, 999, update_data, partial=True)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_update_element_integrity_error(self, test_model, db_session_factory, sample_users_data):
        """Test updating element with duplicate unique field raises IntegrityError."""
        # Create two elements
        user1 = create_element(test_model, db_session_factory, sample_users_data[0])
        user2 = create_element(test_model, db_session_factory, sample_users_data[1])
        
        # Try to update user2 with user1's email
        update_data = {"email": sample_users_data[0]["email"]}
        
        with pytest.raises(HTTPException) as exc_info:
            update_element(test_model, db_session_factory, user2.id, update_data, partial=True)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "integrity" in exc_info.value.detail.lower()


@pytest.mark.unit
class TestDeleteElement:
    """Tests for delete_element function."""

    def test_delete_element_success(self, test_model, db_session_factory, sample_user_data):
        """Test successful element deletion."""
        # Create element
        created = create_element(test_model, db_session_factory, sample_user_data)
        element_id = created.id
        
        # Delete element
        result = delete_element(test_model, db_session_factory, element_id)
        assert result is True
        
        # Verify element is deleted
        with pytest.raises(HTTPException) as exc_info:
            get_element_by_id(test_model, db_session_factory, element_id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_element(self, test_model, db_session_factory):
        """Test deleting non-existent element raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            delete_element(test_model, db_session_factory, 999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_element_with_string_id(self, test_model, db_session_factory, sample_user_data):
        """Test deleting element with string ID."""
        # Create element
        created = create_element(test_model, db_session_factory, sample_user_data)
        
        # Delete with string ID
        result = delete_element(test_model, db_session_factory, str(created.id))
        assert result is True

