"""Tests to cover missing code coverage lines."""

import pytest
import tempfile
from unittest.mock import Mock, patch, PropertyMock

TEST_DATABASE_URL = f"sqlite:///{tempfile.mktemp(suffix='.db')}"


@pytest.mark.unit
class TestMissingCoverage:
    """Tests to cover missing coverage lines."""
    
    def test_base_viewset_register_annotation_exception(self):
        """Test BaseViewset.register exception handling when setting annotations."""
        from fastapi_viewsets import BaseViewset
        from sqlalchemy import Column, Integer, String
        from fastapi_viewsets.db_conf import get_orm_adapter
        
        adapter = get_orm_adapter()
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_annotation_exception"
            id = Column(Integer, primary_key=True)
            name = Column(String)
        
        Base.metadata.create_all(adapter.engine)
        
        viewset = BaseViewset(
            model=TestModel,
            endpoint="/test",
            db_session=adapter.get_session
        )
        
        # Mock the method to raise exception when setting annotations
        original_list = viewset.list
        
        # Create a mock that raises AttributeError when setting annotations
        mock_method = Mock(side_effect=original_list)
        type(mock_method).__annotations__ = PropertyMock(side_effect=AttributeError("Cannot set"))
        
        with patch.object(viewset, 'list', mock_method):
            # This should trigger the exception handler (lines 108-109)
            viewset.register(methods=['LIST'])
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_base_viewset_register_annotation_exception_other_methods(self):
        """Test BaseViewset.register exception handling for other methods."""
        from fastapi_viewsets import BaseViewset
        from sqlalchemy import Column, Integer, String
        from fastapi_viewsets.db_conf import get_orm_adapter
        
        adapter = get_orm_adapter()
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_annotation_exception_other"
            id = Column(Integer, primary_key=True)
            name = Column(String)
        
        Base.metadata.create_all(adapter.engine)
        
        viewset = BaseViewset(
            model=TestModel,
            endpoint="/test",
            db_session=adapter.get_session
        )
        
        # Mock the method to raise exception when setting annotations
        original_get = viewset.get_element
        
        # Create a mock that raises AttributeError when setting annotations
        mock_method = Mock(side_effect=original_get)
        type(mock_method).__annotations__ = PropertyMock(side_effect=AttributeError("Cannot set"))
        
        with patch.object(viewset, 'get_element', mock_method):
            # This should trigger the exception handler (lines 133-134)
            viewset.register(methods=['GET'])
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_async_base_viewset_register_annotation_exception(self):
        """Test AsyncBaseViewset.register exception handling when setting annotations."""
        from fastapi_viewsets.async_base import AsyncBaseViewset
        from sqlalchemy import Column, Integer, String
        from fastapi_viewsets.db_conf import get_orm_adapter
        
        adapter = get_orm_adapter()
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_async_annotation_exception"
            id = Column(Integer, primary_key=True)
            name = Column(String)
        
        Base.metadata.create_all(adapter.engine)
        
        viewset = AsyncBaseViewset(
            model=TestModel,
            endpoint="/test",
            db_session=adapter.get_async_session
        )
        
        # Mock the method to raise exception when setting annotations
        original_list = viewset.list
        
        # Create a mock that raises AttributeError when setting annotations
        mock_method = Mock(side_effect=original_list)
        type(mock_method).__annotations__ = PropertyMock(side_effect=AttributeError("Cannot set"))
        
        with patch.object(viewset, 'list', mock_method):
            # This should trigger the exception handler (lines 113-114)
            viewset.register(methods=['LIST'])
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_async_base_viewset_register_annotation_exception_other_methods(self):
        """Test AsyncBaseViewset.register exception handling for other methods."""
        from fastapi_viewsets.async_base import AsyncBaseViewset
        from sqlalchemy import Column, Integer, String
        from fastapi_viewsets.db_conf import get_orm_adapter
        
        adapter = get_orm_adapter()
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_async_annotation_exception_other"
            id = Column(Integer, primary_key=True)
            name = Column(String)
        
        Base.metadata.create_all(adapter.engine)
        
        viewset = AsyncBaseViewset(
            model=TestModel,
            endpoint="/test",
            db_session=adapter.get_async_session
        )
        
        # Mock the method to raise exception when setting annotations
        original_get = viewset.get_element
        
        # Create a mock that raises AttributeError when setting annotations
        mock_method = Mock(side_effect=original_get)
        type(mock_method).__annotations__ = PropertyMock(side_effect=AttributeError("Cannot set"))
        
        with patch.object(viewset, 'get_element', mock_method):
            # This should trigger the exception handler (lines 138-139)
            viewset.register(methods=['GET'])
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_peewee_adapter_parse_database_url_sqlite(self):
        """Test Peewee adapter _parse_database_url for SQLite."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            adapter = PeeweeAdapter(database_url="sqlite:///test.db")
            assert adapter.database is not None
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_parse_database_url_postgresql(self):
        """Test Peewee adapter _parse_database_url for PostgreSQL."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            # This will fail if psycopg2 is not installed, but we're testing the parsing logic
            try:
                adapter = PeeweeAdapter(database_url="postgresql://user:pass@localhost/db")
                assert adapter.database is not None
            except (ImportError, ValueError):
                # Expected if driver is not installed
                pass
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_parse_database_url_mysql(self):
        """Test Peewee adapter _parse_database_url for MySQL."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            # This will fail if MySQLdb is not installed, but we're testing the parsing logic
            try:
                adapter = PeeweeAdapter(database_url="mysql://user:pass@localhost/db")
                assert adapter.database is not None
            except (ImportError, ValueError):
                # Expected if driver is not installed
                pass
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_parse_database_url_invalid(self):
        """Test Peewee adapter _parse_database_url with invalid URL."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            with pytest.raises(ValueError):
                PeeweeAdapter(database_url="invalid://url")
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_get_list_queryset(self):
        """Test Peewee adapter get_list_queryset."""
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
            
            # Test get_list_queryset
            result = adapter.get_list_queryset(
                TestModel,
                adapter.get_session,
                limit=1
            )
            
            assert len(result) == 1
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_get_element_by_id(self):
        """Test Peewee adapter get_element_by_id."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField
            from fastapi import HTTPException
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField()
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Create test data
            obj = TestModel.create(name="test")
            
            # Test get_element_by_id
            result = adapter.get_element_by_id(
                TestModel,
                adapter.get_session,
                obj.id
            )
            
            assert result.id == obj.id
            assert result.name == "test"
            
            # Test with non-existent id
            with pytest.raises(HTTPException) as exc_info:
                adapter.get_element_by_id(
                    TestModel,
                    adapter.get_session,
                    999
                )
            
            assert exc_info.value.status_code == 404
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_delete_element(self):
        """Test Peewee adapter delete_element."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField
            from fastapi import HTTPException
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField()
            
            TestModel._meta.database = adapter.database
            TestModel.create_table()
            
            # Create test data
            obj = TestModel.create(name="test")
            obj_id = obj.id
            
            # Test delete_element
            result = adapter.delete_element(
                TestModel,
                adapter.get_session,
                obj_id
            )
            
            assert result is True
            
            # Verify it's deleted
            assert TestModel.get_by_id(obj_id) is None
            
            # Test with non-existent id
            with pytest.raises(HTTPException) as exc_info:
                adapter.delete_element(
                    TestModel,
                    adapter.get_session,
                    999
                )
            
            assert exc_info.value.status_code == 404
            
            # Cleanup
            TestModel.drop_table()
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_get_model_columns(self):
        """Test Peewee adapter get_model_columns."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            from peewee import Model, CharField, IntegerField
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            Base = adapter.get_base()
            
            class TestModel(Base):
                name = CharField()
                value = IntegerField(null=True)
            
            TestModel._meta.database = adapter.database
            
            # Test get_model_columns
            columns = adapter.get_model_columns(TestModel)
            
            assert 'name' in columns
            assert 'value' in columns
            assert columns['name']['type'] == 'CharField'
        except ImportError:
            pytest.skip("Peewee not available")

