#!/usr/bin/env python3
"""
Grouped bar chart for `ephemeral/swi` vs `swi_c` with fitted approximation lines.

The bars are the same per-trace medians as in plot_bars_swi_vs_swi_c.py.  On top
of them this script draws two fitted growth models for each implementation:

    polynomial:      t(n) = C * n^p
    polynomial-exp:  t(n) = C * n^p * exp(k * n)

Both models are fitted by ordinary least squares on log(t) versus
(log n, n) using the same positive-n traces as the bars.  The fitted curves
are evaluated on a dense n grid and drawn as lines, so the reader can see
whether the bars actually follow a polynomial or an exponential law.

Usage:
    ./plot_fits_swi_vs_swi_c.py <trace_set> [--output OUTPUT]

Example:
    ./plot_fits_swi_vs_swi_c.py synth/left_right \
        -o plots/swi_vs_swi_c/synth_left_right_fits.png

Notes:
    - n=0 is excluded from the fits because log(0) is undefined and because
      its runtime is dominated by fixed startup overhead.
    - The y axis uses a linear scale, so the bars and the fitted curves are
      read directly in nanoseconds.
"""

import sys
import argparse
import numpy as np
import pandas as pd
import re
import matplotlib.pyplot as plt
from pathlib import Path

# Reuse the data-loading helpers from the existing fixed-pair bar plot script.
from plot_bars_swi_vs_swi_c import get_all_trace_names, load_times, compute_median

ALGOS = ['swi', 'swi_c']
COLORS = {'swi': 'red', 'swi_c': 'blue'}
LINESTYLES = {'poly': '--', 'poly_exp': '-'}


def parse_n(trace_name: str) -> int:
    m = re.search(r'(?:^|[_\-/])n(\d+)$', trace_name)
    if not m:
        raise ValueError(f"Cannot parse n from trace name {trace_name!r}")
    return int(m.group(1))


def fit_models(ns: np.ndarray, times: np.ndarray) -> dict:
    """Fit log t = a + p log n and log t = a + p log n + k n.

    n=0 is excluded.  Returns parameters in original time units via C=exp(a).
    """
    mask = ns > 0
    x = ns[mask].astype(float)
    y = np.log(times[mask])

    # Polynomial: log t = a + p log n
    X_poly = np.column_stack([np.ones_like(x), np.log(x)])
    beta_poly, _, _, _ = np.linalg.lstsq(X_poly, y, rcond=None)
    poly = {'C': float(np.exp(beta_poly[0])), 'p': float(beta_poly[1])}

    # Polynomial-exponential: log t = a + p log n + k n
    X_pexp = np.column_stack([np.ones_like(x), np.log(x), x])
    beta_pexp, _, _, _ = np.linalg.lstsq(X_pexp, y, rcond=None)
    pexp = {
        'C': float(np.exp(beta_pexp[0])),
        'p': float(beta_pexp[1]),
        'k': float(beta_pexp[2]),
    }
    return {'poly': poly, 'poly_exp': pexp}


def eval_poly(model: dict, n: np.ndarray) -> np.ndarray:
    return model['C'] * np.power(n, model['p'])


def eval_poly_exp(model: dict, n: np.ndarray) -> np.ndarray:
    return model['C'] * np.power(n, model['p']) * np.exp(model['k'] * n)


def plot_fits(trace_set: str, output_file: str = None):
    trace_names = get_all_trace_names(trace_set)
    print(f"Found {len(trace_names)} traces")
    if not trace_names:
        print("No traces found. Exiting.")
        return

    ns = np.array([parse_n(t) for t in trace_names], dtype=float)
    order = np.argsort(ns)
    ns = ns[order]
    trace_names = [trace_names[i] for i in order]

    medians = {algo: np.array([compute_median(load_times(algo, trace_set, t))
                               for t in trace_names], dtype=float)
               for algo in ALGOS}

    fits = {algo: fit_models(ns, medians[algo]) for algo in ALGOS}

    x = np.arange(len(trace_names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(12, len(trace_names) * 0.6), 7))

    for i, algo in enumerate(ALGOS):
        ax.bar(x + (i - 0.5) * width, medians[algo], width,
               label=algo, color=COLORS[algo], alpha=0.8)

    # Dense grid in index space so lines align with the categorical x axis.
    dense_idx = np.linspace(0, len(ns) - 1, 400)
    dense_n = np.interp(dense_idx, np.arange(len(ns)), ns)

    for algo in ALGOS:
        color = COLORS[algo]
        m = fits[algo]

        poly_vals = eval_poly(m['poly'], dense_n)
        ax.plot(dense_idx, poly_vals, color=color, linestyle=LINESTYLES['poly'],
                linewidth=1.8, alpha=0.9,
                label=f"{algo}: C*n^p (p={m['poly']['p']:.2f})")

        pexp_vals = eval_poly_exp(m['poly_exp'], dense_n)
        ax.plot(dense_idx, pexp_vals, color=color, linestyle=LINESTYLES['poly_exp'],
                linewidth=1.8, alpha=0.9,
                label=f"{algo}: C*n^p*e^(k n) (p={m['poly_exp']['p']:.2f}, k={m['poly_exp']['k']:.4f})")

    ax.set_xticks(x)
    ax.set_xticklabels(trace_names, rotation=45, ha='right', fontsize=7)
    ax.set_xlabel('Trace')
    ax.set_ylabel('Time (ns)')

    ax.legend(fontsize=8, loc='best')
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)

    plt.tight_layout()

    for algo in ALGOS:
        m = fits[algo]
        print(f"{algo}: poly C={m['poly']['C']:.3f} p={m['poly']['p']:.4f}; "
              f"poly-exp C={m['poly_exp']['C']:.3f} p={m['poly_exp']['p']:.4f} "
              f"k={m['poly_exp']['k']:+.5f}")

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Bar chart with fitted polynomial and polynomial-exponential lines.'
    )
    parser.add_argument('trace_set', type=str,
                        help='Trace set name (e.g. synth/left_right)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output image file. If not given, displays interactively.')
    args = parser.parse_args()

    try:
        plot_fits(trace_set=args.trace_set, output_file=args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
