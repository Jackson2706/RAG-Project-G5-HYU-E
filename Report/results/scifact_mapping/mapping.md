# SciFact mapping report

- BEIR split: `test`
- Original SciFact split: `dev`
- BEIR SOURCE MD5: `5f7d1de60b170fc8027bb7898e2efca1`
- Original SciFact SOURCE MD5: `cb7da4d8609e30f2c7483b61aa447f7e`

## Mapping summary

| Metric | Count |
|---|---:|
| BEIR queries | 300 |
| Original claims | 300 |
| ID matched | 300 |
| Text equal | 300 |
| Qrels equal evidence | 175 |
| Qrels equal cited docs | 300 |
| Original claims missing from BEIR | 0 |

Unmatched BEIR IDs (first 20): None

## Matched claim labels

| Metric | Count |
|---|---:|
| SUPPORT | 124 |
| CONTRADICT | 64 |
| NEI | 112 |
| MIXED | 0 |

## Qrels comparison

| Metric | Count |
|---|---:|
| Qrels vs evidence: equal | 175 |
| Qrels vs evidence: superset | 125 |
| Qrels vs evidence: subset | 0 |
| Qrels vs evidence: other | 0 |
| NEI claims with qrels | 112 |
| Qrels equal cited docs | 300 |

## Original claims missing from BEIR

| Metric | Count |
|---|---:|
| Total | 0 |
| SUPPORT | 0 |
| CONTRADICT | 0 |
| NEI | 0 |
| MIXED | 0 |
