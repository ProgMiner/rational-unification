#!/usr/bin/env python3

import struct
from abc import ABC, abstractmethod
from typing import Generic, List, TypeVar


T = TypeVar('T')
A = TypeVar('A')


class TermVisitor(ABC, Generic[T, A]):

    @abstractmethod
    def var(self, index: int) -> T:
        '''Visit a variable term.'''
        pass

    @abstractmethod
    def int(self, value: int) -> T:
        '''Visit an integer term.'''
        pass

    @abstractmethod
    def float(self, value: float) -> T:
        '''Visit a float term.'''
        pass

    @abstractmethod
    def string(self, value: str) -> T:
        '''Visit a string term.'''
        pass

    @abstractmethod
    def cons(self, functor_id: int, args: List[T]) -> T:
        '''Visit a compound term (constructor).'''
        pass

    @abstractmethod
    def empty_trace(self) -> A:
        '''Return the initial value for a trace.'''
        pass

    @abstractmethod
    def cons_trace(self, acc: A, left: T, right: T) -> A:
        '''Add one equation (left = right) to the trace.'''
        pass


def read_exactly(f, n: int) -> bytes:
    '''Read exactly n bytes from the file, raise EOFError if not enough.'''

    data = bytearray()
    while len(data) < n:
        chunk = f.read(n - len(data))

        if not chunk:
            raise EOFError(f'Unexpected EOF: expected {n} bytes, got {len(data)}')

        data.extend(chunk)

    return bytes(data)


def read_int64(f) -> int:
    '''Read a 64-bit little-endian integer.'''
    return int.from_bytes(read_exactly(f, 8), 'little')


def parse_trace(filepath: str, visitor: TermVisitor[T, A]) -> A:
    '''
    Parse a binary trace file and feed all term pairs to the visitor.

    Args:
        filepath: Path to the trace file.
        visitor: An instance of a concrete TermVisitor.

    Returns:
        The final accumulator returned by the visitor's cons_trace method.
    '''

    acc = visitor.empty_trace()
    with open(filepath, 'rb') as f:
        def read_term():
            nonlocal f

            tag = f.read(1)
            if not tag:
                raise EOFError

            tag = tag[0]
            match tag:
                case 0:
                    idx = read_int64(f)
                    return visitor.var(idx)

                case 1:
                    value = read_int64(f)
                    return visitor.int(value)

                case 2:
                    bits = read_int64(f)
                    value = struct.unpack('<d', bits.to_bytes(8, 'little'))[0]
                    return visitor.float(value)

                case 3:
                    length = read_int64(f)
                    content = read_exactly(f, length).decode('utf-8')
                    return visitor.string(content)

                case 4:
                    functor_id = read_int64(f)
                    arity = read_int64(f)
                    args = [read_term() for _ in range(arity)]
                    return visitor.cons(functor_id, args)

                case _:
                    raise ValueError(f'Invalid term tag: {tag}')

        while True:
            try:
                t1 = read_term()
            except EOFError:
                break

            try:
                t2 = read_term()
            except EOFError:
                raise ValueError('Incomplete trace: odd number of terms')

            acc = visitor.cons_trace(acc, t1, t2)

    return acc


class StatsVisitor(TermVisitor[None, None]):
    '''Visitor that counts variables, functors and pairs.'''

    def __init__(self):
        self.var_count = 0
        self.functor_count = 0
        self.pair_count = 0

    def var(self, index: int) -> None:
        self.var_count += 1

    def int(self, value: int) -> None:
        self.functor_count += 1

    def float(self, value: float) -> None:
        self.functor_count += 1

    def string(self, value: str) -> None:
        self.functor_count += 1

    def cons(self, functor_id: int, args: List[None]) -> None:
        self.functor_count += 1

    def empty_trace(self) -> None:
        self.pair_count = 0

    def cons_trace(self, acc: None, left: None, right: None) -> None:
        self.pair_count += 1

    def get_stats(self) -> dict:
        return {
            'trace_length': self.pair_count,
            'functor_count': self.functor_count,
            'var_count': self.var_count,
            'total_vertices': self.var_count + self.functor_count,
        }


class PrintingVisitor(TermVisitor[str, None]):
    '''Visitor that prints terms in a human-readable format.'''

    def var(self, index: int) -> str:
        return f'_{index}'

    def int(self, value: int) -> str:
        return f'int<{value}>'

    def float(self, value: float) -> str:
        return f'double<{value:e}>'

    def string(self, value: str) -> str:
        return f'string<{value}>'

    def cons(self, functor_id: int, args: List[str]) -> str:
        args_str = ', '.join(args)
        return f'boxed {functor_id} <{args_str}>'

    def empty_trace(self) -> None:
        return None

    def cons_trace(self, acc: None, left: str, right: str) -> None:
        print(left, '=', right)
        return None


def analyze_trace(filepath: str) -> dict:
    '''
    Analyzes a binary trace file and returns statistics.

    Args:
        filepath (str): path to the trace file.

    Returns:
        dict: dictionary with keys:
            - 'trace_length' (int): number of term pairs.
            - 'functor_count' (int): total number of functors (all nodes except variables).
            - 'var_count' (int): total number of variables.
            - 'total_vertices' (int): total number of vertices.
    '''

    visitor = StatsVisitor()
    parse_trace(filepath, visitor)
    return visitor.get_stats()


def print_trace(filepath: str) -> None:
    '''Print the trace in a human-readable format.'''
    visitor = PrintingVisitor()
    parse_trace(filepath, visitor)


class TraceWriter:
    '''
    Writer for binary trace files. Use as a context manager or manually.

    Example:
        with TraceWriter('output.bin') as w:
            w.var(0)
            w.int(42)
            w.pair(lambda w: w.var(0), lambda w: w.int(42))
    '''

    def __init__(self, file):
        '''
        file can be either a path (string) or an already opened binary file object.
        If a path is given, the file will be opened in 'wb' mode.
        '''
        if isinstance(file, str):
            self._file = open(file, 'wb')
            self._own_file = True
        else:
            self._file = file
            self._own_file = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self._own_file and self._file is not None:
            self._file.close()
            self._file = None

    def _write_int64(self, value: int) -> None:
        self._file.write(value.to_bytes(8, 'little'))

    def var(self, index: int) -> None:
        '''Write a variable term.'''
        self._file.write(b'\x00')
        self._write_int64(index)

    def int(self, value: int) -> None:
        '''Write an integer term.'''
        self._file.write(b'\x01')
        self._write_int64(value)

    def float(self, value: float) -> None:
        '''Write a float term.'''
        self._file.write(b'\x02')
        self._write_int64(struct.unpack('<q', struct.pack('<d', value))[0])

    def string(self, s: str) -> None:
        '''Write a string term.'''
        data = s.encode('utf-8')
        self._file.write(b'\x03')
        self._write_int64(len(data))
        self._file.write(data)

    def cons(self, functor_id: int, arity: int) -> None:
        '''
        Write the header of a compound term (constructor).
        After calling this, you must write exactly `arity` term bodies
        using the same writer (e.g., call .var(), .int(), etc.).
        '''

        self._file.write(b'\x04')
        self._write_int64(functor_id)
        self._write_int64(arity)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} [--print] <trace file>', file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == '--print':
        if len(sys.argv) != 3:
            print(f'Usage: {sys.argv[0]} --print <trace file>', file=sys.stderr)
            sys.exit(1)

        print_trace(sys.argv[2])

    else:
        stats = analyze_trace(sys.argv[1])
        print('Trace length:', stats['trace_length'])
        print('Functor count:', stats['functor_count'])
        print('Variable count:', stats['var_count'])
        print('Total size:', stats['total_vertices'])
