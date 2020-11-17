import argh
from typing import Iterable

from http2py.cli_maker import mk_argparse_friendly
from i2.io_trans import AnnotAndDfltIoTrans

def myfun(a: int, b: Iterable[int]):
    print(f'a: {a} {type(a)}')
    print(f'b: {b} {type(b)}')

if __name__ == '__main__':
    parser = argh.ArghParser()
    parser.add_commands([mk_argparse_friendly(AnnotAndDfltIoTrans()(myfun))])
    parser.dispatch()
