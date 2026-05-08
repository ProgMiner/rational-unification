#!/usr/bin/env python3
"""
plot_huet_vs_rational.py

Строит точечный график сравнения медианного времени алгоритмов huet и rational.
Оси: X = время huet (медиана), Y = время rational (медиана).
Каждая точка — один тест (trace). Алгоритм robinson игнорируется.

Аргументы командной строки:
    variant    – вариант (поддиректория в ./samples)
    trace_set  – (опционально) набор трасс (поддиректория в ./traces)
                 Если не указан, используются все имеющиеся trace_set.
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

TRACES_DIR = './traces'
SAMPLES_DIR = './samples'
# Интересуют только huet и rational
ALGOS = ['huet', 'rational']

def list_subdirs(path):
    if not isinstance(path, Path):
        path = Path(path)
    try:
        available = [item.name for item in path.iterdir() if item.is_dir()]
    except OSError:
        available = []
    if not available:
        return '(no available values)'
    return ', '.join(available)

def print_usage():
    print(f'Usage: {sys.argv[0]} <variant> [trace_set]')
    print('  - <variant> can be one of:', list_subdirs(SAMPLES_DIR))
    print('  - <trace_set> can be one of:', list_subdirs(TRACES_DIR))
    print('    If trace_set is omitted, all available trace sets are used.')

def load_medians_for_trace_set(variant, trace_set):
    """Загружает медианные времена huet и rational для одного trace_set.
    Возвращает словарь: ключ = trace_name, значение = словарь с ключами 'huet','rational'.
    Включаются только трейсы, где присутствуют оба алгоритма."""
    traces_path = Path(TRACES_DIR) / trace_set
    if not traces_path.exists():
        print(f'Error: directory {traces_path} not found')
        return {}

    trace_files = list(traces_path.rglob('*.trace'))
    if not trace_files:
        print(f'No .trace files found in {traces_path}')
        return {}

    medians = {}
    for trace_file in trace_files:
        rel_path = trace_file.relative_to(traces_path)
        trace_name = str(rel_path.with_suffix(''))

        trace_meds = {}
        for alg in ALGOS:
            file_path = Path(SAMPLES_DIR) / variant / alg / trace_set / f'{trace_name}.tsv'
            if not file_path.exists():
                break   # если одного алг-ма нет – пропускаем трейс
            try:
                df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
                times = df['time'].dropna().values
                if len(times) > 0:
                    trace_meds[alg] = np.median(times)
                else:
                    break
            except Exception as e:
                print(f'Warning: could not read {file_path}: {e}')
                break
        # Убеждаемся, что оба алгоритма загружены
        if 'huet' in trace_meds and 'rational' in trace_meds:
            medians[trace_name] = trace_meds
    return medians

def load_all_medians(variant, trace_sets):
    """Объединяет медианы из нескольких trace_set.
    Возвращает общий словарь: ключ = 'trace_set::trace_name'.
    """
    all_medians = {}
    for ts in trace_sets:
        meds = load_medians_for_trace_set(variant, ts)
        for trace_name, trace_meds in meds.items():
            composite_name = f"{ts}::{trace_name}"
            all_medians[composite_name] = trace_meds
    return all_medians

def plot_comparison(medians, variant, trace_set_label):
    if not medians:
        print("No traces with both huet and rational data.")
        return

    points = []   # (huet_median, rational_median, label)
    for trace_label, meds in medians.items():
        points.append((meds['huet'], meds['rational'], trace_label))

    xs, ys, names = zip(*points)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(xs, ys, c='green', alpha=0.7, edgecolors='k', linewidth=0.3,
               label=f'{len(points)} traces')

    # Линия y = x
    all_times = [m for p in points for m in (p[0], p[1])]
    if all_times:
        min_val = min(all_times) * 0.5
        max_val = max(all_times) * 2.0
        line_vals = [min_val, max_val]
        ax.plot(line_vals, line_vals, 'k--', alpha=0.6, label='y = x')
        ax.set_xlim(min_val, max_val)
        ax.set_ylim(min_val, max_val)

    ax.set_xlabel('huet median time (s)')
    ax.set_ylabel('rational median time (s)')
    ax.set_title(f'huet vs rational\n(variant={variant}, trace_set={trace_set_label})')
    ax.legend()
    ax.grid(True, alpha=0.3, which='both')
    ax.set_xscale('log')
    ax.set_yscale('log')

    safe_label = trace_set_label.replace('::', '_').replace(' ', '_')
    out_name = f'huet_vs_rational_{variant}_{safe_label}.png'
    plt.tight_layout()
    plt.savefig(out_name, dpi=150)
    print(f'Plot saved to {out_name}')
    plt.show()

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print_usage()
        sys.exit(1)

    variant = sys.argv[1]
    if len(sys.argv) == 3:
        trace_sets = [sys.argv[2]]
        trace_set_label = sys.argv[2]
    else:
        traces_dir = Path(TRACES_DIR)
        if not traces_dir.exists():
            print(f'Error: {TRACES_DIR} does not exist.')
            sys.exit(1)
        trace_sets = [d.name for d in traces_dir.iterdir() if d.is_dir()]
        if not trace_sets:
            print(f'No trace sets found in {TRACES_DIR}')
            sys.exit(1)
        trace_set_label = 'all_trace_sets'

    print(f'Loading data for variant="{variant}", trace_set(s)={trace_sets}...')
    if len(trace_sets) == 1:
        medians = load_medians_for_trace_set(variant, trace_sets[0])
    else:
        medians = load_all_medians(variant, trace_sets)

    print(f'Found {len(medians)} traces with both huet and rational.')
    plot_comparison(medians, variant, trace_set_label)

if __name__ == '__main__':
    main()
