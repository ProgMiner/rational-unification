#!/usr/bin/env sh

for var in ephemeral ephemeral_path_comp persistent; do
    for set in JGS Lama synth; do
        echo $var $set
        ./analyse.py $var $set >./reports/$var/$set.txt
    done

    echo $var all
    ./analyse.py $var . >./reports/$var/all.txt
done

./compare_ephemeral_variants.py rational . >reports/ephemeral-vs-ephemeral_path_comp/rational.txt
./compare_ephemeral_variants.py huet . >reports/ephemeral-vs-ephemeral_path_comp/huet.txt
