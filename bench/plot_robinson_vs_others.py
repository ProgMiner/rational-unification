#!/usr/bin/env python3
"""
plot_robinson_vs_others.py

Строит точечный график сравнения медианного времени алгоритма robinson
с rational и huet. Каждая точка — один тест (trace).
Оси: X = время robinson (медиана), Y = время rational / huet (медиана).

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
ALGOS = ['robinson', 'rational', 'huet']

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
    """Загружает медианные времена для одного trace_set."""
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

        # Проверяем наличие результата для robinson (обязательное условие)
        rob_path = Path(SAMPLES_DIR) / variant / 'robinson' / trace_set / f'{trace_name}.tsv'
        if not rob_path.exists():
            continue

        trace_meds = {}
        for alg in ALGOS:
            file_path = Path(SAMPLES_DIR) / variant / alg / trace_set / f'{trace_name}.tsv'
            if not file_path.exists():
                continue
            try:
                df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
                times = df['time'].dropna().values
                if len(times) > 0:
                    trace_meds[alg] = np.median(times)
            except Exception as e:
                print(f'Warning: could not read {file_path}: {e}')
        if 'robinson' in trace_meds:
            medians[trace_name] = trace_meds
    return medians

def load_all_medians(variant, trace_sets):
    """Объединяет медианы из нескольких trace_set.
    Возвращает общий словарь: ключ = 'trace_set::trace_name'."""
    all_medians = {}
    for ts in trace_sets:
        meds = load_medians_for_trace_set(variant, ts)
        for trace_name, trace_meds in meds.items():
            # Добавляем префикс с именем trace_set, чтобы избежать коллизий имён
            composite_name = f"{ts}::{trace_name}"
            all_medians[composite_name] = trace_meds
    return all_medians

def plot_comparison(medians, variant, trace_set_label):
    if not medians:
        print("No data to plot.")
        return

    points_rational = []   # (robinson_median, rational_median, label)
    points_huet = []

    for trace_label, meds in medians.items():
        rob = meds['robinson']
        if 'rational' in meds:
            points_rational.append((rob, meds['rational'], trace_label))
        if 'huet' in meds:
            points_huet.append((rob, meds['huet'], trace_label))

    fig, ax = plt.subplots(figsize=(8, 8))

    if points_rational:
        xs, ys, names = zip(*points_rational)
        ax.scatter(xs, ys, c='blue', alpha=0.7, label='rational',
                   edgecolors='k', linewidth=0.3)
    if points_huet:
        xs, ys, names = zip(*points_huet)
        ax.scatter(xs, ys, c='red', alpha=0.7, label='huet',
                   edgecolors='k', linewidth=0.3)

    # Линия y = x
    all_times = []
    for _, meds in medians.items():
        all_times.extend(meds.values())
    if all_times:
        min_val = min(all_times) * 0.5
        max_val = max(all_times) * 2.0
        line_vals = [min_val, max_val]
        ax.plot(line_vals, line_vals, 'k--', alpha=0.6, label='y = x')
        ax.set_xlim(min_val, max_val)
        ax.set_ylim(min_val, max_val)

    ax.set_xlabel('robinson median time (ms)')
    ax.set_ylabel('other algorithm median time (ms)')
    # ax.set_title(f'robinson vs rational / huet\n(variant={variant}, trace_set={trace_set_label})')
    ax.legend()
    ax.grid(True, alpha=0.3, which='both')
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Имя файла: заменяем '::' и недопустимые символы
    safe_label = trace_set_label.replace('::', '_').replace(' ', '_')
    out_name = f'robinson_comparison_{variant}_{safe_label}.png'
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
        # Все доступные trace_set
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

    print(f'Found {len(medians)} traces with robinson data.')
    plot_comparison(medians, variant, trace_set_label)

if __name__ == '__main__':
    main()
