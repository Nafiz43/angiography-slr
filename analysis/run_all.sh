#!/bin/bash
# Rebuild the review's figures and tables from extraction/out/*.json. Run from the repo root.
set -e
fail=0
python3 extraction/v2_to_legacy.py results
mkdir -p analysis-results
cd analysis
for s in 01_topical_analysis.py 03_metric_plot.py 04_task-archi.py 07_claim_side_by_side_comparison.py 10_task_dendrogram.py 09_venn_diagram.py; do
  MPLBACKEND=Agg python3 "$s" > "../analysis-results/$s.log" 2>&1 && echo "ran $s" || { echo "FAILED $s"; tail -5 "../analysis-results/$s.log"; fail=1; }
done
python3 claim_fisher.py
exit $fail
