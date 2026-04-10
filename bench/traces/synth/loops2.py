#!/usr/bin/env python3
'''
Generate a trace with n equations of the form xi = f(xi) (cyclic terms)
and then unify each xi with x0 (i.e., x0 = xi).
'''

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.path.normpath(__file__)).parent.parent.parent))

from trace import TraceWriter


def generate_trace(output_file: str, n: int) -> None:
    '''
    Generate a trace file containing:
        for i in 1..n:
            xi = f(xi)
            x0 = xi
    where x0 has index 0, xi has index i.
    '''

    with TraceWriter(output_file) as w:
        for i in range(1, n + 1):
            w.var(i)
            w.cons(0, 1)
            w.var(i)

            w.var(i)
            w.var(0)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <n>', file=sys.stderr)
        sys.exit(1)

    try:
        n = int(sys.argv[1])

        if n < 0:
            raise ValueError('n must be non-negative')

    except ValueError as e:
        print('Invalid n:', e, file=sys.stderr)
        sys.exit(1)

    generate_trace(sys.stdout.buffer, n)
