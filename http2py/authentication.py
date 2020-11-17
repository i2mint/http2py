import json
import os
from pathlib import Path
from typing import Iterable

DFLT_CONFIG_FILENAME = os.path.join(Path.home(), '.http2py', 'credentials.json')


def mk_auth(auth_kwargs: dict,
            expected_auth_kwargs: Iterable[str],
            config_filename=DFLT_CONFIG_FILENAME,
            profile: str = ''):
    output = {}
    stored_auth = {}
    for kwarg in expected_auth_kwargs:
        if not auth_kwargs.get(kwarg, ''):
            if not stored_auth:
                with open(config_filename) as fp:
                    stored_config = json.load(fp)
                    if profile and profile in stored_config:
                        stored_auth = stored_config[profile]
                    elif 'default' in stored_config:
                        stored_auth = stored_config['default']
                    else:
                        stored_auth = stored_config
            output[kwarg] = stored_auth.get(kwarg, '')
    return dict(auth_kwargs, **output)
