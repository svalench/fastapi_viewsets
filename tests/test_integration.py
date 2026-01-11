import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette import status

from fastapi_viewsets import BaseViewset, AsyncBaseViewset


@pytest.mark.integration
class TestFullCRUDCycleSync:
    """Integration tests for full CRUD cycle with synchronous viewset."""

    def test_full_crud_cycle(self, test_model, test_schema, db_session_factory, test_engine, test_app):
        """Test complete CRUD cycle: Create, Read, Update, Delete."""
        # Create tables
        from tests.conftest import TestBase
        TestBase.metadata.create_all(test_engine)
        
        viewset = BaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        # Register all methods explicitly to ensure proper routing
        viewset.register(methods=['LIST', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
        test_app.include_router(viewset)
        client = TestClient(test_app)
        
        # CREATE
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "age": 25
        }
        create_response = client.post('/users', json=user_data)
        assert create_response.status_code == 200
        created_user = create_response.json()
        user_id = created_user['id']
        assert created_user['username'] == user_data['username']
        
        # READ (GET)
        get_response = client.get(f'/users/{user_id}')
        assert get_response.status_code == 200
        assert get_response.json()['id'] == user_id
        
        # READ (LIST)
        list_response = client.get('/users?limit=10&offset=0')
        assert list_response.status_code == 200
        users = list_response.json()
        assert len(users) >= 1
        assert any(u['id'] == user_id for u in users)
        
        # UPDATE (PATCH)
        patch_data = {"username": "updateduser"}
        patch_response = client.patch(f'/users/{user_id}', json=patch_data)
        assert patch_response.status_code == 200
        assert patch_response.json()['username'] == "updateduser"
        assert patch_response.json()['email'] == user_data['email']  # unchanged
        
        # UPDATE (PUT)
        put_data = {
            "username": "putuser",
            "email": "put@example.com",
            "is_active": False,
            "age": 30
        }
        put_response = client.put(f'/users/{user_id}', json=put_data)
        assert put_response.status_code == 200
        updated_user = put_response.json()
        assert updated_user['username'] == "putuser"
        assert updated_user['email'] == "put@example.com"
        
        # DELETE
        delete_response = client.delete(f'/users/{user_id}')
        assert delete_response.status_code == 200
        assert delete_response.json()['status'] is True
        
        # Verify deletion
        get_response = client.get(f'/users/{user_id}')
        assert get_response.status_code == 404


@pytest.mark.async_test
@pytest.mark.integration
class TestFullCRUDCycleAsync:
    """Integration tests for full CRUD cycle with asynchronous viewset."""

    @pytest.mark.asyncio
    async def test_full_crud_cycle(self, test_model, test_schema, async_db_session_factory, test_async_engine, test_app):
        """Test complete CRUD cycle: Create, Read, Update, Delete (async)."""
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
        
        # Register all methods explicitly to ensure proper routing
        viewset.register(methods=['LIST', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
        test_app.include_router(viewset)
        
        from httpx import ASGITransport
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # CREATE
            user_data = {
                "username": "testuser",
                "email": "test@example.com",
                "is_active": True,
                "age": 25
            }
            create_response = await client.post('/users', json=user_data)
            assert create_response.status_code == 200
            created_user = create_response.json()
            user_id = created_user['id']
            
            # READ (GET)
            get_response = await client.get(f'/users/{user_id}')
            assert get_response.status_code == 200
            
            # UPDATE (PATCH)
            patch_response = await client.patch(f'/users/{user_id}', json={"username": "updated"})
            assert patch_response.status_code == 200
            
            # DELETE
            delete_response = await client.delete(f'/users/{user_id}')
            assert delete_response.status_code == 200


@pytest.mark.integration
class TestMultipleModels:
    """Integration tests with multiple models."""

    def test_multiple_viewsets(self, test_model, test_schema, db_session_factory, test_engine, test_app):
        """Test multiple viewsets in the same app."""
        # Create tables
        from tests.conftest import TestBase
        TestBase.metadata.create_all(test_engine)
        
        # Create two viewsets for the same model with different endpoints
        users_viewset = BaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        admin_viewset = BaseViewset(
            endpoint='/admin/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Admin']
        )
        
        # Register all methods explicitly
        users_viewset.register(methods=['LIST', 'GET', 'POST', 'PATCH', 'DELETE'])
        admin_viewset.register(methods=['LIST', 'GET', 'POST', 'PATCH', 'DELETE'])
        
        test_app.include_router(users_viewset)
        test_app.include_router(admin_viewset)
        
        client = TestClient(test_app)
        
        # Create user via first endpoint
        user_data = {
            "username": "user1",
            "email": "user1@example.com"
        }
        response1 = client.post('/users', json=user_data)
        assert response1.status_code == 200
        user_id = response1.json()['id']
        
        # Access via second endpoint
        response2 = client.get(f'/admin/users/{user_id}')
        assert response2.status_code == 200
        assert response2.json()['id'] == user_id


@pytest.mark.integration
class TestPagination:
    """Integration tests for pagination."""

    def test_pagination_works(self, test_model, test_schema, db_session_factory, test_engine, test_app, sample_users_data):
        """Test that pagination works correctly."""
        # Create tables - ensure they're created in the same engine
        from tests.conftest import TestBase
        # Tables should already be created by test_engine fixture, but ensure they exist
        TestBase.metadata.create_all(bind=test_engine)
        
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
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        # Register all methods explicitly
        viewset.register(methods=['LIST', 'GET', 'POST', 'PATCH', 'DELETE'])
        test_app.include_router(viewset)
        client = TestClient(test_app)
        
        # Get first page
        response1 = client.get('/users?limit=5&offset=0')
        assert response1.status_code == 200
        page1 = response1.json()
        assert len(page1) == 5
        
        # Get second page
        response2 = client.get('/users?limit=5&offset=5')
        assert response2.status_code == 200
        page2 = response2.json()
        assert len(page2) == 5
        
        # Verify no overlap
        page1_ids = {u['id'] for u in page1}
        page2_ids = {u['id'] for u in page2}
        assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.integration
class TestErrorHandling:
    """Integration tests for error handling."""

    def test_404_on_nonexistent_resource(self, test_model, test_schema, db_session_factory, test_engine, test_app):
        """Test 404 error on non-existent resource."""
        # Create tables
        from tests.conftest import TestBase
        TestBase.metadata.create_all(test_engine)
        
        viewset = BaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        # Register all methods explicitly to ensure proper routing
        viewset.register(methods=['LIST', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
        test_app.include_router(viewset)
        client = TestClient(test_app)
        
        # Try to get non-existent user
        response = client.get('/users/99999')
        assert response.status_code == 404
        
        # Try to update non-existent user
        response = client.patch('/users/99999', json={"username": "test"})
        assert response.status_code == 404
        
        # Try to delete non-existent user
        response = client.delete('/users/99999')
        assert response.status_code == 404

    def test_400_on_duplicate_unique_field(self, test_model, test_schema, db_session_factory, test_engine, test_app):
        """Test 400 error on duplicate unique field."""
        # Create tables
        from tests.conftest import TestBase
        TestBase.metadata.create_all(test_engine)
        
        viewset = BaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        # Register all methods explicitly
        viewset.register(methods=['LIST', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
        test_app.include_router(viewset)
        client = TestClient(test_app)
        
        user_data = {
            "username": "uniqueuser",
            "email": "unique@example.com"
        }
        
        # Create first user
        response1 = client.post('/users', json=user_data)
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = client.post('/users', json=user_data)
        assert response2.status_code == 400
        assert "integrity" in response2.json()['detail'].lower()


@pytest.mark.integration
class TestOAuthProtection:
    """Integration tests for OAuth2 protection."""

    def test_protected_endpoints_require_auth(self, test_model, test_schema, db_session_factory, test_app):
        """Test that protected endpoints require authentication."""
        oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        
        viewset = BaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        viewset.register(
            methods=['LIST', 'GET', 'POST'],
            protected_methods=['LIST', 'GET', 'POST'],
            oauth_protect=oauth2_scheme
        )
        
        test_app.include_router(viewset)
        client = TestClient(test_app)
        
        # Try to access protected endpoint without token
        response = client.get('/users')
        # Should return 401 or 403
        assert response.status_code in [401, 403]

    def test_unprotected_endpoints_work(self, test_model, test_schema, db_session_factory, test_engine, test_app):
        """Test that unprotected endpoints work without authentication."""
        # Create tables
        from tests.conftest import TestBase
        TestBase.metadata.create_all(test_engine)
        
        oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        
        viewset = BaseViewset(
            endpoint='/users',
            model=test_model,
            response_model=test_schema,
            db_session=db_session_factory,
            tags=['Users']
        )
        
        # Only protect POST, not GET
        # Register all methods explicitly
        viewset.register(
            methods=['LIST', 'GET', 'POST'],
            protected_methods=['POST'],
            oauth_protect=oauth2_scheme
        )
        
        test_app.include_router(viewset)
        client = TestClient(test_app)
        
        # LIST should work without auth (GET /users)
        response = client.get('/users')
        assert response.status_code == 200
        
        # POST should require auth
        response = client.post('/users', json={"username": "test", "email": "test@example.com"})
        assert response.status_code in [401, 403]

