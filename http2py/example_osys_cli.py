from http2py import dispatch_cli

OTOSENSE_ANNOTATION_SERVICE_URL = 'https://api.otosense.analogcloudsandbox.io/v3/annotations/openapi'

from osys.handlers import source_handler_list, mk_source_configs
from py2http import mk_http_service
source_service = mk_http_service(
    source_handler_list[0:1], **mk_source_configs()
)

if __name__ == '__main__':
    dispatch_cli(source_service.openapi_spec)
