#!/usr/bin/env python3
"""
Script to generate a scatter plot with error bars (whiskers) for multiple algorithms
across different traces. Uses the same trace naming convention as the original script:
traces are identified by their relative path inside the trace_set directory (without extension).
Traces are sorted by the minimum median time across algorithms.

Usage:
    ./plot_scatter.py <variant> <trace_set> [--output OUTPUT]

Example:
    ./plot_scatter.py my_variant my_traces --output plot.png
"""

import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Constants based on the original script structure
TRACES_DIR = Path('./traces')
SAMPLES_DIR = Path('./samples')
ALGOS = ['robinson', 'rational', 'huet']
COLORS = {
    'robinson': 'blue',
    'rational': 'green',
    'huet': 'red'
}


def get_all_trace_names(trace_set: str) -> list:
    """
    Scan TRACES_DIR/trace_set for all *.trace files recursively.
    Return a sorted list of trace identifiers (relative path from trace_set without extension).
    Example: if file is traces/my_set/subdir/foo.trace, returns "subdir/foo".
    """
    traces_path = TRACES_DIR / trace_set
    if not traces_path.exists():
        raise FileNotFoundError(f"Traces directory not found: {traces_path}")

    trace_files = list(traces_path.rglob('*.trace'))
    if not trace_files:
        raise FileNotFoundError(f"No .trace files found in {traces_path}")

    trace_names = []
    for tf in trace_files:
        rel_path = tf.relative_to(traces_path)
        # Remove the .trace extension
        trace_name = str(rel_path.with_suffix(''))
        trace_names.append(trace_name)

    return sorted(trace_names)


def load_times(variant: str, trace_set: str, trace_name: str, algo: str) -> np.ndarray:
    """
    Load the 'time' column from the TSV file for a given trace and algorithm.
    The TSV file is expected at:
        SAMPLES_DIR / variant / algo / trace_set / trace_name.tsv
    where trace_name may contain subdirectories.
    Returns a numpy array of time values (empty if file missing or no data).
    """
    file_path = SAMPLES_DIR / variant / algo / trace_set / f"{trace_name}.tsv"
    if not file_path.exists():
        return np.array([])

    df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
    times = df['time'].dropna().values
    return times


def compute_stats(times: np.ndarray) -> tuple:
    """
    Compute median and interquartile range (Q1, Q3) for the given times.
    Returns (median, lower_bound, upper_bound).
    Returns (NaN, NaN, NaN) if times is empty.
    """
    if len(times) == 0:
        return (np.nan, np.nan, np.nan)

    median = np.median(times)
    lower = np.percentile(times, 25)
    upper = np.percentile(times, 75)
    return (median, lower, upper)


def plot_scatter(variant: str, trace_set: str, output_file: str = None):
    """
    Main plotting function. Traces are sorted by the minimum median time across algorithms.
    """
    # Get all trace identifiers (with potential subdirectories)
    trace_names = get_all_trace_names(trace_set)
    print(f"Found {len(trace_names)} traces")
    if len(trace_names) == 0:
        print("No traces found. Exiting.")
        return

    # Prepare data: for each trace, for each algo, store (median, lower, upper)
    data = {trace: {} for trace in trace_names}
    has_any_data = False

    for trace in trace_names:
        for algo in ALGOS:
            times = load_times(variant, trace_set, trace, algo)
            if len(times) == 0:
                continue
            has_any_data = True
            median, lower, upper = compute_stats(times)
            data[trace][algo] = (median, lower, upper)

    if not has_any_data:
        print("No data found for any algorithm. Exiting.")
        return

    # Compute for each trace the minimum median across algorithms that have data
    trace_min_median = {}
    for trace in trace_names:
        medians = []
        for algo in ALGOS:
            if algo in data[trace]:
                med = data[trace][algo][0]  # median
                if not np.isnan(med):
                    medians.append(med)
        if medians:
            trace_min_median[trace] = min(medians)
        else:
            trace_min_median[trace] = np.inf  # traces with no data go to the end

    # Sort traces by the minimum median
    sorted_traces = sorted(trace_names, key=lambda t: trace_min_median[t])

    # Create plot
    fig, ax = plt.subplots(figsize=(max(10, len(sorted_traces) * 0.4), 6))

    # X positions: integer indices
    x_positions = range(len(sorted_traces))

    # For each algorithm, collect x, y, yerr_low, yerr_high
    for algo in ALGOS:
        x_vals = []
        y_vals = []
        yerr_lower = []
        yerr_upper = []

        for i, trace in enumerate(sorted_traces):
            if algo in data[trace]:
                median, lower, upper = data[trace][algo]
                x_vals.append(i)
                y_vals.append(median)
                yerr_lower.append(median - lower)
                yerr_upper.append(upper - median)

        if x_vals:
            ax.errorbar(
                x_vals, y_vals,
                yerr=[yerr_lower, yerr_upper],
                fmt='o', capsize=3, capthick=1, markersize=6,
                label=algo, color=COLORS.get(algo, 'gray'), alpha=0.8
            )

    # Set x-axis ticks and labels (the full trace name, may be long)
    ax.set_xticks(range(len(sorted_traces)))
    ax.set_xticklabels(sorted_traces, rotation=45, ha='right', fontsize=7)

    ax.set_xlabel('Trace (sorted by min median)')
    ax.set_ylabel('Time (seconds)')

    ax.set_title(f"Algorithm comparison on '{trace_set}' (variant: {variant})")
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend()

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Generate scatter plot with whiskers for algorithm comparison.'
    )
    parser.add_argument('variant', type=str,
                        help='Variant name (subdirectory under samples/)')
    parser.add_argument('trace_set', type=str,
                        help='Trace set name (subdirectory under traces/ and under samples/*/*/)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output image file (e.g., plot.png). If not given, displays interactively.')
    args = parser.parse_args()

    try:
        plot_scatter(
            variant=args.variant,
            trace_set=args.trace_set,
            output_file=args.output
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
