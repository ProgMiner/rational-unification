## rational-unification/bench

This directory contains practical implementations of the algorithm and two more algorithms:
the Robinson's algorithm and the Huet's algorithm. These algorithms are implemented in several flavors:
ephemeral, ephemeral with path compression and persistent.

Also, there are traces collected from real-world relational programs and synthetic ones.
For them, there are samples collected from the algorithms runs on the traces.

The synthetic traces could be recreated using the corresponding scripts inside the directory `traces/synth`.
There are also some clarifying comments for them. They are not require any dependencies to run.

Traces could be studied manually using the script `./trace.py`:
```bash
./trace.py --print ./traces/JGS/TESTIV/18.trace
```

The samples are collected using the script on a clean Linux-based system,
this requires the project to be built (see README in the root of the repo):
```bash
./collect.sh
```

To use the scripts inside this directory you need several Python dependencies.
You may use a virtual environment to obtain them:
```bash
python -m venv venv
. ./venv/bin/activate
pip install -r requirements.txt
```

There are also reports of statistical tests inside the directory `reports` and plots inside the directory `plots`.
They could be recreated from samples using:
```bash
./make_analyse.sh
./make_plots.sh
```

Some scripts in this repo wasn't used in the paper but could be interesting to look.
