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

## Build

Create an opam switch and activate it:
```bash
opam switch create ./ --empty
eval $(opam env)
```

Configure the switch using the script:
```bash
./configure-opam.sh
eval $(opam env) # yes, you need it again
```

This will install all necessary dependencies.

To build the project use:
```bash
dune b . --profile=release
```
