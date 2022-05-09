import os

SEPARATOR = os.path.sep
BASE_DIR = os.getcwd()
BASE_DIR += SEPARATOR

MAP_METHODS = {'GET': {'method': 'get_element', 'http_method': 'GET', 'path': '/{id}', 'is_list': False},
               'POST': {'method': 'create_element', 'http_method': 'POST', 'path': '', 'is_list': False},
               'PUT': {'method': 'update_element', 'http_method': 'PUT', 'path': '', 'is_list': False},
               'PATCH': {'method': 'update_element', 'http_method': 'PATCH', 'path': '', 'is_list': False},
               'DELETE': {'method': 'delete_element', 'http_method': 'DELETE', 'path': '', 'is_list': False},
               'LIST': {'method': 'list', 'http_method': 'GET', 'path': '', 'is_list': True},
               }

ALLOWED_METHODS = [key for key in MAP_METHODS.keys()]
