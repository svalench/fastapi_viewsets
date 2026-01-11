import pytest
from fastapi import FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer
from starlette import status
from httpx import AsyncClient

from fastapi_viewsets import AsyncBaseViewset


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncBaseViewsetInit:
    """Tests for AsyncBaseViewset initialization."""

    def test_init_with_all_params(self, test_model, test_schema, async_db_session_factory):
        """Test initialization with all parameters (async)."""
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=async_db_session_factory,
            tags=['Test']
        )
        
        assert viewset.endpoint == '/test'
        assert viewset.model == test_model
        assert viewset.response_model == test_schema
        assert viewset.db_session == async_db_session_factory
        assert viewset.tags == ['Test']

    def test_init_with_minimal_params(self, test_model, test_schema):
        """Test initialization with minimal parameters (async)."""
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema
        )
        
        assert viewset.endpoint == '/test'
        assert viewset.model == test_model
        assert viewset.response_model == test_schema

    def test_init_inherits_from_apirouter(self, test_model, test_schema):
        """Test that AsyncBaseViewset inherits from APIRouter."""
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema
        )
        
        from fastapi import APIRouter
        assert isinstance(viewset, APIRouter)


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncBaseViewsetRegister:
    """Tests for AsyncBaseViewset register method."""

    def test_register_all_methods(self, test_model, test_schema, async_db_session_factory):
        """Test registering all CRUD methods (async)."""
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=async_db_session_factory,
            tags=['Test']
        )
        
        viewset.register()
        
        # Check that routes are registered
        assert len(viewset.routes) > 0

    def test_register_selected_methods(self, test_model, test_schema, async_db_session_factory):
        """Test registering only selected methods (async)."""
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=async_db_session_factory,
            tags=['Test']
        )
        
        viewset.register(methods=['LIST', 'GET', 'POST'])
        
        route_methods = []
        for route in viewset.routes:
            route_methods.extend(route.methods)
        
        assert 'GET' in route_methods
        assert 'POST' in route_methods
        assert 'DELETE' not in route_methods

    def test_register_with_oauth_protection(self, test_model, test_schema, async_db_session_factory):
        """Test registering methods with OAuth2 protection (async)."""
        oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=async_db_session_factory,
            tags=['Test']
        )
        
        viewset.register(
            methods=['LIST', 'GET'],
            protected_methods=['LIST', 'GET'],
            oauth_protect=oauth2_scheme
        )
        
        # Routes should be registered
        assert len(viewset.routes) > 0


@pytest.mark.async_test
@pytest.mark.unit
class TestAsyncBaseViewsetCRUD:
    """Tests for AsyncBaseViewset CRUD methods."""

    @pytest.mark.asyncio
    async def test_list_method(self, test_model, test_schema, async_db_session_factory, sample_users_data):
        """Test list method returns all items (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()
        
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Test']
        )
        
        result = await viewset.list(limit=10, offset=0)
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, test_model, test_schema, async_db_session_factory, sample_users_data):
        """Test list method with pagination (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            for data in sample_users_data:
                user = test_model(**data)
                session.add(user)
            await session.commit()
        
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Test']
        )
        
        result = await viewset.list(limit=5, offset=0)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_element_method(self, test_model, test_schema, async_db_session_factory, sample_user_data):
        """Test get_element method (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        async with session_factory() as session:
            user = test_model(**sample_user_data)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id
        
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Test']
        )
        
        result = await viewset.get_element(user_id)
        assert result.id == user_id
        assert result.username == sample_user_data["username"]

    @pytest.mark.asyncio
    async def test_get_element_not_found(self, test_model, test_schema, async_db_session_factory):
        """Test get_element method with non-existent ID (async)."""
        session_factory = async_db_session_factory
        
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Test']
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await viewset.get_element(999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_element_method(self, test_model, test_schema, async_db_session_factory, sample_user_data):
        """Test create_element method (async)."""
        session_factory = async_db_session_factory
        
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Test']
        )
        
        # Create schema instance
        from tests.conftest import TestUserSchema
        user_schema = TestUserSchema(**sample_user_data)
        
        result = await viewset.create_element(item=user_schema)
        assert result.id is not None
        assert result.username == sample_user_data["username"]

    @pytest.mark.asyncio
    async def test_update_element_patch(self, test_model, test_schema, async_db_session_factory, sample_user_data):
        """Test update_element method with PATCH (async)."""
        session_factory = async_db_session_factory
        
        # Create test data
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Test']
        )
        
        from tests.conftest import TestUserSchema
        user_schema = TestUserSchema(**sample_user_data)
        created = await viewset.create_element(item=user_schema)
        
        # Update with PATCH
        update_data = {"username": "patcheduser"}
        update_schema = TestUserSchema(**update_data)
        
        result = await viewset.update_element(id=created.id, item=update_schema, partial=True)
        assert result.username == "patcheduser"
        assert result.email == sample_user_data["email"]  # unchanged

    @pytest.mark.asyncio
    async def test_delete_element_method(self, test_model, test_schema, async_db_session_factory, sample_user_data):
        """Test delete_element method (async)."""
        session_factory = async_db_session_factory
        
        viewset = AsyncBaseViewset(
            endpoint='/test',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Test']
        )
        
        # Create element
        from tests.conftest import TestUserSchema
        user_schema = TestUserSchema(**sample_user_data)
        created = await viewset.create_element(item=user_schema)
        
        # Delete element
        result = await viewset.delete_element(created.id)
        assert result['status'] is True
        assert result['text'] == "successfully deleted"
        
        # Verify deletion
        with pytest.raises(HTTPException):
            await viewset.get_element(created.id)


@pytest.mark.async_test
@pytest.mark.integration
class TestAsyncBaseViewsetIntegration:
    """Integration tests for AsyncBaseViewset with FastAPI."""

    @pytest.mark.asyncio
    async def test_viewset_in_fastapi_app(self, test_model, test_schema, async_db_session_factory, test_async_engine, test_app, sample_user_data):
        """Test async viewset integrated with FastAPI app."""
        session_factory = async_db_session_factory
        
        # Create tables
        from tests.conftest import TestBase
        async with test_async_engine.begin() as conn:
            await conn.run_sync(TestBase.metadata.create_all)
        
        viewset = AsyncBaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=session_factory,
            tags=['Users']
        )
        
        viewset.register(methods=['LIST', 'GET', 'POST', 'PATCH', 'DELETE'])
        test_app.include_router(viewset)
        
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Test LIST endpoint - use GET method explicitly
            response = await client.request('GET', '/users', params={'limit': 10, 'offset': 0})
            assert response.status_code == 200
            
            # Test POST endpoint
            response = await client.post('/users', json=sample_user_data)
            assert response.status_code == 200
            data = response.json()
            assert data['username'] == sample_user_data['username']
            
            user_id = data['id']
            
            # Test GET endpoint
            response = await client.get(f'/users/{user_id}')
            assert response.status_code == 200
            assert response.json()['id'] == user_id
            
            # Test PATCH endpoint
            response = await client.patch(f'/users/{user_id}', json={"username": "updated"})
            assert response.status_code == 200
            assert response.json()['username'] == "updated"
            
            # Test DELETE endpoint
            response = await client.delete(f'/users/{user_id}')
            assert response.status_code == 200
            assert response.json()['status'] is True

