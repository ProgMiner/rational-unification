#!/usr/bin/env sh


mkdir -p ./plots

# Ephemeral

mkdir -p ./plots/ephemeral

./plot_robinson_vs_others.py ephemeral
mv ./robinson_comparison_ephemeral_all_trace_sets.png ./plots/ephemeral/robinson_comparison.png

./plot_bars.py ephemeral synth/full -o ./plots/ephemeral/synth_full.png --ymax 44000
./plot_bars.py ephemeral synth/left_right -o ./plots/ephemeral/synth_left_right.png --ymax 44000
for ((i = 1; i <= 4; ++i)); do ./plot_bars.py ephemeral synth/loops$i -o ./plots/ephemeral/synth_loops${i}.png --ymax 17000 ; done

./plot_bars_no_robinson.py ephemeral Lama -o plots/ephemeral/Lama.png

# Ephemeral path compression

mkdir -p ./plots/ephemeral_path_comp

./plot_robinson_vs_others.py ephemeral_path_comp
mv ./robinson_comparison_ephemeral_path_comp_all_trace_sets.png ./plots/ephemeral_path_comp/robinson_comparison.png

./plot_bars.py ephemeral_path_comp synth/full -o ./plots/ephemeral_path_comp/synth_full.png --ymax 44000
./plot_bars.py ephemeral_path_comp synth/left_right -o ./plots/ephemeral_path_comp/synth_left_right.png --ymax 44000
for ((i = 1; i <= 4; ++i)); do ./plot_bars.py ephemeral_path_comp synth/loops$i -o ./plots/ephemeral_path_comp/synth_loops${i}.png --ymax 17000 ; done

./plot_bars_no_robinson.py ephemeral_path_comp Lama -o ./plots/ephemeral_path_comp/Lama.png

# Persistent

mkdir -p ./plots/persistent

./plot_robinson_vs_others.py persistent
mv ./robinson_comparison_persistent_all_trace_sets.png ./plots/persistent/robinson_comparison.png

./plot_bars.py persistent synth/full -o plots/persistent/synth_full.png --ymax 370000
./plot_bars.py persistent synth/left_right -o plots/persistent/synth_left_right.png --ymax 370000
for ((i=1;i<=4;++i)); do ./plot_bars.py persistent synth/loops$i -o plots/persistent/synth_loops${i}.png --ymax 88000 ; done

./plot_bars_no_robinson.py persistent Lama -o ./plots/persistent/Lama.png
