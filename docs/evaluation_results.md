# WorkSync AI detection evaluation

Ground truth: `C:\Users\konda\OneDrive\Documents\deepseek-harness\default-workspace\WorkSyncAI\ground_truth\ground_truth.csv`  
The runtime detector was executed against the operational database **without reading** this file.

## Overall (five required anomaly types)

| Metric | Value |
|---|---:|
| True positives | 34 |
| False positives | 0 |
| False negatives | 0 |
| Precision | 100.00% |
| Recall | 100.00% |
| F1 | 100.00% |

## Per anomaly type

| Issue type | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| DOUBLE_BOOKING | 6 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| LEAVE_OVERLAP | 6 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| MISSING_SKILL | 10 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| OVERTIME_CAP | 6 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| UNAPPROVED_SWAP | 6 | 0 | 0 | 100.00% | 100.00% | 100.00% |

## Other legitimate findings

Coverage gaps and rest/hour violations are separate operational findings and are not false positives for the five required anomaly classes. The detector reported:

| Finding | Count |
|---|---:|
| COVERAGE_GAP | 126 |

## Method

1. Ground truth labels are written only by the anomaly injector, after valid baseline generation.
2. Ground truth is never loaded into the application database or passed to the detector.
3. Matching uses the documented affected-entity keys (employee + shift, shift + skill, employee + week, swap id).
4. Each labelled scenario is matched at most once; unmatched detections of the same type are false positives.
