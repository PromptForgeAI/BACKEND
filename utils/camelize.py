# utils/camelize.py


import re

def _to_camel_case(s):
        s = str(s)
        if not s or '_' not in s:
                return s
        parts = s.split('_')
        return parts[0] + ''.join(word.capitalize() for word in parts[1:])

def camelize(obj):
        if isinstance(obj, list):
                return [camelize(item) for item in obj]
        elif isinstance(obj, dict):
                new_dict = {}
                for k, v in obj.items():
                        new_key = _to_camel_case(k)
                        new_dict[new_key] = camelize(v)
                return new_dict
        else:
                return obj
