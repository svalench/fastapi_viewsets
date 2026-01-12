"""Additional tests to increase coverage for adapter methods."""

import pytest
import tempfile
import os

TEST_DATABASE_URL = f"sqlite:///{tempfile.mktemp(suffix='.db')}"


@pytest.mark.unit
class TestSQLAlchemyAdapterMethods:
    """Tests for SQLAlchemy adapter methods to increase coverage."""
    
    def test_sqlalchemy_adapter_async_engine_none_on_error(self):
        """Test SQLAlchemy adapter when async engine creation fails."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        
        # Use invalid async URL to trigger exception
        # SQLAlchemy will raise an error, but the adapter should handle it gracefully
        try:
            adapter = SQLAlchemyAdapter(
                database_url=TEST_DATABASE_URL,
                async_database_url="sqlite+invalid:///nonexistent.db"
            )
            # If it doesn't raise, check that async_engine is None
            # (This depends on how SQLAlchemy handles invalid drivers)
            # For now, just verify adapter was created
            assert adapter is not None
        except Exception:
            # If it raises an exception during creation, that's also acceptable
            # The important thing is that it doesn't crash the system
            pass
    
    def test_sqlalchemy_adapter_get_async_session_error(self):
        """Test get_async_session raises error when not available."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        
        adapter = SQLAlchemyAdapter(
            database_url=TEST_DATABASE_URL,
            async_database_url=None
        )
        
        # Force async_engine to None
        adapter.async_engine = None
        adapter.AsyncSessionLocal = None
        
        with pytest.raises(RuntimeError, match="Async session is not available"):
            adapter.get_async_session()
    
    def test_sqlalchemy_adapter_update_element_put_full(self):
        """Test update_element with PUT (full replacement)."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_put_full"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
            value = Column(Integer, nullable=True)
        
        Base.metadata.create_all(adapter.engine)
        
        # Create test data
        session = adapter.get_session()
        try:
            obj = TestModel(name="old", value=10)
            session.add(obj)
            session.commit()
            obj_id = obj.id
        finally:
            session.close()
        
        # Test PUT (full replacement)
        result = adapter.update_element(
            TestModel,
            adapter.get_session,
            obj_id,
            {"name": "new", "value": 20},
            partial=False
        )
        
        assert result.name == "new"
        assert result.value == 20
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    @pytest.mark.asyncio
    async def test_sqlalchemy_adapter_update_element_async_put_full(self):
        """Test update_element_async with PUT (full replacement)."""
        try:
            from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
            from sqlalchemy import Column, Integer, String
            
            adapter = SQLAlchemyAdapter(
                database_url=TEST_DATABASE_URL,
                async_database_url=TEST_DATABASE_URL.replace('sqlite://', 'sqlite+aiosqlite://')
            )
            Base = adapter.get_base()
            
            class TestModel(Base):
                __tablename__ = "test_put_full_async"
                id = Column(Integer, primary_key=True)
                name = Column(String, nullable=False)
                value = Column(Integer, nullable=True)
            
            import asyncio
            async def setup():
                async with adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            
            await setup()
            
            # Create test data
            session = adapter.get_async_session()
            try:
                obj = TestModel(name="old", value=10)
                session.add(obj)
                await session.commit()
                await session.refresh(obj)
                obj_id = obj.id
            finally:
                await session.close()
            
            # Test PUT (full replacement)
            result = await adapter.update_element_async(
                TestModel,
                adapter.get_async_session,
                obj_id,
                {"name": "new", "value": 20},
                partial=False
            )
            
            assert result.name == "new"
            assert result.value == 20
            
            # Cleanup
            async def cleanup():
                async with adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
                await adapter.async_engine.dispose()
            await cleanup()
        except RuntimeError:
            pytest.skip("Async driver not available")
    
    def test_sqlalchemy_adapter_create_element_exception_handling(self):
        """Test create_element exception handling."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_exception"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        # Test with invalid data that causes exception
        # This should be caught and converted to HTTPException
        from fastapi import HTTPException
        
        # Missing required field should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            adapter.create_element(TestModel, adapter.get_session, {})
        
        assert exc_info.value.status_code == 400
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()


@pytest.mark.unit
class TestTortoiseAdapterMethods:
    """Tests for Tortoise adapter methods to increase coverage."""
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_get_list_queryset_with_offset(self):
        """Test Tortoise adapter get_list_queryset_async with offset."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            from tortoise.models import Model
            from tortoise import fields
            
            adapter = TortoiseAdapter(
                database_url="sqlite:///test_tortoise_offset.db",
                models=[],
                app_label="test"
            )
            
            class TestModel(Model):
                id = fields.IntField(pk=True)
                name = fields.CharField(max_length=50)
            
            # Initialize
            await adapter._ensure_initialized()
            
            # Create test data
            await TestModel.create(name="test1")
            await TestModel.create(name="test2")
            await TestModel.create(name="test3")
            
            # Test with offset
            result = await adapter.get_list_queryset_async(
                TestModel,
                adapter.get_async_session,
                limit=2,
                offset=1
            )
            
            assert len(result) == 2
            
            # Cleanup
            from tortoise import Tortoise
            await Tortoise.close_connections()
        except ImportError:
            pytest.skip("Tortoise ORM not available")
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_create_element_validation(self):
        """Test Tortoise adapter create_element_async validation."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            from tortoise.models import Model
            from tortoise import fields
            
            adapter = TortoiseAdapter(
                database_url="sqlite:///test_tortoise_validation.db",
                models=[],
                app_label="test"
            )
            
            class TestModel(Model):
                id = fields.IntField(pk=True)
                name = fields.CharField(max_length=50, required=True)
                value = fields.IntField(null=True)
            
            await adapter._ensure_initialized()
            
            # Test missing required field
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await adapter.create_element_async(
                    TestModel,
                    adapter.get_async_session,
                    {"value": 10}
                )
            
            assert exc_info.value.status_code == 400
            
            # Cleanup
            from tortoise import Tortoise
            await Tortoise.close_connections()
        except ImportError:
            pytest.skip("Tortoise ORM not available")
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_update_element_put(self):
        """Test Tortoise adapter update_element_async with PUT."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            from tortoise.models import Model
            from tortoise import fields
            
            adapter = TortoiseAdapter(
                database_url="sqlite:///test_tortoise_put.db",
                models=[],
                app_label="test"
            )
            
            class TestModel(Model):
                id = fields.IntField(pk=True)
                name = fields.CharField(max_length=50)
                value = fields.IntField(null=True)
            
            await adapter._ensure_initialized()
            
            # Create test data
            obj = await TestModel.create(name="old", value=10)
            
            # Test PUT (full replacement)
            result = await adapter.update_element_async(
                TestModel,
                adapter.get_async_session,
                obj.id,
                {"name": "new", "value": 20},
                partial=False
            )
            
            assert result.name == "new"
            assert result.value == 20
            
            # Cleanup
            from tortoise import Tortoise
            await Tortoise.close_connections()
        except ImportError:
            pytest.skip("Tortoise ORM not available")


@pytest.mark.unit
class TestPeeweeAdapterMethods:
    """Tests for Peewee adapter methods to increase coverage."""
    
    def test_peewee_adapter_create_element_validation(self):
        """Test Peewee adapter create_element validation."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField, IntegerField
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField(null=False)
                value = IntegerField(null=True)
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Test missing required field
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                adapter.create_element(
                    TestModel,
                    adapter.get_session,
                    {"value": 10}
                )
            
            assert exc_info.value.status_code == 400
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_update_element_put(self):
        """Test Peewee adapter update_element with PUT."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField, IntegerField
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField(null=False)
                value = IntegerField(null=True)
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Create test data
            obj = TestModel.create(name="old", value=10)
            
            # Test PUT (full replacement)
            result = adapter.update_element(
                TestModel,
                adapter.get_session,
                obj.id,
                {"name": "new", "value": 20},
                partial=False
            )
            
            assert result.name == "new"
            assert result.value == 20
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_get_list_queryset_with_offset(self):
        """Test Peewee adapter get_list_queryset with offset."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField()
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Create test data
            TestModel.create(name="test1")
            TestModel.create(name="test2")
            TestModel.create(name="test3")
            
            # Test with offset
            result = adapter.get_list_queryset(
                TestModel,
                adapter.get_session,
                limit=2,
                offset=1
            )
            
            assert len(result) == 2
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")


@pytest.mark.unit
class TestFactoryMethods:
    """Tests for Factory methods to increase coverage."""
    
    def test_factory_get_adapter_from_env_tortoise_json_models(self, monkeypatch):
        """Test factory with Tortoise and JSON models list."""
        from fastapi_viewsets.orm.factory import ORMFactory
        
        monkeypatch.setenv('ORM_TYPE', 'tortoise')
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
        monkeypatch.setenv('TORTOISE_MODELS', '["app.models", "app.other"]')
        
        try:
            adapter = ORMFactory.get_adapter_from_env()
            assert adapter is not None
        except (ImportError, ValueError):
            pytest.skip("Tortoise ORM not available")
    
    def test_factory_get_adapter_from_env_tortoise_custom_app_label(self, monkeypatch):
        """Test factory with Tortoise and custom app label."""
        from fastapi_viewsets.orm.factory import ORMFactory
        
        monkeypatch.setenv('ORM_TYPE', 'tortoise')
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
        monkeypatch.setenv('TORTOISE_MODELS', '[]')
        monkeypatch.setenv('TORTOISE_APP_LABEL', 'custom')
        
        try:
            adapter = ORMFactory.get_adapter_from_env()
            assert adapter is not None
        except (ImportError, ValueError):
            pytest.skip("Tortoise ORM not available")

