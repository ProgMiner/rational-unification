#!/usr/bin/env python3
"""
Script to build scatter plot with linear regression:
- X axis: median time of Robinson algorithm
- Y axis: median time of target algorithm (rational, huet)
- Error bars (whiskers) show IQR (Q1, Q3)
- Auto-merges all trace sets for given variant

Usage:
    ./robinson_corr.py <variant> [--output <file>]
"""

import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SAMPLES_DIR = SCRIPT_DIR / 'samples'
ROBINSON = 'robinson'
TARGET_ALGOS = ['rational', 'huet']
COLORS = {
    'rational': 'green',
    'huet': 'red'
}


def get_trace_names_from_robinson(variant: str, trace_set: str) -> list:
    """Get all trace names from robinson samples directory."""
    robinson_path = SAMPLES_DIR / variant / ROBINSON / trace_set
    if not robinson_path.exists():
        raise FileNotFoundError(f"Robinson samples not found: {robinson_path}")
    
    tsv_files = list(robinson_path.rglob('*.tsv'))
    trace_names = []
    for f in tsv_files:
        rel = f.relative_to(robinson_path).with_suffix('')
        trace_names.append(str(rel))
    return sorted(trace_names)


def load_times(variant: str, algo: str, trace_set: str, trace_name: str) -> np.ndarray:
    """Load time values from TSV file."""
    file_path = SAMPLES_DIR / variant / algo / trace_set / f"{trace_name}.tsv"
    if not file_path.exists():
        return np.array([])
    df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
    return df['time'].dropna().values


def collect_all_trace_names(variant: str) -> dict:
    """
    Get all trace names from all trace sets for given variant.
    Returns dict: {trace_set: [trace_names]}
    """
    robinson_root = SAMPLES_DIR / variant / ROBINSON
    if not robinson_root.exists():
        raise FileNotFoundError(f"Robinson samples not found: {robinson_root}")
    
    trace_sets = {}
    for trace_set_dir in robinson_root.iterdir():
        if trace_set_dir.is_dir():
            trace_names = get_trace_names_from_robinson(variant, trace_set_dir.name)
            if trace_names:
                trace_sets[trace_set_dir.name] = trace_names
    
    return trace_sets


def compute_median_stats(times: np.ndarray) -> tuple:
    """Compute median, Q1, Q3 for given times."""
    if len(times) == 0:
        return (np.nan, np.nan, np.nan)
    median = np.median(times)
    q1 = np.percentile(times, 25)
    q3 = np.percentile(times, 75)
    return (median, q1, q3)


def compute_min_stats(times: np.ndarray) -> tuple:
    """Compute minimum, lower bound (min), upper bound (median) for given times."""
    if len(times) == 0:
        return (np.nan, np.nan, np.nan)
    minimum = np.min(times)
    median = np.median(times)
    return (minimum, minimum, median)


def collect_data_from_trace_set(variant: str, trace_set: str, use_min: bool = False) -> dict:
    """
    Collect median or min data for all algorithms from single trace set.
    Returns dict: {algo: {trace_name: (stats, lower, upper)}}
    """
    trace_names = get_trace_names_from_robinson(variant, trace_set)
    print(f"Found {len(trace_names)} traces in {variant}/{trace_set}")
    
    data = {algo: {} for algo in [ROBINSON] + TARGET_ALGOS}
    
    for trace in trace_names:
        for algo in [ROBINSON] + TARGET_ALGOS:
            times = load_times(variant, algo, trace_set, trace)
            if len(times) == 0:
                continue
            if use_min:
                stats, lower, upper = compute_min_stats(times)
            else:
                stats, lower, upper = compute_median_stats(times)
            data[algo][trace] = (stats, lower, upper)
    
    return data


def collect_data(variant: str, use_min: bool = False) -> dict:
    """
    Collect median or min data for all algorithms from all trace sets.
    Returns dict: {algo: {trace_name: (stats, lower, upper)}}
    """
    trace_sets = collect_all_trace_names(variant)
    print(f"Found {len(trace_sets)} trace sets for {variant}: {list(trace_sets.keys())}")
    
    data = {algo: {} for algo in [ROBINSON] + TARGET_ALGOS}
    
    total_traces = 0
    for trace_set, trace_names in trace_sets.items():
        for trace in trace_names:
            for algo in [ROBINSON] + TARGET_ALGOS:
                times = load_times(variant, algo, trace_set, trace)
                if len(times) == 0:
                    continue
                if use_min:
                    stats, lower, upper = compute_min_stats(times)
                else:
                    stats, lower, upper = compute_median_stats(times)
                data[algo][trace] = (stats, lower, upper)
        total_traces += len(trace_names)
    
    print(f"Total traces (from all trace sets): {total_traces}")
    
    return data


def filter_common_traces(data: dict) -> dict:
    """
    Keep only traces that exist in both Robinson and at least one target algorithm.
    Returns dict: {algo: {common_trace: stats}}
    """
    robinson_traces = set(data[ROBINSON].keys())
    if not robinson_traces:
        raise ValueError("No traces found for Robinson")
    
    common = {}
    for algo in TARGET_ALGOS:
        if algo not in data or not data[algo]:
            print(f"Warning: no data for {algo}, skipping")
            continue
        algo_traces = set(data[algo].keys())
        common_traces = robinson_traces & algo_traces
        if not common_traces:
            print(f"Warning: no common traces between {ROBINSON} and {algo}")
            continue
        common[algo] = {
            trace: data[ROBINSON][trace] + data[algo][trace]
            for trace in common_traces
        }
        print(f"{algo}: {len(common_traces)} common traces")
    
    return common


def build_regression_dataset(common_traces: dict) -> dict:
    """
    Build regression dataset for each target algorithm.
    Returns: {algo: {'x': robinson_medians, 'y': algo_medians, 'x_err': ..., 'y_err': ...}}
    """
    datasets = {}
    for algo, traces_data in common_traces.items():
        x_vals = []
        y_vals = []
        x_lower = []
        x_upper = []
        y_lower = []
        y_upper = []
        
        for trace, stats_tuple in traces_data.items():
            rob_med, rob_q1, rob_q3 = stats_tuple[:3]
            algo_med, algo_q1, algo_q3 = stats_tuple[3:]
            
            x_vals.append(rob_med)
            y_vals.append(algo_med)
            x_lower.append(rob_med - rob_q1)
            x_upper.append(rob_q3 - rob_med)
            y_lower.append(algo_med - algo_q1)
            y_upper.append(algo_q3 - algo_med)
        
        datasets[algo] = {
            'x': np.array(x_vals),
            'y': np.array(y_vals),
            'x_err_lower': np.array(x_lower),
            'x_err_upper': np.array(x_upper),
            'y_err_lower': np.array(y_lower),
            'y_err_upper': np.array(y_upper),
        }
    
    return datasets


def perform_regression(x: np.ndarray, y: np.ndarray) -> dict:
    """Perform linear regression and return results."""
    result = stats.linregress(x, y)
    return {
        'slope': result.slope,
        'intercept': result.intercept,
        'rvalue': result.rvalue,
        'pvalue': result.pvalue,
        'stderr': result.stderr,
    }


def plot_results(datasets: dict, variant: str, output_file: str = None, show_errorbars: bool = True):
    """Create scatter plot with regression lines."""
    fig, ax = plt.subplots(figsize=(12, 10))
    
    all_x = []
    all_y = []
    
    for algo, data in datasets.items():
        x = data['x']
        y = data['y']
        all_x.extend(x)
        all_y.extend(y)
        
        color = COLORS.get(algo, 'gray')
        
        xerr = [data['x_err_lower'], data['x_err_upper']] if show_errorbars else None
        yerr = [data['y_err_lower'], data['y_err_upper']] if show_errorbars else None
        
        ax.errorbar(
            x, y,
            xerr=xerr,
            yerr=yerr,
            fmt='o', capsize=3, markersize=6,
            label=algo, color=color, alpha=0.7, elinewidth=1
        )
        
        regression = perform_regression(x, y)
        x_range = np.linspace(min(x) * 0.9, max(x) * 1.1, 100)
        y_pred = regression['intercept'] + regression['slope'] * x_range
        ax.plot(x_range, y_pred, '--', color=color, alpha=0.8, label=f'{algo} fit')
    
    if all_x and all_y:
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        x_min_adj = x_min / 1.1
        x_max_adj = x_max * 1.1
        y_min_adj = y_min / 1.1
        y_max_adj = y_max * 1.1
        ax.set_xlim(x_min_adj, x_max_adj)
        ax.set_ylim(y_min_adj, y_max_adj)
    
    ax.set_xlabel(f'Median time (ns) - {ROBINSON}', fontsize=12)
    ax.set_ylabel('Median time (ns) - target algorithm', fontsize=12)
    ax.set_title(f'Algorithm performance vs Robinson\n{variant} (all trace sets)', fontsize=14)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='upper left', fontsize=10)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.show()


def print_regression_stats(datasets: dict):
    """Print regression statistics to terminal."""
    print("\n" + "=" * 60)
    print("LINEAR REGRESSION STATISTICS")
    print("=" * 60)
    print(f"{'Algorithm':<12} {'Slope':>12} {'Intercept':>12} {'R-value':>12} {'P-value':>12} {'StdErr':>12}")
    print("-" * 74)
    
    for algo, data in datasets.items():
        stats = perform_regression(data['x'], data['y'])
        print(f"{algo:<12} {stats['slope']:>12.6f} {stats['intercept']:>12.6f} "
              f"{stats['rvalue']:>12.6f} {stats['pvalue']:>12.6e} {stats['stderr']:>12.6f}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Build scatter plot with linear regression comparing algorithm performance to Robinson.'
    )
    parser.add_argument('variant', type=str, help='Variant name (subdirectory under samples/)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output image file (e.g., plot.png). If not given, displays interactively.')
    parser.add_argument('--no-errorbars', dest='errorbars', action='store_false', default=True,
                        help='Disable errorbars (whiskers) on the plot.')
    parser.add_argument('--use-min', dest='use_min', action='store_true', default=False,
                        help='Use minimum instead of median for statistics.')
    args = parser.parse_args()
    
    try:
        data = collect_data(args.variant, args.use_min)
        common_traces = filter_common_traces(data)
        
        if not common_traces:
            print("Error: no common traces found between Robinson and target algorithms")
            sys.exit(1)
        
        datasets = build_regression_dataset(common_traces)
        
        print_regression_stats(datasets)
        plot_results(datasets, args.variant, args.output, args.errorbars)
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
