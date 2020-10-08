from http2py.decorators import handle_text_resp, handle_json_resp, handle_content_resp


@handle_text_resp
def default_text_output_trans(output):
    return output


@handle_json_resp
def default_json_output_trans(output):
    return output


@handle_content_resp
def default_content_output_trans(output):
    return output
