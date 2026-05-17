#!/usr/bin/env sh

for var in ephemeral ephemeral_path_comp persistent; do
    for set in JGS Lama synth; do
        echo $var $set
        mkdir -p "./reports/$var"
        ./analyse.py $var $set >"./reports/$var/$set.txt"
    done

    echo $var all
    mkdir -p "./reports/$var"
    ./analyse.py $var . >./reports/$var/all.txt
done

mkdir -p ./reports/ephemeral-vs-ephemeral_path_comp
for algo in robinson rational huet; do
    echo $algo
    ./compare_ephemeral_variants.py $algo . >"./reports/ephemeral-vs-ephemeral_path_comp/$algo.txt"
done
