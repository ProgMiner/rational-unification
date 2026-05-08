#!/usr/bin/env sh

# This script is intended to run by root

# change this if you have no realtime scheduling support
CHRT=true # false

# CPU number to run on
CPU=4


TRACES_DIR='./traces'
SAMPLES_DIR='./samples'
ALGOS='robinson rational huet'
VARIANTS='ephemeral ephemeral_path_comp persistent'

if ! "$CHRT"; then
    chrt() {
        shift
        shift
        exec "$@"
    }
fi

if [ $# -ne 0 ] ; then
    file=$1

    trace=${file%.trace}
    trace=${trace#"$TRACES_DIR/"}

    for var in $VARIANTS ; do
        for algo in $ALGOS ; do
            if [ "$algo" = robinson ] && echo "$trace" | grep -q synth ; then
                continue
            fi

            var_algo="$var/$algo"

            printf '%s       \t%s                \r' "$trace" "$var_algo"

            res="$SAMPLES_DIR/$var_algo/$trace.tsv"
            mkdir -p "$(dirname "$res")"

            ./fix_affinity.py "$2" "$CPU"

            ulimit -r unlimited

            chrt -f 99 "../_build/default/bench/impl/$var_algo.exe" --cpu "$CPU" --quiet "$1" >"$res" || {
                printf '%s       \t%s\terror\n' "$trace" "$var_algo"
                rm "$res"
            }
        done
    done

    exit 0
fi

renice -20 -p $$

find "$TRACES_DIR" -name '*.trace' -type f -exec sh "$0" '{}' "$$" ';'
