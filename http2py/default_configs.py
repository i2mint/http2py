from http2py.decorators import (
    handle_text_resp,
    handle_json_resp,
    handle_content_resp,
)


def _default_output_trans(output):
    return output


default_text_output_trans = handle_text_resp(_default_output_trans)
default_json_output_trans = handle_json_resp(_default_output_trans)
default_content_output_trans = handle_content_resp(_default_output_trans)
