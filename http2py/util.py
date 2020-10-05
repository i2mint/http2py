import json


def add_defaults(d, dflts):
    """Adds defaults to every (mapping) value of every item of d"""
    dflt_keys = set(dflts)
    for k, v in d.items():
        d[k].update({dflt_key: dflts[dflt_key] for dflt_key in dflt_keys.difference(v)})
    return d


class ModuleNotFoundErrorNiceMessage:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is ModuleNotFoundError:
            raise ModuleNotFoundError(f"""
It seems you don't have requred `{exc_val.name}` package.
Try installing it by running:

    pip install {exc_val.name}

in your terminal.
For more information: https://pypi.org/project/{exc_val.name}
            """)


class I2mintModuleNotFoundErrorNiceMessage:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is ModuleNotFoundError:
            raise ModuleNotFoundError(f"""
It seems you don't have requred `{exc_val.name}` package. Not sure if this is the problem, but you could try:
    git clone https://github.com/i2mint/{exc_val.name}
in a place that your python path (i.e. PYTHONPATH environment variable).  
            """)


def is_jsonable(x):
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False
