import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from starlette import status

from fastapi_viewsets import BaseViewset


@pytest.mark.unit
class TestBaseViewsetInit:
    """Tests for BaseViewset initialization."""

    def test_init_with_all_params(self, test_model, test_schema, db_session_factory):
        """Test initialization with all parameters."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        assert viewset.endpoint == '/test'
        assert viewset.model == test_model
        assert viewset.response_model == test_schema
        assert viewset.db_session == db_session_factory
        assert viewset.tags == ['Test']

    def test_init_with_minimal_params(self, test_model, test_schema):
        """Test initialization with minimal parameters."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema
        )
        
        assert viewset.endpoint == '/test'
        assert viewset.model == test_model
        assert viewset.response_model == test_schema

    def test_init_inherits_from_apirouter(self, test_model, test_schema):
        """Test that BaseViewset inherits from APIRouter."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema
        )
        
        from fastapi import APIRouter
        assert isinstance(viewset, APIRouter)


@pytest.mark.unit
class TestBaseViewsetRegister:
    """Tests for BaseViewset register method."""

    def test_register_all_methods(self, test_model, test_schema, db_session_factory):
        """Test registering all CRUD methods."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        viewset.register()
        
        # Check that routes are registered
        assert len(viewset.routes) > 0
        # Should have routes for LIST, GET, POST, PUT, PATCH, DELETE
        route_paths = [route.path for route in viewset.routes]
        assert '/test' in route_paths  # LIST and POST
        assert any('/test/{id}' in path or path == '/test/{id}' for path in route_paths)  # GET

    def test_register_selected_methods(self, test_model, test_schema, db_session_factory):
        """Test registering only selected methods."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        viewset.register(methods=['LIST', 'GET', 'POST'])
        
        route_methods = []
        for route in viewset.routes:
            route_methods.extend(route.methods)
        
        assert 'GET' in route_methods
        assert 'POST' in route_methods
        assert 'DELETE' not in route_methods

    def test_register_with_oauth_protection(self, test_model, test_schema, db_session_factory):
        """Test registering methods with OAuth2 protection."""
        oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        viewset.register(
            methods=['LIST', 'GET'],
            protected_methods=['LIST', 'GET'],
            oauth_protect=oauth2_scheme
        )
        
        # Routes should be registered
        assert len(viewset.routes) > 0

    def test_register_invalid_methods(self, test_model, test_schema):
        """Test registering with invalid methods raises error."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema
        )
        
        with pytest.raises(ValueError):
            viewset.register(methods="INVALID")  # Should be a list


@pytest.mark.unit
class TestBaseViewsetCRUD:
    """Tests for BaseViewset CRUD methods."""

    def test_list_method(self, test_model, test_schema, db_session_factory, sample_users_data):
        """Test list method returns all items."""
        # Create test data
        session = db_session_factory()
        try:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()
        finally:
            session.close()
        
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        result = viewset.list(limit=10, offset=0)
        assert len(result) == 10

    def test_list_with_pagination(self, test_model, test_schema, db_session_factory, sample_users_data):
        """Test list method with pagination."""
        # Create test data
        session = db_session_factory()
        try:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            session.commit()
        finally:
            session.close()
        
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        result = viewset.list(limit=5, offset=0)
        assert len(result) == 5

    def test_get_element_method(self, test_model, test_schema, db_session_factory, sample_user_data):
        """Test get_element method."""
        # Create test data
        session = db_session_factory()
        try:
            user = test_model(**sample_user_data)
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id
        finally:
            session.close()
        
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        result = viewset.get_element(user_id)
        assert result.id == user_id
        assert result.username == sample_user_data["username"]

    def test_get_element_not_found(self, test_model, test_schema, db_session_factory):
        """Test get_element method with non-existent ID."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        with pytest.raises(HTTPException) as exc_info:
            viewset.get_element(999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_create_element_method(self, test_model, test_schema, db_session_factory, sample_user_data):
        """Test create_element method."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        # Create schema instance
        from tests.conftest import TestUserSchema
        user_schema = TestUserSchema(**sample_user_data)
        
        result = viewset.create_element(item=user_schema)
        assert result.id is not None
        assert result.username == sample_user_data["username"]

    def test_update_element_put(self, test_model, test_schema, db_session_factory, sample_user_data):
        """Test update_element method with PUT (full replacement)."""
        # Create test data
        session = db_session_factory()
        try:
            user = test_model(**sample_user_data)
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id
        finally:
            session.close()
        
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        from tests.conftest import TestUserSchema
        # Get current user data first
        current_user = viewset.get_element(user_id)
        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "is_active": False,
            "age": 30
        }
        user_schema = TestUserSchema(**update_data)
        
        result = viewset.update_element(id=user_id, item=user_schema, partial=False)
        assert result.username == "updateduser"
        assert result.email == "updated@example.com"

    def test_update_element_patch(self, test_model, test_schema, db_session_factory, sample_user_data):
        """Test update_element method with PATCH (partial update)."""
        # Create test data
        session = db_session_factory()
        try:
            user = test_model(**sample_user_data)
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id
        finally:
            session.close()
        
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        from tests.conftest import TestUserSchema
        update_data = {"username": "patcheduser"}
        user_schema = TestUserSchema(**update_data)
        
        result = viewset.update_element(id=user_id, item=user_schema, partial=True)
        assert result.username == "patcheduser"
        assert result.email == sample_user_data["email"]  # unchanged

    def test_delete_element_method(self, test_model, test_schema, db_session_factory, sample_user_data):
        """Test delete_element method."""
        # Create test data
        session = db_session_factory()
        try:
            user = test_model(**sample_user_data)
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id
        finally:
            session.close()
        
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        result = viewset.delete_element(user_id)
        assert result['status'] is True
        assert result['text'] == "successfully deleted"
        
        # Verify deletion
        with pytest.raises(HTTPException):
            viewset.get_element(user_id)

    def test_delete_element_not_found(self, test_model, test_schema, db_session_factory):
        """Test delete_element method with non-existent ID."""
        viewset = BaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Test']
        )
        
        with pytest.raises(HTTPException) as exc_info:
            viewset.delete_element(999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestBaseViewsetIntegration:
    """Integration tests for BaseViewset with FastAPI."""

    def test_viewset_in_fastapi_app(self, test_model, test_schema, db_session_factory, test_engine, test_app, sample_user_data):
        """Test viewset integrated with FastAPI app."""
        # Create tables using the same engine that db_session_factory uses
        from tests.conftest import TestBase
        # Ensure tables are created before using them
        TestBase.metadata.create_all(bind=test_engine)
        
        viewset = BaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        # Explicitly register LIST and other methods
        viewset.register(methods=['LIST', 'GET', 'POST', 'PATCH', 'DELETE'])
        test_app.include_router(viewset)
        
        client = TestClient(test_app)
        
        # Test LIST endpoint
        response = client.get('/users?limit=10&offset=0')
        assert response.status_code == 200
        
        # Test POST endpoint
        response = client.post('/users', json=sample_user_data)
        assert response.status_code == 200
        data = response.json()
        assert data['username'] == sample_user_data['username']
        
        user_id = data['id']
        
        # Test GET endpoint
        response = client.get(f'/users/{user_id}')
        assert response.status_code == 200
        assert response.json()['id'] == user_id
        
        # Test PATCH endpoint
        response = client.patch(f'/users/{user_id}', json={"username": "updated"})
        assert response.status_code == 200
        assert response.json()['username'] == "updated"
        
        # Test DELETE endpoint
        response = client.delete(f'/users/{user_id}')
        assert response.status_code == 200
        assert response.json()['status'] is True

