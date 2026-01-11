import os

SEPARATOR = os.path.sep
BASE_DIR = os.getcwd()
BASE_DIR += SEPARATOR

MAP_METHODS = {'GET': {'method': 'get_element', 'http_method': 'GET', 'path': '/{id}', 'is_list': False},
               'POST': {'method': 'create_element', 'http_method': 'POST', 'path': '', 'is_list': False},
               'PUT': {'method': 'update_element', 'http_method': 'PUT', 'path': '/{id}', 'is_list': False},
               'PATCH': {'method': 'update_element', 'http_method': 'PATCH', 'path': '/{id}', 'is_list': False},
               'DELETE': {'method': 'delete_element', 'http_method': 'DELETE', 'path': '/{id}', 'is_list': False},
               'LIST': {'method': 'list', 'http_method': 'GET', 'path': '', 'is_list': True},
               }

# Order matters: LIST must come before GET for proper FastAPI routing
ALLOWED_METHODS = ['LIST', 'POST', 'GET', 'PUT', 'PATCH', 'DELETE']
