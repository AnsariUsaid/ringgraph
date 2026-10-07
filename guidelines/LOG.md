# Log — decisions, numbers, problems (append only)

## 2026-10-07 baseline facts
- Data: IEEE-CIS, 590,540 txns, 3.5% fraud. Split: train d0-119, val d120-150, test d151-181.
- M1 tuned LightGBM, 431 features: test AUC 0.894, TPR@1%FPR 0.442, TPR@0.1%FPR 0.237.
- M2 (shape-only graph features), 5 seeds: full_test mean diff vs M1 = -0.006 (sd 0.013). Null.
- Graph: link attrs DeviceInfo,id_31,id_33,id_30,id_17,id_19,id_20,id_13; degree band 2-10, weight>=1.
  5,312 linked clients of 217,850 (2.4%); 550 rings (>=3 clients); 112 with >=2 fraud clients; 358 with none.
- Existing design forbids neighbour-label features (D-40). We now deliberately add them, time-respecting with a delay.
- Repo authors: Ansari Usaid (49 commits). User (Lohithnath) is a collaborator.
- Manifests record /Users/usaid/... paths: cosmetic, ignore.
- `.gitignore` ignores all `*.md` except README.md, so `guidelines/*.md` are NOT tracked unless a rule is added (ask user).

## Decisions
- 2026-10-07: do not strengthen M1 (user choice). Add a delayed-label control from tabular keys so the gain can be attributed to graph.
- 2026-10-07: GNN skipped for now.
- 2026-10-07: commits are one line, conventional format, user identity only.
