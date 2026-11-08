#!/usr/bin/env python3
"""
Script to generate a grouped bar chart for multiple algorithms across different traces.
Only includes traces that do NOT have a robinson run.
Each trace shows two columns: rational, huet (in this order).

Usage:
    ./plot_bars_no_robinson.py <variant> <trace_set> [--output OUTPUT]

Example:
    ./plot_bars_no_robinson.py my_variant my_traces --output plot.png
"""

import sys
import argparse
import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
from pathlib import Path

TRACES_DIR = Path('./traces')
SAMPLES_DIR = Path('./samples')
ALGOS = ['robinson', 'rational', 'huet']
COLORS = ['green', 'blue', 'red']


def get_all_trace_names(trace_set: str) -> list:
    traces_path = TRACES_DIR / trace_set
    if not traces_path.exists():
        raise FileNotFoundError(f"Traces directory not found: {traces_path}")

    trace_files = list(traces_path.rglob('*.trace'))
    if not trace_files:
        raise FileNotFoundError(f"No .trace files found in {traces_path}")

    trace_names = []
    for tf in trace_files:
        rel_path = tf.relative_to(traces_path)
        trace_name = str(rel_path).replace('.trace', '')
        trace_names.append(trace_name)

    def natural_sort_key(name: str) -> tuple:
        parts = re.findall(r'(\d+|\D+)', name)
        return tuple(int(p) if p.isdigit() else p.lower() for p in parts)

    return sorted(trace_names, key=natural_sort_key)


def load_times(variant: str, trace_set: str, trace_name: str, algo: str) -> np.ndarray:
    file_path = SAMPLES_DIR / variant / algo / trace_set / f"{trace_name}.tsv"
    if not file_path.exists():
        return np.array([])

    df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
    times = df['time'].dropna().values
    return times


def has_run(variant: str, trace_set: str, trace_name: str, algo: str) -> bool:
    file_path = SAMPLES_DIR / variant / algo / trace_set / f"{trace_name}.tsv"
    return file_path.exists()


def compute_median(times: np.ndarray) -> float:
    if len(times) == 0:
        return float('nan')
    return float(np.median(times))


def plot_bars(variant: str, trace_set: str, output_file: str = None, ymax: float = None):
    trace_names = get_all_trace_names(trace_set)
    print(f"Found {len(trace_names)} traces")

    filtered_traces = []
    for trace in trace_names:
        if not has_run(variant, trace_set, trace, 'robinson'):
            filtered_traces.append(trace)

    print(f"Traces without robinson run: {len(filtered_traces)}")
    if len(filtered_traces) == 0:
        print("No traces found without robinson run. Exiting.")
        return

    algorithms = ['rational', 'huet']
    algo_to_color = {'robinson': 'green', 'rational': 'blue', 'huet': 'red'}

    data = {trace: {} for trace in filtered_traces}
    has_any_data = False

    for trace in filtered_traces:
        for algo in algorithms:
            times = load_times(variant, trace_set, trace, algo)
            if len(times) == 0:
                continue
            has_any_data = True
            median = compute_median(times)
            data[trace][algo] = median

    if not has_any_data:
        print("No data found for any algorithm. Exiting.")
        return

    x = np.arange(len(filtered_traces))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(10, len(filtered_traces) * 0.5), 6))

    algorithms_with_data = []
    for i, algo in enumerate(algorithms):
        medians = []
        for trace in filtered_traces:
            if algo in data[trace]:
                med_val = data[trace][algo]
                if not np.isnan(med_val):
                    medians.append(med_val)
                else:
                    medians.append(np.nan)
            else:
                medians.append(np.nan)

        valid_minimums = [m for m in medians if m is not None and not np.isnan(m)]
        if len(valid_minimums) > 0:
            algorithms_with_data.append(algo)
            ax.bar(x + i * width, medians, width, label=algo, color=algo_to_color[algo], alpha=0.8)

    if len(algorithms_with_data) == 0:
        print("No valid data for any algorithm. Exiting.")
        return

    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(filtered_traces, rotation=45, ha='right', fontsize=7)

    ax.set_xlabel('Trace')
    ax.set_ylabel('Time (ns)')

    ax.legend()
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)

    plt.tight_layout()

    ylim = ax.get_ylim()
    if ymax is not None:
        ylim = (ylim[0], ymax)
        ax.set_ylim(top=ymax)

    print(f"Viewport boundaries: y_min={ylim[0]:.6f}, y_max={ylim[1]:.6f}")

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Generate grouped bar chart for algorithm comparison (excludes traces with robinson).'
    )
    parser.add_argument('variant', type=str,
                        help='Variant name (subdirectory under samples/)')
    parser.add_argument('trace_set', type=str,
                        help='Trace set name (subdirectory under traces/ and under samples/*/*/)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output image file (e.g., plot.png). If not given, displays interactively.')
    parser.add_argument('--ymax', type=float, default=None,
                        help='Maximum Y value for the plot.')
    args = parser.parse_args()

    try:
        plot_bars(
            variant=args.variant,
            trace_set=args.trace_set,
            output_file=args.output,
            ymax=args.ymax
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
