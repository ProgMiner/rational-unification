#!/usr/bin/env python3
"""
compare_ephemeral_variants.py

Compares ephemeral and ephemeral_path_comp variants for a given algorithm.
For each trace (test), computes median times, performs Mann-Whitney test,
calculates median ratio and Cliff's delta. Results are aggregated and displayed as tables.

Command-line arguments:
    algorithm  – one of: robinson, rational, huet
    trace_set  – (optional) trace set (subdirectory in ./traces)
                 If not specified, all available trace sets are used.
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path
from itertools import combinations
from statsmodels.stats.multitest import multipletests

TRACES_DIR = './traces'
SAMPLES_DIR = './samples'
VARIANTS = ['ephemeral', 'ephemeral_path_comp']
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
    print(f'Usage: {sys.argv[0]} <algorithm> [trace_set]')
    print('  - <algorithm> can be one of:', ', '.join(ALGOS))
    print('  - <trace_set> can be one of:', list_subdirs(TRACES_DIR))
    print('    If trace_set is omitted, all available trace sets are used.')

def compare_trace(algorithm, trace_set, trace_name, alpha=0.05):
    """Compares ephemeral and ephemeral_path_comp on a single trace."""
    data = {}
    for var in VARIANTS:
        file_path = Path(SAMPLES_DIR) / var / algorithm / trace_set / f'{trace_name}.tsv'
        if not file_path.exists():
            print(f'Warning: file not found {file_path}')
            continue
        try:
            df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
            times = df['time'].dropna().values
            if len(times) == 0:
                print(f'Warning: file {file_path} contains no data')
                continue
            data[var] = times
        except Exception as e:
            print(f'Error reading {file_path}: {e}')
            continue

    if len(data) < 2:
        print(f'Insufficient data for comparison (need both variants)')
        return None

    # Medians
    medians = {var: np.median(times) for var, times in data.items()}

    # Mann-Whitney test
    u_stat, p_mw = stats.mannwhitneyu(data['ephemeral'], data['ephemeral_path_comp'],
                                      alternative='two-sided')
    print('='*60)
    print(f'Results for trace: {trace_name} (algorithm: {algorithm})')
    print('Median time (sec):')
    for var, med in medians.items():
        print(f'  {var:30s} : {med:.6f}')
    print(f'\nMann-Whitney U-test: U = {u_stat:.4f}, p-value = {p_mw:.6f}')

    # Cliff's delta
    a = data['ephemeral']
    b = data['ephemeral_path_comp']
    n_a, n_b = len(a), len(b)
    gt = sum(1 for x in a for y in b if x > y)
    lt = sum(1 for x in a for y in b if x < y)
    cliff = (gt - lt) / (n_a * n_b) if n_a * n_b > 0 else np.nan
    ratio = medians['ephemeral'] / medians['ephemeral_path_comp'] if medians['ephemeral_path_comp'] != 0 else np.inf

    print(f'Median ratio (ephemeral / ephemeral_path_comp) = {ratio:.3f}')
    print(f"Cliff's delta = {cliff:.3f}")
    if p_mw < alpha:
        print('  -> Significant difference detected.')
    else:
        print('  -> No significant difference.')

    return {
        'trace_name': trace_name,
        'medians': medians,
        'p_value': p_mw,
        'ratio_median': ratio,
        'cliff_delta': cliff,
        'significant': p_mw < alpha,
        'data': data
    }

def run_all_traces(algorithm, trace_set=None, alpha=0.05):
    """Iterates through all traces in the specified trace_set (or all) and returns a list of results."""
    if trace_set is None:
        # All available trace sets
        traces_dir = Path(TRACES_DIR)
        if not traces_dir.exists():
            print(f'Error: {TRACES_DIR} does not exist.')
            return []
        trace_sets = [d.name for d in traces_dir.iterdir() if d.is_dir()]
        if not trace_sets:
            print(f'No trace sets found in {TRACES_DIR}')
            return []
    else:
        trace_sets = [trace_set]

    all_results = []
    for ts in trace_sets:
        traces_path = Path(TRACES_DIR) / ts
        if not traces_path.exists():
            print(f'Warning: trace set directory {traces_path} not found, skipping.')
            continue
        trace_files = list(traces_path.rglob('*.trace'))
        if not trace_files:
            print(f'No .trace files found in {traces_path}')
            continue

        print(f'Processing trace set: {ts}, found {len(trace_files)} files')
        for trace_file in trace_files:
            rel_path = trace_file.relative_to(traces_path)
            trace_name = str(rel_path.with_suffix(''))
            res = compare_trace(algorithm, ts, trace_name, alpha)
            if res is not None:
                # Add trace_set identifier for uniqueness
                res['trace_set'] = ts
                res['full_name'] = f"{ts}::{trace_name}"
                all_results.append(res)
            print()

    # Correction for multiple testing (FDR)
    if all_results:
        p_vals = [r['p_value'] for r in all_results]
        reject, p_corrected, _, _ = multipletests(p_vals, alpha=alpha, method='fdr_bh')
        for i, r in enumerate(all_results):
            r['p_corrected'] = p_corrected[i]
            r['significant_corrected'] = reject[i]

    return all_results

def aggregate_results(results, algorithm):
    """
    Constructs summary tables:
    - trace_summary: median, p-value, significance for each trace
    - pair_summary: aggregated metrics for pair ephemeral vs ephemeral_path_comp
    - win_counts: count of significant wins for each variant
    """
    if not results:
        print("No results to aggregate.")
        return None

    # Table by trace
    rows = []
    for r in results:
        row = {
            'trace': r['full_name'],
            'median_ephemeral': r['medians']['ephemeral'],
            'median_ephemeral_path_comp': r['medians']['ephemeral_path_comp'],
            'p_value': r['p_value'],
            'p_corrected': r.get('p_corrected', r['p_value']),
            'significant': r.get('significant_corrected', r['significant']),
            'ratio_median': r['ratio_median'],
            'cliff_delta': r['cliff_delta']
        }
        rows.append(row)
    df_traces = pd.DataFrame(rows).set_index('trace')

    # Aggregated metrics for pair
    n_total = len(results)
    n_sig = sum(r['significant_corrected'] for r in results if 'significant_corrected' in r)
    n_ephemeral_faster = sum((r['significant_corrected'] and r['ratio_median'] < 1.0)
                             for r in results if 'significant_corrected' in r)
    n_path_comp_faster = sum((r['significant_corrected'] and r['ratio_median'] > 1.0)
                             for r in results if 'significant_corrected' in r)

    # Median ratio, geometric mean
    ratios = [r['ratio_median'] for r in results]
    median_ratio = np.median(ratios)
    geom_mean_ratio = np.exp(np.mean(np.log(ratios)))
    cliffs = [r['cliff_delta'] for r in results]
    median_cliff = np.median(cliffs)
    mean_cliff = np.mean(cliffs)

    pair_summary = pd.DataFrame([{
        'pair': 'ephemeral vs ephemeral_path_comp',
        'algorithm': algorithm,
        'total_traces': n_total,
        'significant_traces': n_sig,
        'ephemeral_faster_sig': n_ephemeral_faster,
        'ephemeral_path_comp_faster_sig': n_path_comp_faster,
        'median_ratio': median_ratio,
        'geom_mean_ratio': geom_mean_ratio,
        'median_cliff': median_cliff,
        'mean_cliff': mean_cliff
    }]).set_index('pair')

    # Number of significant wins (separately)
    win_counts = pd.DataFrame([
        {'variant': 'ephemeral', 'significant_wins': n_ephemeral_faster},
        {'variant': 'ephemeral_path_comp', 'significant_wins': n_path_comp_faster}
    ]).set_index('variant').sort_values('significant_wins', ascending=False)

    return {
        'trace_summary': df_traces,
        'pair_summary': pair_summary,
        'win_counts': win_counts
    }

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print_usage()
        sys.exit(1)

    algorithm = sys.argv[1]
    if algorithm not in ALGOS:
        print(f"Error: unknown algorithm '{algorithm}'.")
        print_usage()
        sys.exit(1)

    trace_set = sys.argv[2] if len(sys.argv) == 3 else None

    print(f"Comparing ephemeral vs ephemeral_path_comp for algorithm '{algorithm}'...")
    results = run_all_traces(algorithm, trace_set, alpha=0.05)
    if not results:
        print("No results found.")
        return

    agg = aggregate_results(results, algorithm)

    print('\n=== Trace summary ===')
    print(agg['trace_summary'].to_string())
    print('\n=== Pair aggregated metrics ===')
    print(agg['pair_summary'].to_string())
    print('\n=== Significant wins count ===')
    print(agg['win_counts'].to_string())

if __name__ == '__main__':
    main()
