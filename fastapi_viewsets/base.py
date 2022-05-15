import functools
from typing import Callable, Type, List

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from fastapi_viewsets.constants import ALLOWED_METHODS, MAP_METHODS


class Base(APIRouter):
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

    def __registeration_methods(self, methods, protected_methods, oauth_protect: OAuth2PasswordBearer = None, ):
        for method in methods:
            data_method = MAP_METHODS.get(method)
            self_method = getattr(self, data_method.get('method'))
            self.__set_annotation(self_method)
            old_docstring = self_method.__doc__
            if method in protected_methods and oauth_protect:
                self_method = functools.partial(self_method, token=Depends(oauth_protect))
                self_method.__doc__ = old_docstring
            self.add_api_route(
                self.endpoint + data_method.get('path', ''),
                self_method,
                response_model=List[self.response_model] if data_method.get('is_list', False) else self.response_model,
                tags=self.tags,
                methods=[data_method.get('http_method')],
            )

    def __set_annotation(self, method):
        try:
            if method.__annotations__.get('item', False): method.__annotations__['item'] = self.response_model
        except:
            pass
