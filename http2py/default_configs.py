from http2py.decorators import handle_json_resp


@handle_json_resp
def default_output_trans(output):
    return output