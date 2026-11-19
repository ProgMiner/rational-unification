#!/usr/bin/env python3
"""
Check whether the difference between two implementations is asymptotically
constant on synthetic trace families.

Given two sample roots with the same layout

    <root>/<trace_set>/<trace_name>.tsv

the script compares median runtime per trace using two growth models:

  1. polynomial:      log t = a + p log n
  2. polynomial-exp:  log t = a + p log n + k n

The second model is useful for synthetic families whose runtime grows like
C * n^p * exp(k*n), for example when the produced rational term has a size
that grows with n.  The script reports both fits, bootstrap CIs for p and k,
and a conservative verdict.

A constant-factor difference between A and B requires matching growth in
both models: p_A ~= p_B and k_A ~= k_B.

Example:
    ./check_constant_factor.py \
        --a-root samples/ephemeral/swi \
        --b-root samples/swi_c/swi \
        --trace-set synth/full \
        --output full.txt
"""

import sys
import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BOOTSTRAP = 2000
DEFAULT_PERMUTATIONS = 10000
DEFAULT_SEED = 20261118


def natural_sort_key(name: str) -> tuple:
    parts = re.findall(r'(\d+|\D+)', name)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def load_trace_names(root: Path, trace_set: str) -> list:
    base = root / trace_set
    if not base.exists():
        raise FileNotFoundError(f"Trace sample directory not found: {base}")

    traces = []
    for p in base.rglob('*.tsv'):
        traces.append(str(p.relative_to(base).with_suffix('')))
    if not traces:
        raise FileNotFoundError(f"No .tsv sample files found in {base}")
    return sorted(traces, key=natural_sort_key)


def load_times(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"Sample file not found: {path}")

    df = pd.read_csv(path, sep='\t', header=None, names=['n', 'time'], index_col='n')
    return df['time'].dropna().to_numpy(dtype=float)


def median(values: np.ndarray) -> float:
    return float(np.median(values))


def slope(x: np.ndarray, y: np.ndarray) -> float:
    """OLS slope for already-transformed x and y."""
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    den = float(np.sum((x - x_mean) ** 2))
    if den == 0.0:
        raise ValueError("Cannot fit slope: all x values are identical")
    return float(np.sum((x - x_mean) * (y - y_mean)) / den)


def fit_polynomial(ns: np.ndarray, times: np.ndarray) -> dict:
    """Fit log t = a + p log n.

    n=0 is excluded because log(0) is undefined and because its runtime is
    dominated by fixed startup overhead rather than by the trace size.
    """
    mask = ns > 0
    x = np.log(ns[mask].astype(float))
    y = np.log(times[mask])
    p = slope(x, y)
    a = float(np.mean(y) - p * np.mean(x))
    pred = a + p * x
    rss = float(np.sum((y - pred) ** 2))
    return {'p': p, 'a': a, 'rss': rss}


def fit_polynomial_exponential(ns: np.ndarray, times: np.ndarray) -> dict:
    """Fit log t = a + p log n + k n by ordinary least squares.

    The model is linear in (a, p, k), so no nonlinear optimiser is needed.
    The number of positive-n points must exceed 3 for the residual variance
    to be defined.
    """
    mask = ns > 0
    x = ns[mask].astype(float)
    y = np.log(times[mask])
    design = np.column_stack([np.ones_like(x), np.log(x), x])
    if design.shape[0] <= design.shape[1]:
        raise ValueError("Need more than three positive n values for polynomial-exponential fit")
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    pred = design @ beta
    rss = float(np.sum((y - pred) ** 2))
    return {'a': float(beta[0]), 'p': float(beta[1]), 'k': float(beta[2]), 'rss': rss}


def aic(rss: float, n_points: int, n_params: int) -> float:
    """Gaussian AIC up to an additive constant."""
    return float(n_points * math.log(rss / n_points) + 2 * n_params)


def pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    den = math.sqrt(float(np.sum((x - x_mean) ** 2) * np.sum((y - y_mean) ** 2)))
    if den == 0.0:
        return 0.0
    return float(np.sum((x - x_mean) * (y - y_mean)) / den)


def permutation_pvalue(x: np.ndarray, y: np.ndarray, permutations: int,
                       rng: np.random.Generator) -> float:
    observed = abs(pearson_corr(x, y))
    count = 0
    for _ in range(permutations):
        if abs(pearson_corr(x, rng.permutation(y))) >= observed:
            count += 1
    return (count + 1) / (permutations + 1)


def parse_n_from_trace_name(trace_name: str) -> int:
    # Synthetic traces are expected to be named n0, n10, ..., or contain _n10.
    nums = re.findall(r'(?:^|[_\-/])n(\d+)$', trace_name)
    if len(nums) != 1:
        raise ValueError(
            f"Cannot parse n from trace name {trace_name!r}; "
            "expected names ending in n<number>"
        )
    return int(nums[0])


def analyze(a_root: Path, b_root: Path, trace_set: str,
            a_label: str, b_label: str, bootstrap: int,
            permutations: int, seed: int) -> dict:
    a_traces = load_trace_names(a_root, trace_set)
    b_traces = load_trace_names(b_root, trace_set)

    if a_traces != b_traces:
        only_a = sorted(set(a_traces) - set(b_traces))
        only_b = sorted(set(b_traces) - set(a_traces))
        raise ValueError(
            "Trace sets do not match between roots; "
            f"only in {a_label}: {only_a[:10]}, only in {b_label}: {only_b[:10]}"
        )

    ns = np.array([parse_n_from_trace_name(t) for t in a_traces], dtype=int)
    order = np.argsort(ns)
    ns = ns[order]
    traces = [a_traces[i] for i in order]

    a_samples = []
    b_samples = []
    for trace in traces:
        a_path = a_root / trace_set / f"{trace}.tsv"
        b_path = b_root / trace_set / f"{trace}.tsv"
        a_samples.append(load_times(a_path))
        b_samples.append(load_times(b_path))

    a_med = np.array([median(v) for v in a_samples], dtype=float)
    b_med = np.array([median(v) for v in b_samples], dtype=float)
    ratios = a_med / b_med

    poly_a = fit_polynomial(ns, a_med)
    poly_b = fit_polynomial(ns, b_med)
    pexp_a = fit_polynomial_exponential(ns, a_med)
    pexp_b = fit_polynomial_exponential(ns, b_med)

    p_diff = poly_a['p'] - poly_b['p']
    k_diff = pexp_a['k'] - pexp_b['k']

    rng = np.random.default_rng(seed)

    boot_p_diffs = []
    boot_k_diffs = []
    boot_k_a = []
    boot_k_b = []
    for _ in range(bootstrap):
        # Resample each trace's samples independently with replacement.
        ba = np.array([median(rng.choice(v, len(v), replace=True)) for v in a_samples])
        bb = np.array([median(rng.choice(v, len(v), replace=True)) for v in b_samples])
        boot_p_diffs.append(fit_polynomial(ns, ba)['p'] - fit_polynomial(ns, bb)['p'])
        ka = fit_polynomial_exponential(ns, ba)['k']
        kb = fit_polynomial_exponential(ns, bb)['k']
        boot_k_a.append(ka)
        boot_k_b.append(kb)
        boot_k_diffs.append(ka - kb)
    p_ci_low, p_ci_high = np.percentile(boot_p_diffs, [2.5, 97.5])
    k_ci_low, k_ci_high = np.percentile(boot_k_diffs, [2.5, 97.5])
    k_a_ci_low, k_a_ci_high = np.percentile(boot_k_a, [2.5, 97.5])
    k_b_ci_low, k_b_ci_high = np.percentile(boot_k_b, [2.5, 97.5])

    positive = ns > 0
    x = np.log(ns[positive].astype(float))
    y = np.log(ratios[positive])
    corr = pearson_corr(x, y)
    pvalue = permutation_pvalue(x, y, permutations, rng)

    n_pos = int(np.count_nonzero(positive))
    aic_poly_a = aic(poly_a['rss'], n_pos, 2)
    aic_poly_b = aic(poly_b['rss'], n_pos, 2)
    aic_pexp_a = aic(pexp_a['rss'], n_pos, 3)
    aic_pexp_b = aic(pexp_b['rss'], n_pos, 3)

    # Verdict combines the polynomial exponent gap, the exponential rate gap
    # and the permutation test on the raw ratio trend.
    #
    # A tiny but statistically significant k is not asymptotically meaningful:
    # over the observed range it changes the fitted time by exp(k * n_range).
    # We therefore require that the exponential factor actually moves by a
    # noticeable amount before treating the growth as exponential.
    n_range = float(ns[positive].max() - ns[positive].min())
    # Materiality is judged by the total effect of the exponential term over
    # the observed n range: exp(k * n_range).  A factor below 1.5 is treated
    # as noise-level for this benchmark range.
    k_material_factor = 1.5
    k_a_sig = not (k_a_ci_low <= 0.0 <= k_a_ci_high)
    k_b_sig = not (k_b_ci_low <= 0.0 <= k_b_ci_high)
    k_diff_sig = not (k_ci_low <= 0.0 <= k_ci_high)
    p_diff_sig = not (p_ci_low <= 0.0 <= p_ci_high)
    k_a_material = math.exp(abs(pexp_a['k']) * n_range) >= k_material_factor
    k_b_material = math.exp(abs(pexp_b['k']) * n_range) >= k_material_factor
    k_diff_material = math.exp(abs(k_diff) * n_range) >= k_material_factor

    if k_a_sig and k_b_sig and k_diff_sig and k_diff_material:
        verdict = 'DIFFERENT_EXPONENTIAL_GROWTH'
        explanation = (
            f"Both implementations show a significant exponential component, "
            f"but k_{a_label} and k_{b_label} differ materially by {k_diff:+.5f} "
            f"(95% CI [{k_ci_low:+.5f}, {k_ci_high:+.5f}])."
        )
    elif k_a_sig and k_b_sig and not k_diff_sig and (k_a_material or k_b_material):
        verdict = 'SAME_EXPONENTIAL_RATE'
        explanation = (
            f"Both implementations grow like C*n^p*exp(k*n) with statistically "
            f"indistinguishable k (gap {k_diff:+.5f}, 95% CI "
            f"[{k_ci_low:+.5f}, {k_ci_high:+.5f}])."
        )
    elif pvalue < 0.05 and p_diff_sig and abs(p_diff) >= 0.10:
        verdict = 'NOT_CONSTANT'
        explanation = (
            'Statistically significant ratio trend with a practically '
            'meaningful polynomial exponent gap (|p_A - p_B| >= 0.10).'
        )
    elif pvalue < 0.05 and p_diff_sig:
        verdict = 'ALMOST_CONSTANT'
        explanation = (
            'Statistically detectable trend, but polynomial exponent gap is '
            'small (|p_A - p_B| < 0.10).'
        )
    else:
        verdict = 'CONSTANT_LIKE'
        explanation = (
            'No statistically detectable trend in log(ratio) versus log(n); '
            'both polynomial and exponential rate gaps are small or insignificant.'
        )

    return {
        'a_label': a_label,
        'b_label': b_label,
        'a_root': str(a_root),
        'b_root': str(b_root),
        'trace_set': trace_set,
        'seed': seed,
        'bootstrap': bootstrap,
        'permutations': permutations,
        'traces': traces,
        'ns': ns.tolist(),
        f'{a_label}_median_ns': a_med.tolist(),
        f'{b_label}_median_ns': b_med.tolist(),
        'ratio_medians': ratios.tolist(),
        'poly': {
            a_label: poly_a,
            b_label: poly_b,
            'p_difference': p_diff,
            'p_ci_low': float(p_ci_low),
            'p_ci_high': float(p_ci_high),
            'aic': {a_label: aic_poly_a, b_label: aic_poly_b},
        },
        'poly_exp': {
            a_label: pexp_a,
            b_label: pexp_b,
            'k_difference': k_diff,
            'k_ci_low': float(k_ci_low),
            'k_ci_high': float(k_ci_high),
            f'k_{a_label}_ci_low': float(k_a_ci_low),
            f'k_{a_label}_ci_high': float(k_a_ci_high),
            f'k_{b_label}_ci_low': float(k_b_ci_low),
            f'k_{b_label}_ci_high': float(k_b_ci_high),
            'aic': {a_label: aic_pexp_a, b_label: aic_pexp_b},
        },
        'ratio_log_corr': corr,
        'permutation_pvalue': pvalue,
        'verdict': verdict,
        'explanation': explanation,
    }


def format_report(result: dict) -> str:
    a_label = result['a_label']
    b_label = result['b_label']
    lines = []
    lines.append('=== Constant-factor check ===')
    lines.append(f"Implementations: {a_label} vs {b_label}")
    lines.append(f"Trace set: {result['trace_set']}")
    lines.append(f"A root: {result['a_root']}")
    lines.append(f"B root: {result['b_root']}")
    lines.append('')
    lines.append(f"{'n':>6}  {'A ns':>12}  {'B ns':>12}  {'A/B':>8}")
    ratios = result['ratio_medians']
    a_vals = result[f'{a_label}_median_ns']
    b_vals = result[f'{b_label}_median_ns']
    for n, av, bv, r in zip(result['ns'], a_vals, b_vals, ratios):
        lines.append(f"{n:>6}  {av:>12.1f}  {bv:>12.1f}  {r:>8.2f}")

    lines.append('')
    lines.append('=== Polynomial fit (n > 0): log t = a + p log n ===')
    poly = result['poly']
    lines.append(f"p_{a_label}: {poly[a_label]['p']:+.4f}")
    lines.append(f"p_{b_label}: {poly[b_label]['p']:+.4f}")
    lines.append(f"p_{a_label} - p_{b_label}: {poly['p_difference']:+.4f}")
    lines.append(
        f"95% bootstrap CI for p gap: "
        f"[{poly['p_ci_low']:+.4f}, {poly['p_ci_high']:+.4f}]"
    )
    lines.append(
        f"AIC (poly): {a_label}={poly['aic'][a_label]:.2f}, "
        f"{b_label}={poly['aic'][b_label]:.2f}"
    )

    lines.append('')
    lines.append('=== Polynomial-exponential fit (n > 0): log t = a + p log n + k n ===')
    pexp = result['poly_exp']
    lines.append(
        f"p_{a_label}: {pexp[a_label]['p']:+.4f}; "
        f"k_{a_label}: {pexp[a_label]['k']:+.5f}"
    )
    lines.append(
        f"p_{b_label}: {pexp[b_label]['p']:+.4f}; "
        f"k_{b_label}: {pexp[b_label]['k']:+.5f}"
    )
    lines.append(f"k_{a_label} - k_{b_label}: {pexp['k_difference']:+.5f}")
    lines.append(
        f"95% bootstrap CI for k gap: "
        f"[{pexp['k_ci_low']:+.5f}, {pexp['k_ci_high']:+.5f}]"
    )
    lines.append(
        f"95% CI k_{a_label}: "
        f"[{pexp[f'k_{a_label}_ci_low']:+.5f}, "
        f"{pexp[f'k_{a_label}_ci_high']:+.5f}]"
    )
    lines.append(
        f"95% CI k_{b_label}: "
        f"[{pexp[f'k_{b_label}_ci_low']:+.5f}, "
        f"{pexp[f'k_{b_label}_ci_high']:+.5f}]"
    )
    lines.append(
        f"AIC (poly-exp): {a_label}={pexp['aic'][a_label]:.2f}, "
        f"{b_label}={pexp['aic'][b_label]:.2f}"
    )

    lines.append('')
    lines.append('=== Ratio trend ===')
    lines.append(f"corr(log(A/B), log(n)): {result['ratio_log_corr']:+.4f}")
    lines.append(f"permutation p-value: {result['permutation_pvalue']:.4f}")

    lines.append('')
    lines.append('=== Verdict ===')
    lines.append(result['verdict'])
    lines.append(result['explanation'])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
        description='Check whether two implementations differ by a constant factor.'
    )
    parser.add_argument('--a-root', required=True,
                        help='Sample root for implementation A (e.g. samples/ephemeral/swi)')
    parser.add_argument('--b-root', required=True,
                        help='Sample root for implementation B (e.g. samples/swi_c/swi)')
    parser.add_argument('--a-label', default='A',
                        help='Short label for implementation A (default: A)')
    parser.add_argument('--b-label', default='B',
                        help='Short label for implementation B (default: B)')
    parser.add_argument('--trace-set', required=True,
                        help='Trace set under each root (e.g. synth/full)')
    parser.add_argument('--bootstrap', type=int, default=DEFAULT_BOOTSTRAP,
                        help=f'Bootstrap iterations (default: {DEFAULT_BOOTSTRAP})')
    parser.add_argument('--permutations', type=int, default=DEFAULT_PERMUTATIONS,
                        help=f'Permutation iterations (default: {DEFAULT_PERMUTATIONS})')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED,
                        help=f'RNG seed (default: {DEFAULT_SEED})')
    parser.add_argument('--output', '-o',
                        help='Write text report to this file; stdout otherwise')
    parser.add_argument('--json',
                        help='Write machine-readable result to this JSON file')
    args = parser.parse_args()

    try:
        result = analyze(
            a_root=Path(args.a_root),
            b_root=Path(args.b_root),
            trace_set=args.trace_set,
            a_label=args.a_label,
            b_label=args.b_label,
            bootstrap=args.bootstrap,
            permutations=args.permutations,
            seed=args.seed,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    report = format_report(result)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(result, indent=2) + '\n')
        print(f"JSON saved to {args.json}")


if __name__ == '__main__':
    main()
