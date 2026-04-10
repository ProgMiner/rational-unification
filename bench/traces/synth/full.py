#!/usr/bin/env python3
'''
Generate a trace file with a chain of equations for binary trees of depth n.
For each level i, we introduce variables T_i and U_i (except T_0 = x, U_0 = a).
Equations:
    T_i = f(T_{i-1}, T_{i-1}) for i=1..n,
    U_i = f(U_{i-1}, U_{i-1}) for i=1..n,
    and finally T_n = U_n.
All terms are represented using variables and constants.
'''

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.path.normpath(__file__)).parent.parent.parent))

from trace import TraceWriter


def generate_trace(output_file: str, n: int) -> None:
    '''
    Generate a trace file containing equations for the unification problem
    T_n = U_n where T_0 = x, U_0 = a, and T_{i+1} = f(T_i, T_i), U_{i+1} = f(U_i, U_i).
    Each T_i and U_i is a separate variable.
    '''

    with TraceWriter(output_file) as w:
        if n == 0:
            w.var(0)
            w.int(0)
            return

        for i in range(1, n + 1):
            w.var(2 * i - 1)

            w.cons(0, 2)
            if i == 1:
                w.var(0)
                w.var(0)

            else:
                prev_t = 2 * (i - 1) - 1
                w.var(prev_t)
                w.var(prev_t)

            w.var(2 * i)
            w.cons(0, 2)

            if i == 1:
                w.int(0)
                w.int(0)

            else:
                prev_u = 2 * (i - 1)
                w.var(prev_u)
                w.var(prev_u)

        # Final equation: T_n = U_n
        w.var(2 * n - 1)
        w.var(2 * n)


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
