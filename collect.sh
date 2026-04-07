#!/usr/bin/env sh


TRACES_DIR='./traces'
SAMPLES_DIR='./samples'
ALGOS='
    ephemeral/robinson  ephemeral/rational  ephemeral/huet
    persistent/robinson persistent/rational persistent/huet
'

if [ $# -ne 0 ] ; then
    file=$1

    trace=${file%.trace}
    trace=${trace#"$TRACES_DIR/"}

    for algo in $ALGOS ; do
        printf '%s       \t%s                \r' "$trace" "$algo"

        dir="$SAMPLES_DIR/$algo/$trace.tsv"
        mkdir -p "$(dirname "$dir")"

        "./_build/default/bench/$algo.exe" --quiet "$1" >"$dir"
    done

    exit 0
fi

find "$TRACES_DIR" -name '*.trace' -type f -exec sh "$0" '{}' ';'
