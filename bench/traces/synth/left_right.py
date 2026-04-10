#!/usr/bin/env python3
'''
Generate a trace file for left-deep vs right-deep trees unification.
T0 = x, U0 = x
For i = 1..n:
    Ti = f(T_{i-1}, x)
    Ui = f(x, U_{i-1})
Finally Tn = Un.
All intermediate terms are represented by separate variables.
'''

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.path.normpath(__file__)).parent.parent.parent))

from trace import TraceWriter


def generate_trace(output_file: str, n: int) -> None:
    '''
    Generate a trace file containing equations for the unification problem
    T_n = U_n where T0 = x, U0 = x,
    T_{i+1} = f(T_i, x), U_{i+1} = f(x, U_i).
    Each T_i and U_i is a separate variable.
    '''

    with TraceWriter(output_file) as w:
        # Base equations: T0 = x, U0 = x (where x is variable 0)
        # T0: variable index 1? Let's define T0 = var(1), U0 = var(2), x = var(0)
        # Actually we can set T0 = var(1), U0 = var(2), and x = var(0)
        # Write T0 = x
        w.var(1)   # T0
        w.var(0)   # x
        # Write U0 = x
        w.var(2)   # U0
        w.var(0)

        # Generate equations for T_i and U_i for i = 1..n
        for i in range(1, n + 1):
            # T_i = f(T_{i-1}, x)
            t_prev = 2*(i-1) + 1  # T_{i-1} index: 1,3,5,... for i=1 -> T0=1
            t_curr = 2*i + 1      # T_i index: 3,5,7,...
            w.var(t_curr)
            w.cons(0, 2)   # functor f
            w.var(t_prev)  # left argument
            w.var(0)       # right argument = x

            # U_i = f(x, U_{i-1})
            u_prev = 2*(i-1) + 2  # U_{i-1} index: 2,4,6,...
            u_curr = 2*i + 2      # U_i index: 4,6,8,...
            w.var(u_curr)
            w.cons(0, 2)   # functor f
            w.var(0)       # left argument = x
            w.var(u_prev)  # right argument

        # Final equation: T_n = U_n
        w.var(2*n + 1)
        w.var(2*n + 2)


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
