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
for algo in robinson rational huet swi; do
    echo $algo
    ./compare_ephemeral_variants.py $algo . >"./reports/ephemeral-vs-ephemeral_path_comp/$algo.txt"
done

mkdir -p ./reports/swi_vs_swi_c
for set in full left_right loops1 loops2 loops3 loops4; do
    echo "swi vs swi_c: $set"
    ./check_constant_factor.py \
        --a-root samples/ephemeral/swi --a-label swi \
        --b-root samples/swi_c/swi --b-label swi_c \
        --trace-set "synth/$set" \
        --output "./reports/swi_vs_swi_c/$set.txt" \
        --json "./reports/swi_vs_swi_c/$set.json"
done
