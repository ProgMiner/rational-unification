#!/usr/bin/env python3
"""
Generate grouped bar charts comparing only `ephemeral/swi` and `swi_c`.

The two implementations use different sample roots:

    samples/ephemeral/swi/<trace_set>/<trace>.tsv
    samples/swi_c/swi/<trace_set>/<trace>.tsv

Therefore this script intentionally does not accept a `variant` argument:
the pair of implementations is fixed.

Usage:
    ./plot_bars_swi_vs_swi_c.py <trace_set> [--output OUTPUT]

Example:
    ./plot_bars_swi_vs_swi_c.py synth/full -o plots/swi_vs_swi_c/synth_full.png

The trace set is resolved under traces/<trace_set>; matching sample files are
read from the two fixed roots shown above.
"""

import sys
import argparse
import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
from pathlib import Path

TRACES_DIR = Path('./traces')
SAMPLES_ROOTS = {
    'swi': Path('./samples/ephemeral/swi'),
    'swi_c': Path('./samples/swi_c/swi'),
}
ALGOS = ['swi', 'swi_c']
COLORS = {'swi': 'red', 'swi_c': 'blue'}


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


def load_times(algo: str, trace_set: str, trace_name: str) -> np.ndarray:
    root = SAMPLES_ROOTS[algo]
    file_path = root / trace_set / f"{trace_name}.tsv"
    if not file_path.exists():
        return np.array([])

    df = pd.read_csv(file_path, sep='\t', header=None, names=['n', 'time'], index_col='n')
    times = df['time'].dropna().values
    return times


def compute_median(times: np.ndarray) -> float:
    if len(times) == 0:
        return float('nan')
    return float(np.median(times))


def plot_bars(trace_set: str, output_file: str = None, ymax: float = None):
    trace_names = get_all_trace_names(trace_set)
    print(f"Found {len(trace_names)} traces")
    if len(trace_names) == 0:
        print("No traces found. Exiting.")
        return

    data = {trace: {} for trace in trace_names}
    has_any_data = False

    for trace in trace_names:
        for algo in ALGOS:
            times = load_times(algo, trace_set, trace)
            if len(times) == 0:
                continue
            has_any_data = True
            data[trace][algo] = compute_median(times)

    if not has_any_data:
        print("No data found for any algorithm. Exiting.")
        return

    filtered_traces = [
        trace for trace in trace_names
        if any(algo in data[trace] for algo in ALGOS)
    ]

    if len(filtered_traces) == 0:
        print("No traces with valid data. Exiting.")
        return

    x = np.arange(len(filtered_traces))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(10, len(filtered_traces) * 0.5), 6))

    for i, algo in enumerate(ALGOS):
        medians = []
        for trace in filtered_traces:
            med_val = data[trace].get(algo, np.nan)
            medians.append(med_val)

        valid_medians = [m for m in medians if not np.isnan(m)]
        if len(valid_medians) > 0:
            ax.bar(x + (i - 0.5) * width, medians, width,
                   label=algo, color=COLORS[algo], alpha=0.8)

    ax.set_xticks(x)
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
        description='Generate grouped bar chart for ephemeral/swi vs swi_c.'
    )
    parser.add_argument('trace_set', type=str,
                        help='Trace set name (subdirectory under traces/ and under samples/*/*/)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output image file (e.g., plot.png). If not given, displays interactively.')
    parser.add_argument('--ymax', type=float, default=None,
                        help='Maximum Y value for the plot.')
    args = parser.parse_args()

    try:
        plot_bars(
            trace_set=args.trace_set,
            output_file=args.output,
            ymax=args.ymax,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
