from http2py.decorators import (
    handle_raw_resp,
    handle_json_resp,
    handle_binary_resp,
)


def _default_output_trans(output):
    return output


default_text_output_trans = handle_raw_resp(_default_output_trans)
default_json_output_trans = handle_json_resp(_default_output_trans)
default_binary_output_trans = handle_binary_resp(_default_output_trans)
