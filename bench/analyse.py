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


def compare_test(var, test_name, alpha=0.05):
    data = {}

    for alg in ALGOS:
        file_path = Path(SAMPLES_DIR) / var / alg / f'{test_name}.tsv'

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
    print('Results for test:', test_name)

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
    if p_kw < alpha and len(data) >= 3:
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

    elif len(data) == 2 and p_kw < alpha:
        # For two groups, Kruskal-Wallis is equivalent to Mann-Whitney U
        # but post-hoc is not needed, just report
        print('\nOnly two algorithms with data. Significant difference confirmed by Kruskal-Wallis.')

        # optionally compute Cliff's delta or median ratio
        alg1, alg2 = list(data.keys())
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
        'test_name': test_name,
        'medians': medians,
        'p_kruskal': p_kw,
        'significant_pairs': sig_pairs if p_kw < alpha and len(data)>=3 else None,
        'pairwise_metrics': pairwise_metrics,
        'data': data,
    }


def run_all_tests(var, alpha=0.05):
    traces_path = Path(TRACES_DIR)
    if not traces_path.exists():
        print(f'Error: directory {TRACES_DIR} not found')
        return

    trace_files = list(traces_path.rglob('*.trace'))
    if not trace_files:
        print(f'Files in directory {traces_dir} not found')
        return

    print(f'Found {len(trace_files)} files')

    results = []
    for trace_file in trace_files:
        rel_path = trace_file.relative_to(traces_path)
        test_name = str(rel_path.with_suffix(''))

        try:
            res = compare_test(var, test_name, alpha)

            if res is not None:
                results.append(res)

        except Exception as e:
            print(f'Error processing {test_name}:', e)

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
        results_list: list of dictionaries returned by compare_test
    Returns:
        summary_tests: DataFrame (test, medians, significant pairs)
        summary_pairs: DataFrame (algorithm pair, number of wins, average speedup)
        win_counts: DataFrame (total number of tests where algorithm is significantly faster)
    """

    pair_data = {}
    rows_tests = []
    for res in results_list:
        test = res['test_name']
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
            'test': test,
            'p_kruskal': p_kw,
            'significant_wins': win_str if win_str else 'none'
        }

        for alg, m in med.items():
            row[f'median_{alg}'] = m

        rows_tests.append(row)

        for (pair_key, metrics) in res['pairwise_metrics'].items():
            a, b = pair_key.split('_vs_')

            is_sig = any((a==x and b==y) or (a==y and b==x) for (x,y,_) in sig_pairs)
            pair_data.setdefault((a,b), []).append({
                'test': test,
                'ratio': metrics['ratio_median'],
                'cliff': metrics['cliff_delta'],
                'faster': metrics['faster'],
                'significant': is_sig
            })

    df_tests = pd.DataFrame(rows_tests)
    df_tests.set_index('test', inplace=True)

    pair_summaries = []
    for (a,b), records in pair_data.items():
        df = pd.DataFrame(records)
        n_total = len(df)
        n_sig = df['significant'].sum()
        n_a_faster = ((df['faster'] == a) & df['significant']).sum()
        n_b_faster = ((df['faster'] == b) & df['significant']).sum()
        n_not_sig = n_sig - n_a_faster - n_b_faster

        # For all tests (including non-significant) compute median ratio
        median_ratio = df['ratio'].median()

        # Also geometric mean (more robust for ratios)
        geom_mean = np.exp(np.mean(np.log(df['ratio'])))

        pair_summaries.append({
            'pair': f'{a} vs {b}',
            'A_faster_sig': n_a_faster,
            'B_faster_sig': n_b_faster,
            'non_sig': n_not_sig,
            'total_tests': n_total,
            'median_ratio': median_ratio,
            'geom_mean_ratio': geom_mean
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
        'test_summary': df_tests,
        'pair_summary': df_pairs,
        'win_counts': df_wins,
        'detailed_pair_data': pair_data,
    }


def print_usage():
    print(f'Usage: {sys.argv[0]} <variant>')

    try:
        available = ', '.join([item.name for item in Path(SAMPLES_DIR).iterdir() if item.is_dir()])
        print('  <variant> can be one of:', available)
    except OSError:
        print('  <variant>: no available values')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print_usage()
        exit(1)

    all_results = run_all_tests(sys.argv[1], alpha=0.05)
    agg = aggregate_results(all_results)

    print('=== By test ===')
    print(agg['test_summary'].to_string())

    print('\n=== By pair (aggregated) ===')
    print(agg['pair_summary'].to_string())

    print('\n=== Total number of significant wins ===')
    print(agg['win_counts'].to_string())
