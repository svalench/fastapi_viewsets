import os
from collections import Iterable
from typing import List, Optional, Any, Callable, Type

from fastapi import APIRouter, Body
from pydantic import BaseModel

from fastapi_viewsets.constants import ALLOWED_METHODS, MAP_METHODS
from fastapi_viewsets.utils import get_list_queryset, get_element_by_id, create_element, update_element, delete_element


class BaseViewset(APIRouter):
    """Base class for Viewset endpoint"""

    ALLOWED_METHODS = ALLOWED_METHODS

    def __init__(self, *args,
                 allowed_methods: list = None,
                 endpoint: str = None,
                 model=None,
                 db_session: Callable = None,
                 response_model: Type[BaseModel] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_methods = allowed_methods
        self.endpoint = endpoint
        self.response_model = response_model
        self.model = model
        self.db_session = db_session

    def register(self, methods: List = None):
        if not methods:
            methods = self.ALLOWED_METHODS
        if not isinstance(methods, Iterable):
            raise ValueError('methods must be List of methods (e.g. ["GET"])')
        for method in methods:
            data_method = MAP_METHODS.get(method)
            self_method = getattr(self, data_method.get('method'))
            try:
                self_method.__annotations__['item'] = self.response_model
            except:
                pass
            self.add_api_route(
                self.endpoint + data_method.get('path', ''),
                self_method,
                response_model=List[self.response_model],
                tags=self.tags,
                methods=[data_method.get('http_method')],
            )

    def list(self, limit: Optional[int] = 10,
             offset: Optional[int] = 0,
             search: Optional[str] = None):
        return get_list_queryset(self.model, db_session=self.db_session, limit=limit, offset=offset)

    def get_element(self, id: Any):
        return get_element_by_id(self.model, db_session=self.db_session, id=id)

    def create_element(self, item=Body(...)):
        return create_element(self.model, db_session=self.db_session, data=item)

    def update_element(self, id: str, item=Body(...)):
        return update_element(self.model, self.db_session, id, item)

    def delete_element(self, id: str):
        return {'status': True, 'text': "успешно удалено"} if delete_element(self.model, self.db_session,
                                                                             id) is True else {'status': False,
                                                                                               'text': "не удалено"}
