def handle_json_resp(func):
    def output_trans(resp):
        if resp.status_code == 200:
            return resp.json()
        else:
            return {
                'status_code': resp.status_code,
                'message': resp.text
            }

    output_trans.content_type = 'json'
    return output_trans
