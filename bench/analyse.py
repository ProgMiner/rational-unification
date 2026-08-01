#!/usr/bin/env python3

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import scikit_posthocs as sp
from pathlib import Path
from itertools import combinations
from statsmodels.stats.multitest import multipletests


TRACES_DIR = './traces'
SAMPLES_DIR = './samples'
ALGOS = ['robinson', 'rational', 'huet']


def compare_trace(var, trace_set, trace_name, alpha=0.05):
    data = {}

    for alg in ALGOS:
        file_path = Path(SAMPLES_DIR) / var / alg / trace_set / f'{trace_name}.tsv'

        if not file_path.exists():
            print(f'Warning: file not found {file_path}')
            continue

        # Read TSV
        df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
        times = df['time'].dropna().values

        if len(times) == 0:
            print(f'Warning: file {file_path} contains no data')
            continue

        data[alg] = times

    if len(data) < 2:
        print('Insufficient data for comparison (need at least two algorithms with data)')
        return

    df_long = pd.DataFrame([
        {'algorithm': alg, 'time': t}
        for alg, times in data.items()
        for t in times
    ])

    # 1. Medians and basic statistics
    medians = {alg: np.median(times) for alg, times in data.items()}

    print('='*60)
    print('Results for trace:', trace_name)

    print('='*60)
    print('Median time (sec):')

    for alg, med in medians.items():
        print(f'  {alg:30s} : {med:.6f}')

    # 2. Kruskal-Wallis test (comparison of all groups)
    h_stat, p_kw = stats.kruskal(*list(data.values()))

    print(f'\nKruskal-Wallis H-test: H = {h_stat:.4f}, p-value = {p_kw:.6f}')

    if p_kw < alpha:
        print('  -> Reject H0: there are statistically significant differences between algorithms.')

    else:
        print('  -> Fail to reject H0: no differences detected between algorithms.')

    # 3. Post-hoc Dunn test (pairwise) with Bonferroni correction
    if p_kw < alpha:
        if len(data) >= 3:
            dunn_result = sp.posthoc_dunn(df_long, val_col='time', group_col='algorithm', p_adjust='bonferroni')
            print('\nPost-hoc Dunn test (p-values, Bonferroni corrected):')
            print(dunn_result.round(6))

            sig_pairs = []
            for i, alg1 in enumerate(dunn_result.columns):
                for alg2 in dunn_result.columns[i+1:]:
                    p_val = dunn_result.loc[alg1, alg2]
                    if p_val < alpha:
                        sig_pairs.append((alg1, alg2, p_val))

            if sig_pairs:
                print(f'\nStatistically significant differences between pairs (p < {alpha}):')

                for a1, a2, pv in sig_pairs:
                    print(f'  {a1} vs {a2} : p = {pv:.6f}')

            else:
                print(f'\nNo significant pairwise differences detected at α={alpha}.')

        elif len(data) == 2:
            # For two groups, Kruskal-Wallis is equivalent to Mann-Whitney U
            # but post-hoc is not needed, just report
            print('\nOnly two algorithms with data. Significant difference confirmed by Kruskal-Wallis.')

            alg1, alg2 = list(data.keys())
            sig_pairs = [(alg1, alg2, p_kw)]

            # optionally compute Cliff's delta or median ratio
            times1, times2 = data[alg1], data[alg2]
            ratio = medians[alg1] / medians[alg2] if medians[alg2] != 0 else np.inf
            print(f'  Median ratio ({alg1} / {alg2}) = {ratio:.3f}')

    pairwise_metrics = {}
    algs_list = list(data.keys())
    for a, b in combinations(algs_list, 2):
        ratio = medians[a] / medians[b] if medians[b] != 0 else np.inf

        # Cliff's delta
        n_a = len(data[a])
        n_b = len(data[b])
        gt = sum(1 for x in data[a] for y in data[b] if x > y)
        lt = sum(1 for x in data[a] for y in data[b] if x < y)
        cliff = (gt - lt) / (n_a * n_b) if n_a * n_b > 0 else np.nan

        pairwise_metrics[f'{a}_vs_{b}'] = {
            'ratio_median': ratio,
            'cliff_delta': cliff,
            'faster': a if ratio < 1 else b if ratio > 1 else 'equal',
        }

    return {
        'trace_name': trace_name,
        'medians': medians,
        'p_kruskal': p_kw,
        'significant_pairs': sig_pairs if p_kw < alpha else [],
        'pairwise_metrics': pairwise_metrics,
        'data': data,
    }


def run_all_traces(var, trace_set, alpha=0.05):
    traces_path = Path(TRACES_DIR) / trace_set
    if not traces_path.exists():
        print(f'Error: directory {traces_path} not found')
        return

    trace_files = list(traces_path.rglob('*.trace'))
    if not trace_files:
        print(f'Files in directory {traces_dir} not found')
        return

    print(f'Found {len(trace_files)} files')

    results = []
    for trace_file in trace_files:
        rel_path = trace_file.relative_to(traces_path)
        trace_name = str(rel_path.with_suffix(''))

        try:
            res = compare_trace(var, trace_set, trace_name, alpha)

            if res is not None:
                results.append(res)

        except Exception as e:
            print(f'Error processing {trace_name}:', e)

        print()

    p_vals = [res['p_kruskal'] for res in results]
    reject, p_corrected, _, _ = multipletests(p_vals, alpha=alpha, method='fdr_bh')

    # Apply corrected p-values and recompute significant_pairs
    for i, res in enumerate(results):
        res['p_kruskal_corrected'] = p_corrected[i]
        res['reject_h0_corrected'] = reject[i]

    print('Tests processed:', len(results))
    return results


def aggregate_results(results_list):
    """
    Parameters:
        results_list: list of dictionaries returned by compare_trace
    Returns:
        summary_traces: DataFrame (trace, medians, significant pairs)
        summary_pairs: DataFrame (algorithm pair, number of wins, average speedup)
        win_counts: DataFrame (total number of traces where algorithm is significantly faster)
    """

    pair_data = {}
    rows_traces = []
    for res in results_list:
        trace = res['trace_name']
        med = res['medians']

        # Use corrected flag if present, otherwise raw p_kruskal < alpha
        if 'reject_h0_corrected' in res:
            has_significant = res['reject_h0_corrected']
        else:
            has_significant = res['p_kruskal'] < alpha

        if has_significant:
            sig_pairs = res.get('significant_pairs', [])
        else:
            sig_pairs = []

        p_kw = res['p_kruskal']

        wins = []
        for a,b,_ in sig_pairs:
            if med[a] < med[b]:
                wins.append(f"{a} > {b}")
            else:
                wins.append(f"{b} > {a}")

        win_str = "; ".join(wins)
        row = {
            'trace': trace,
            'p_kruskal': p_kw,
            'significant_wins': win_str if win_str else 'none'
        }

        for alg, m in med.items():
            row[f'median_{alg}'] = m

        rows_traces.append(row)

        for (pair_key, metrics) in res['pairwise_metrics'].items():
            a, b = pair_key.split('_vs_')

            is_sig = any((a==x and b==y) or (a==y and b==x) for (x,y,_) in sig_pairs)
            pair_data.setdefault((a,b), []).append({
                'trace': trace,
                'ratio': metrics['ratio_median'],
                'cliff': metrics['cliff_delta'],
                'faster': metrics['faster'],
                'significant': is_sig
            })

    df_traces = pd.DataFrame(rows_traces)
    df_traces.set_index('trace', inplace=True)

    pair_summaries = []
    for (a,b), records in pair_data.items():
        df = pd.DataFrame(records)

        n_sig = df['significant'].sum()
        n_a_faster = ((df['faster'] == a) & df['significant']).sum()
        n_b_faster = ((df['faster'] == b) & df['significant']).sum()
        n_not_sig = n_sig - n_a_faster - n_b_faster

        median_ratio = df['ratio'].mean()
        geom_mean = np.exp(np.mean(np.log(df['ratio'])))

        median_cliff = df['cliff'].median()
        mean_cliff = df['cliff'].mean()

        pair_summaries.append({
            'pair': f'{a} vs {b}',
            'A_faster_sig': n_a_faster,
            'B_faster_sig': n_b_faster,
            'non_sig': n_not_sig,
            'total_traces': len(df),
            'median_ratio': median_ratio,
            'geom_mean_ratio': geom_mean,
            'median_cliff': median_cliff,
            'mean_cliff': mean_cliff,
        })

    df_pairs = pd.DataFrame(pair_summaries)
    df_pairs.set_index('pair', inplace=True)

    win_count = {}
    for alg in set([a for (a,b) in pair_data.keys()] + [b for (a,b) in pair_data.keys()]):
        win_count[alg] = 0

    for (a,b), records in pair_data.items():
        for rec in records:
            if rec['significant']:
                win_count[rec['faster']] += 1

    df_wins = pd.DataFrame(list(win_count.items()), columns=['algorithm', 'significant_wins'])
    df_wins.sort_values(by='significant_wins', ascending=False, inplace=True)
    df_wins.set_index('algorithm', inplace=True)

    return {
        'trace_summary': df_traces,
        'pair_summary': df_pairs,
        'win_counts': df_wins,
        'detailed_pair_data': pair_data,
    }


def list_subdirs(path):
    if not isinstance(path, Path):
        path = Path(path)

    try:
        available = [item.name for item in path.iterdir() if item.is_dir()]

    except OSError:
        available = None

    if not available:
        return '(no available values)'

    return ', '.join(available)


def print_usage():
    print(f'Usage: {sys.argv[0]} <variant> <trace set>')

    print('  - <variant> can be one of:', list_subdirs(SAMPLES_DIR))
    print('  - <trace set> can be one of:', list_subdirs(TRACES_DIR))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print_usage()
        exit(1)

    all_results = run_all_traces(sys.argv[1], sys.argv[2], alpha=0.05)
    agg = aggregate_results(all_results)

    print('=== By trace ===')
    print(agg['trace_summary'].to_string())

    print('\n=== By pair (aggregated) ===')
    print(agg['pair_summary'].to_string())

    print('\n=== Total number of significant wins ===')
    print(agg['win_counts'].to_string())
