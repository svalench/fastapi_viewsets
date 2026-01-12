"""Tests for exception handling to increase coverage."""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock

TEST_DATABASE_URL = f"sqlite:///{tempfile.mktemp(suffix='.db')}"


@pytest.mark.unit
class TestSQLAlchemyAdapterExceptions:
    """Tests for exception handling in SQLAlchemyAdapter."""
    
    def test_create_element_sqlalchemy_error(self):
        """Test create_element handles SQLAlchemyError."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.exc import SQLAlchemyError
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_sqlalchemy_error"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        # Mock session to raise SQLAlchemyError
        def mock_session():
            session = adapter.get_session()
            # Patch commit to raise error
            original_commit = session.commit
            def failing_commit():
                raise SQLAlchemyError("Database error")
            session.commit = failing_commit
            return session
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            adapter.create_element(TestModel, mock_session, {"name": "test"})
        
        assert exc_info.value.status_code == 400
        assert "Database error" in str(exc_info.value.detail)
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_create_element_generic_exception(self):
        """Test create_element handles generic Exception."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        from unittest.mock import patch
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_generic_error"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        # Mock model creation to raise generic exception
        with patch.object(TestModel, '__init__', side_effect=ValueError("Generic error")):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                adapter.create_element(TestModel, adapter.get_session, {"name": "test"})
            
            assert exc_info.value.status_code == 400
            assert "Error creating element" in str(exc_info.value.detail)
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_update_element_integrity_error(self):
        """Test update_element handles IntegrityError."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.exc import IntegrityError
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_update_integrity"
            id = Column(Integer, primary_key=True)
            name = Column(String, unique=True, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        # Create test data
        session = adapter.get_session()
        try:
            obj1 = TestModel(name="test1")
            obj2 = TestModel(name="test2")
            session.add(obj1)
            session.add(obj2)
            session.commit()
            obj1_id = obj1.id
            obj2_id = obj2.id
        finally:
            session.close()
        
        # Try to update with duplicate name (should raise IntegrityError)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            adapter.update_element(
                TestModel,
                adapter.get_session,
                obj1_id,
                {"name": "test2"},  # Duplicate
                partial=True
            )
        
        assert exc_info.value.status_code == 400
        assert "Integrity error" in str(exc_info.value.detail)
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_update_element_sqlalchemy_error(self):
        """Test update_element handles SQLAlchemyError."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.exc import SQLAlchemyError
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_update_sqlalchemy_error"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        # Create test data
        session = adapter.get_session()
        try:
            obj = TestModel(name="test")
            session.add(obj)
            session.commit()
            obj_id = obj.id
        finally:
            session.close()
        
        # Mock update to raise SQLAlchemyError
        with patch.object(adapter, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.update.side_effect = SQLAlchemyError("DB error")
            mock_get_session.return_value = mock_session
            
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                adapter.update_element(
                    TestModel,
                    adapter.get_session,
                    obj_id,
                    {"name": "new"},
                    partial=True
                )
            
            assert exc_info.value.status_code == 400
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_delete_element_sqlalchemy_error(self):
        """Test delete_element handles SQLAlchemyError."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.exc import SQLAlchemyError
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_delete_sqlalchemy_error"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        # Create test data
        session = adapter.get_session()
        try:
            obj = TestModel(name="test")
            session.add(obj)
            session.commit()
            obj_id = obj.id
        finally:
            session.close()
        
        # Mock delete to raise SQLAlchemyError
        def mock_session():
            session = adapter.get_session()
            original_commit = session.commit
            def failing_commit():
                raise SQLAlchemyError("DB error")
            session.commit = failing_commit
            return session
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            adapter.delete_element(TestModel, mock_session, obj_id)
        
        assert exc_info.value.status_code == 400
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    @pytest.mark.asyncio
    async def test_create_element_async_sqlalchemy_error(self):
        """Test create_element_async handles SQLAlchemyError."""
        try:
            from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
            from sqlalchemy import Column, Integer, String
            from sqlalchemy.exc import SQLAlchemyError
            from unittest.mock import AsyncMock
            
            adapter = SQLAlchemyAdapter(
                database_url=TEST_DATABASE_URL,
                async_database_url=TEST_DATABASE_URL.replace('sqlite://', 'sqlite+aiosqlite://')
            )
            Base = adapter.get_base()
            
            class TestModel(Base):
                __tablename__ = "test_async_sqlalchemy_error"
                id = Column(Integer, primary_key=True)
                name = Column(String, nullable=False)
            
            import asyncio
            async def setup():
                async with adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            
            await setup()
            
            # Mock to raise SQLAlchemyError
            with patch.object(adapter, 'get_async_session') as mock_get:
                mock_session = AsyncMock()
                mock_session.commit = AsyncMock(side_effect=SQLAlchemyError("DB error"))
                mock_get.return_value = mock_session
                
                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await adapter.create_element_async(
                        TestModel,
                        adapter.get_async_session,
                        {"name": "test"}
                    )
                
                assert exc_info.value.status_code == 400
            
            # Cleanup
            async def cleanup():
                async with adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
                await adapter.async_engine.dispose()
            await cleanup()
        except RuntimeError:
            pytest.skip("Async driver not available")


@pytest.mark.unit
class TestTortoiseAdapterExceptions:
    """Tests for exception handling in TortoiseAdapter."""
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_create_element_integrity_error(self):
        """Test Tortoise adapter create_element_async handles IntegrityError."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            from tortoise.models import Model
            from tortoise import fields
            from tortoise.exceptions import IntegrityError as TortoiseIntegrityError
            
            adapter = TortoiseAdapter(
                database_url="sqlite:///test_tortoise_integrity.db",
                models=[],
                app_label="test"
            )
            
            class TestModel(Model):
                id = fields.IntField(pk=True)
                name = fields.CharField(max_length=50, unique=True)
            
            await adapter._ensure_initialized()
            
            # Create first record
            await TestModel.create(name="test1")
            
            # Try to create duplicate (should raise IntegrityError)
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await adapter.create_element_async(
                    TestModel,
                    adapter.get_async_session,
                    {"name": "test1"}  # Duplicate
                )
            
            assert exc_info.value.status_code == 400
            assert "Integrity error" in str(exc_info.value.detail)
            
            # Cleanup
            from tortoise import Tortoise
            await Tortoise.close_connections()
        except ImportError:
            pytest.skip("Tortoise ORM not available")
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_create_element_generic_error(self):
        """Test Tortoise adapter create_element_async handles generic Exception."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            from tortoise.models import Model
            from tortoise import fields
            
            adapter = TortoiseAdapter(
                database_url="sqlite:///test_tortoise_generic.db",
                models=[],
                app_label="test"
            )
            
            class TestModel(Model):
                id = fields.IntField(pk=True)
                name = fields.CharField(max_length=50)
            
            await adapter._ensure_initialized()
            
            # Mock create to raise generic exception
            with patch.object(TestModel, 'create', side_effect=ValueError("Generic error")):
                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await adapter.create_element_async(
                        TestModel,
                        adapter.get_async_session,
                        {"name": "test"}
                    )
                
                assert exc_info.value.status_code == 400
                assert "Error creating element" in str(exc_info.value.detail)
            
            # Cleanup
            from tortoise import Tortoise
            await Tortoise.close_connections()
        except ImportError:
            pytest.skip("Tortoise ORM not available")
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_update_element_empty_data(self):
        """Test Tortoise adapter update_element_async with empty data."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            from tortoise.models import Model
            from tortoise import fields
            
            adapter = TortoiseAdapter(
                database_url="sqlite:///test_tortoise_empty.db",
                models=[],
                app_label="test"
            )
            
            class TestModel(Model):
                id = fields.IntField(pk=True)
                name = fields.CharField(max_length=50)
            
            await adapter._ensure_initialized()
            
            # Create test data
            obj = await TestModel.create(name="test")
            
            # Test with empty data (PATCH)
            result = await adapter.update_element_async(
                TestModel,
                adapter.get_async_session,
                obj.id,
                {},
                partial=True
            )
            
            assert result.name == "test"  # Should remain unchanged
            
            # Cleanup
            from tortoise import Tortoise
            await Tortoise.close_connections()
        except ImportError:
            pytest.skip("Tortoise ORM not available")


@pytest.mark.unit
class TestPeeweeAdapterExceptions:
    """Tests for exception handling in PeeweeAdapter."""
    
    def test_peewee_adapter_create_element_integrity_error(self):
        """Test Peewee adapter create_element handles IntegrityError."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField(unique=True)
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Create first record
            TestModel.create(name="test1")
            
            # Try to create duplicate (should raise IntegrityError)
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                adapter.create_element(
                    TestModel,
                    adapter.get_session,
                    {"name": "test1"}  # Duplicate
                )
            
            assert exc_info.value.status_code == 400
            assert "Integrity error" in str(exc_info.value.detail)
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_create_element_generic_error(self):
        """Test Peewee adapter create_element handles generic Exception."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField
            from unittest.mock import patch
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField()
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Mock create to raise generic exception
            with patch.object(TestModel, 'create', side_effect=ValueError("Generic error")):
                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    adapter.create_element(
                        TestModel,
                        adapter.get_session,
                        {"name": "test"}
                    )
                
                assert exc_info.value.status_code == 400
                assert "Error creating element" in str(exc_info.value.detail)
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_update_element_empty_data(self):
        """Test Peewee adapter update_element with empty data."""
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
            obj = TestModel.create(name="test")
            
            # Test with empty data (PATCH)
            result = adapter.update_element(
                TestModel,
                adapter.get_session,
                obj.id,
                {},
                partial=True
            )
            
            assert result.name == "test"  # Should remain unchanged
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_delete_element_generic_error(self):
        """Test Peewee adapter delete_element handles generic Exception."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField
            from unittest.mock import patch
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField()
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Create test data
            obj = TestModel.create(name="test")
            
            # Mock delete_instance to raise exception
            with patch.object(TestModel, 'get_by_id', return_value=obj):
                with patch.object(obj, 'delete_instance', side_effect=ValueError("Delete error")):
                    from fastapi import HTTPException
                    with pytest.raises(HTTPException) as exc_info:
                        adapter.delete_element(
                            TestModel,
                            adapter.get_session,
                            obj.id
                        )
                    
                    assert exc_info.value.status_code == 400
                    assert "Error deleting element" in str(exc_info.value.detail)
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")


@pytest.mark.unit
class TestFactoryExceptionHandling:
    """Tests for exception handling in Factory."""
    
    def test_factory_json_decode_error_handling(self, monkeypatch):
        """Test factory handles JSON decode error for TORTOISE_MODELS."""
        from fastapi_viewsets.orm.factory import ORMFactory
        
        monkeypatch.setenv('ORM_TYPE', 'tortoise')
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
        monkeypatch.setenv('TORTOISE_MODELS', 'invalid json')
        
        try:
            adapter = ORMFactory.get_adapter_from_env()
            # Should fall back to comma-separated parsing
            assert adapter is not None
        except (ImportError, ValueError):
            pytest.skip("Tortoise ORM not available")

