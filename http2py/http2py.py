"""(Http) Requests for humans"""

from requests.sessions import Session


class Http2Py:
    def __init__(self, session=None):
        self.session = session or Session()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        return self.session.close()


import inspect

inspect.signature()
