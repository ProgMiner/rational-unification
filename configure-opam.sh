#!/bin/sh

set -e

opam switch set-invariant --packages 'ocaml-option-flambda,ocaml-variants=5.2.1+options'
opam install . --working-dir --deps-only --with-test
