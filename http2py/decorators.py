from i2.errors import AuthorizationError, ForbiddenError, InputError, NotFoundError, DuplicateRecordError


def handle_error(resp):
    if resp.status_code == 400:
        if resp.reason == 'AuthorizationError':
            raise AuthorizationError(resp.text)
        if resp.reason == 'InputError':
            raise InputError(resp.text)
        if resp.reason == 'DuplicateRecordError':
            raise DuplicateRecordError(resp.text)
    if resp.status_code == 403:
        raise ForbiddenError(resp.text)
    if resp.status_code == 404:
        raise NotFoundError(resp.text)
    raise RuntimeError(resp.text)


def handle_text_resp(func):
    def output_trans(resp):
        if resp.status_code == 200:
            return resp.text
        else:
            handle_error(resp)

    output_trans.content_type = 'text'
    return output_trans


def handle_json_resp(func):
    def output_trans(resp):
        if resp.status_code == 200:
            return resp.json()
        else:
            handle_error(resp)

    output_trans.content_type = 'json'
    return output_trans


def handle_content_resp(func):
    def output_trans(resp):
        if resp.status_code == 200:
            return resp.content
        else:
            handle_error(resp)

    output_trans.content_type = 'content'
    return output_trans
