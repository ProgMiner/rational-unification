#!/usr/bin/env python3

import re
import sys


def parse_term(s, pos=0):
    # skip spaces
    while pos < len(s) and s[pos] == ' ':
        pos += 1
    if s.startswith('_', pos):
        m = re.match(r'_(\d+)', s[pos:])
        if not m:
            raise ValueError(f"bad var at {pos}: {s[pos:pos+40]}")
        return ('var', int(m.group(1))), pos + m.end()
    m = re.match(r'(int|float|string)<', s[pos:])
    if m:
        kind = m.group(1)
        p = pos + m.end()
        depth = 1
        q = p
        while q < len(s) and depth:
            if s[q] == '<':
                depth += 1
            elif s[q] == '>':
                depth -= 1
            q += 1
        if depth:
            raise ValueError("unterminated atomic")
        return (kind, s[p:q-1]), q
    m = re.match(r'boxed (\d+) <', s[pos:])
    if not m:
        raise ValueError(f"bad term at {pos}: {s[pos:pos+80]}")
    tag = int(m.group(1))
    p = pos + m.end()
    args = []
    while True:
        arg, p = parse_term(s, p)
        args.append(arg)
        while p < len(s) and s[p] == ' ':
            p += 1
        if p < len(s) and s[p] == ',':
            p += 1
            continue
        if p < len(s) and s[p] == '>':
            return ('con', tag, tuple(args)), p + 1
        raise ValueError(f"expected , or > at {p}: {s[p:p+80]}")


def parse_dump(path):
    sub = {}
    with open(path) as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip() or '\t' in line:
                continue
            m = re.match(r'\s*(\d+) -> ', line)
            if not m:
                raise ValueError(f"bad dump line: {line!r}")
            k = int(m.group(1))
            term, p = parse_term(line, m.end())
            if p != len(line):
                raise ValueError(f"trailing input in {line!r}: {p} {line[p:]}")
            sub[k] = term
    return sub


def eq_terms(a, b, sa, sb, seen):
    # resolve variable references through substitutions
    if isinstance(a, tuple) and a and a[0] == 'var':
        aid = a[1]
        if aid in sa:
            key = ('v', aid)
            if key in seen:
                return True
            seen.add(key)
            return eq_terms(sa[aid], b, sa, sb, seen)
        a = ('free', aid)
    if isinstance(b, tuple) and b and b[0] == 'var':
        bid = b[1]
        if bid in sb:
            key = ('v', bid)
            if key in seen:
                return True
            seen.add(key)
            return eq_terms(a, sb[bid], sa, sb, seen)
        b = ('free', bid)

    if isinstance(a, tuple) and isinstance(b, tuple) and type(a) is not tuple:
        pass

    # atomic / free
    if a[0] in ('int', 'float', 'string', 'free') or b[0] in ('int', 'float', 'string', 'free'):
        return a == b

    if a[0] != 'con' or b[0] != 'con' or a[1] != b[1] or len(a[2]) != len(b[2]):
        return False

    key = ('c', id(a), id(b))
    if key in seen:
        return True
    seen.add(key)
    for x, y in zip(a[2], b[2]):
        if not eq_terms(x, y, sa, sb, seen):
            return False
    return True


def eq_subs(sa, sb):
    ids = set(sa) | set(sb)
    # include referenced variables
    def collect(t, out):
        if not isinstance(t, tuple):
            return
        if t and t[0] == 'var':
            out.add(t[1])
        elif t and t[0] == 'con':
            for x in t[2]:
                collect(x, out)
    for sub in (sa, sb):
        for t in sub.values():
            collect(t, ids)
    for i in sorted(ids):
        if not eq_terms(('var', i), ('var', i), sa, sb, set()):
            return False, i
    return True, None


if __name__ == '__main__':
    sa = parse_dump(sys.argv[1])
    sb = parse_dump(sys.argv[2])
    ok, i = eq_subs(sa, sb)
    print(('SEM_MATCH' if ok else f'SEM_DIFF var={i}'))
    sys.exit(0 if ok else 1)
