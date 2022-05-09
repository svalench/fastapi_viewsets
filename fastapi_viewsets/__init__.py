import os
from typing import List, Optional, Any, Callable, Type

from fastapi import APIRouter, Body
from pydantic import BaseModel

from fastapi_viewsets.utils import get_list_queryset, get_element_by_id, create_element, update_element, delete_element

SEPARATOR = os.path.sep
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
BASE_DIR += SEPARATOR

class Base(APIRouter):

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

    def register(self):
        path = self.endpoint
        self.add_api_route(
            path,
            self.list,
            response_model=List[self.response_model],
            tags=self.tags,
            methods=["GET"],
        )

        self.add_api_route(
            path + '/{id}',
            self.get_element,
            response_model=self.response_model,
            tags=self.tags,
            methods=["GET"],
        )

        self.add_api_route(
            path,
            self.create_element,
            response_model=self.response_model,
            tags=self.tags,
            methods=["POST"],
        )

        self.add_api_route(
            path,
            self.update_element,
            response_model=self.response_model,
            tags=self.tags,
            methods=["PUT"],
        )

        self.add_api_route(
            path,
            self.update_element,
            response_model=self.response_model,
            tags=self.tags,
            methods=["PATCH"],
        )

        self.add_api_route(
            path,
            self.delete_element,
            tags=self.tags,
            methods=["DELETE"],
        )

    def list(self, limit: Optional[int] = 10,
             offset: Optional[int] = 0,
             search: Optional[str] = None):
        return get_list_queryset(self.model, db_session=self.db_session, limit=limit, offset=offset)

    def get_element(self, id: Any):
        return get_element_by_id(self.model, db_session=self.db_session, id=id)

    def create_element(self, item=Body(...)):
        return create_element(self.model, db_session=self.db_session, data=item)

    def update_element(self, id: str, item = Body(...)):
        return update_element(self.model, self.db_session, id, item)

    def delete_element(self, id: str):
        return {'status': True, 'text': "успешно удалено"} if delete_element(self.model, self.db_session, id) == True else {'status': False,
                                                                                                        'text': "не удалено"}
