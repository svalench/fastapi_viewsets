
from collections import Iterable
from typing import List, Optional, Any

from fastapi import  Body, Depends
from fastapi.security import OAuth2PasswordBearer

from fastapi_viewsets.base import Base
from fastapi_viewsets.constants import ALLOWED_METHODS, MAP_METHODS
from fastapi_viewsets.utils import get_list_queryset, get_element_by_id, create_element, update_element, delete_element


def butle():
    return None

class BaseViewset(Base):


    def register(self, methods: List = None, oauth_protect: OAuth2PasswordBearer = None,
                 protected_methods: List = None):
        if not protected_methods:
            protected_methods = []
        if not methods:
            methods = self.ALLOWED_METHODS
        if not isinstance(methods, Iterable):
            raise ValueError('methods must be List of methods (e.g. ["GET"])')
        self.__registeration_methods(methods=methods, protected_methods=protected_methods, oauth_protect=oauth_protect)

    def list(self, limit: Optional[int] = 10,
             offset: Optional[int] = 0,
             search: Optional[str] = None,
             token: str = Depends(butle)
             ):
        return get_list_queryset(self.model, db_session=self.db_session, limit=limit, offset=offset)

    def get_element(self, id: Any, token: str = Depends(butle)):
        return get_element_by_id(self.model, db_session=self.db_session, id=id, )

    def create_element(self, item=Body(...), token: str = Depends(butle)):
        return create_element(self.model, db_session=self.db_session, data=dict(item))

    def update_element(self, id: str, item=Body(...), token: str = Depends(butle)):
        return update_element(self.model, self.db_session, id, dict(item))

    def delete_element(self, id: str, token: str = Depends(butle)):
        return {'status': True, 'text': "успешно удалено"} if delete_element(self.model, self.db_session,
                                                                             id) is True else {'status': False,
                                                                                               'text': "не удалено"}
