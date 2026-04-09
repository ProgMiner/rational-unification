#!/usr/bin/env sh


TRACES_DIR='./traces'
SAMPLES_DIR='./samples'
ALGOS='robinson rational huet'
VARIANTS='ephemeral ephemeral_path_comp persistent'

if [ $# -ne 0 ] ; then
    file=$1

    trace=${file%.trace}
    trace=${trace#"$TRACES_DIR/"}

    for var in $VARIANTS ; do
        for algo in $ALGOS ; do
            var_algo="$var/$algo"

            printf '%s       \t%s                \r' "$trace" "$var_algo"

            res="$SAMPLES_DIR/$var_algo/$trace.tsv"
            mkdir -p "$(dirname "$res")"

            "../_build/default/bench/impl/$var_algo.exe" --quiet "$1" >"$res" || {
                printf '%s       \t%s\terror\n' "$trace" "$var_algo"
                rm "$res"
            }
        done
    done

    exit 0
fi

find "$TRACES_DIR" -name '*.trace' -type f -exec sh "$0" '{}' ';'
