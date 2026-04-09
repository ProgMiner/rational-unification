#!/usr/bin/env python3


def read_exactly(f, n: int) -> bytes:
    data = bytearray()

    while len(data) < n:
        chunk = f.read(n - len(data))

        if not chunk:
            raise EOFError(f'Unexpected EOF: expected {n} bytes, got {len(data)}')

        data.extend(chunk)

    return bytes(data)


def read_int64(f) -> int:
    return int.from_bytes(read_exactly(f, 8), 'little')


def analyze_trace(filepath: str) -> dict:
    """
    Analyzes a binary trace file and returns statistics.

    Args:
        filepath (str): path to the trace file.

    Returns:
        dict: dictionary with keys:
            - 'trace_length' (int): number of term pairs.
            - 'functor_count' (int): total number of functors (all nodes except variables).
            - 'var_count' (int): total number of variables.
            - 'total_vertices' (int): total number of vertices (sum of functor_count and var_count).
    """

    var_cnt, fun_cnt, pair_cnt = 0, 0, 0

    with open(filepath, 'rb') as f:
        def read_term():
            nonlocal var_cnt, fun_cnt

            tag = f.read(1)
            if not tag:
                raise EOFError

            tag = tag[0]

            match tag:
                case 0:
                    var_cnt += 1
                    read_int64(f)

                case 1:
                    fun_cnt += 1
                    read_int64(f)

                case 2:
                    fun_cnt += 1
                    read_int64(f)

                case 3:
                    fun_cnt += 1
                    length = read_int64(f)
                    read_exactly(f, length)

                case 4:
                    fun_cnt += 1
                    read_int64(f)
                    arity = read_int64(f)
                    for _ in range(arity):
                        read_term()

                case _:
                    raise ValueError(f'Invalid term tag: {tag}')

        try:
            while True:
                read_term()
                read_term()
                pair_cnt += 1

        except EOFError:
            pass

    return {
        'trace_length': pair_cnt,
        'functor_count': fun_cnt,
        'var_count': var_cnt,
        'total_vertices': var_cnt + fun_cnt,
    }


if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <trace file>', file=sys.stderr)
        sys.exit(1)

    try:
        stats = analyze_trace(sys.argv[1])

    except Exception as e:
        print('Error:', e, file=sys.stderr)
        sys.exit(1)

    print('Trace length:', stats['trace_length'])
    print('Functor count:', stats['functor_count'])
    print('Variable count:', stats['var_count'])
    print('Total size:', stats['total_vertices'])
