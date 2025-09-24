import re

def snake_to_camel(s):
    parts = s.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])

def camelize(data):
    if isinstance(data, list):
        return [camelize(item) for item in data]
    elif isinstance(data, dict):
        return {snake_to_camel(k): camelize(v) for k, v in data.items()}
    else:
        return data
