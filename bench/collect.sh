#!/usr/bin/env sh

# This script is intended to run by root

# change this if you have no realtime scheduling support
CHRT=true # false

# CPU number to run on
CPU=4


TRACES_DIR='./traces'
SAMPLES_DIR='./samples'
ALGOS='robinson rational huet swi'
VARIANTS='ephemeral ephemeral_path_comp persistent'

if ! "$CHRT"; then
    chrt() {
        shift
        shift
        exec "$@"
    }
fi

do_run() {
    printf '%s       \t%s                \r' "$trace" "$3"

    res="$SAMPLES_DIR/$3/$trace.tsv"
    mkdir -p "$(dirname "$res")"

    ./fix_affinity.py "$2" "$CPU"

    ulimit -r unlimited

    chrt -f 99 "$4" --cpu "$CPU" --quiet "$1" >"$res" || {
        printf '%s       \t%s\terror\n' "$trace" "$3"
        rm "$res"
    }
}

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
            do_run "$1" "$2" "$var_algo" "../_build/default/bench/impl/$var_algo.exe"
        done
    done

    do_run "$1" "$2" 'swi_c/swi' './impl/swi_c/swi'

    exit 0
fi

renice -20 -p $$

find "$TRACES_DIR" -name '*.trace' -type f -exec sh "$0" '{}' "$$" ';'
