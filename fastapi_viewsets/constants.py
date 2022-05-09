import os

SEPARATOR = os.path.sep
BASE_DIR = os.getcwd()
BASE_DIR += SEPARATOR

MAP_METHODS = {'GET': {'method': 'get_element', 'http_method': 'GET', 'path': '/{id}'},
               'POST': {'method': 'create_element', 'http_method': 'POST', 'path': ''},
               'PUT': {'method': 'update_element', 'http_method': 'PUT', 'path': ''},
               'PATCH': {'method': 'update_element', 'http_method': 'PATCH', 'path': ''},
               'DELETE': {'method': 'delete_element', 'http_method': 'DELETE', 'path': ''},
               'LIST': {'method': 'list', 'http_method': 'GET', 'path': ''},
               }

ALLOWED_METHODS = [key for key in MAP_METHODS.keys()]
