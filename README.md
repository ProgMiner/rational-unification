# rational-unification

Supplementary materials for the rational unification algorithm research.

This repository is organized as follows:

- `lib` — conceptual implementations of the algorithm in several variants:
  - `ephemeral` — a non-persistent (ephemeral) implementation
  - `persistent` — a persistent implementation
  - `disunify` — a persistent implementation with disunification support
  - `mixed` — a persistent implementation with both finite and rational term support
- `test` — some tests for `lib`
- `bench` — practical implementations of the algorithm and other benchmarking stuff
