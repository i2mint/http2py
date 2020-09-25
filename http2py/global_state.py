from requests import request, Session

_global_state = {}


def get_global_state(key, default_value=None):
    value = _global_state.get(key, default_value)
    if value == default_value and default_value:
        _global_state[key] = value
    return value
