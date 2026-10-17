# Final scene C handoff — 2026-10-18

Frozen cumulative package: `checkpoint_patches_272.json`, **272 patches**, SHA256 `a6da9cac30ac1988870bf591dd171292042614979e917fc51875338835e3bca1`. `checkpoint_patches.json` and `patches.json` have identical bytes. The initial117 patches are unchanged;155 were added after that checkpoint. All13 pre-existing patches for transferred X39/40/43/44/45/46 are unchanged. Only scene_c files were edited. No CVAT/Git action performed by this agent.

Fresh `validate_and_preview.py` completed with **VALID272**, including reviewed evidence checks and application against immutable baseline tracks/source timestamps. Patched native previews for X30/31/32/33/34/35/37/38 were actually viewed. Main corrections: behind-glass class changes, confirmed duplicate/forearm removal, clipped rising heads, omitted X30 entrant/real hands, X33 whole entrant geometry, X34 departing sliver geometry, and early omitted cashier reflections. Interpolated geometry is explicitly disclosed; keyframes are hand-measured, intervening dense samples use source timestamps.

## Actual coverage

User changed the requirement to indices0,5,10,... plus last. All **1576/1576** selected frames in this block were actually viewed full-frame. Earlier consecutive views remain recorded. Native crops confirm suspected small objects and class/geometry. `human_review_complete=false`: this is selected-frame screening, not exhaustive pixel-perfect validation of every source frame.

| Video | Selected viewed | Actual full-frame source views | Cumulative patches |
|---|---:|---:|---:|
| X-28 | 100/100 | 492/492 | 21 |
| X-29 | 104/104 | 515/515 | 31 |
| X-30 | 114/114 | 562/562 | 30 |
| X-31 | 143/143 | 711/711 | 28 |
| X-32 | 129/129 | 637/637 | 25 |
| X-33 | 87/87 | 430/430 | 24 |
| X-34 | 107/107 | 120/530 | 23 |
| X-35 | 341/341 | 353/1700 | 29 |
| X-37 | 96/96 | 108/473 | 16 |
| X-38 | 355/355 | 366/1767 | 32 |

## Residual status

The confirmed correction queue is empty. `uncertain_candidates.json` lists unconfirmed candidates and limitations; these are not confirmed errors awaiting an omitted fix. Tiny upper-office images, actual feet visible below the desk and distinct pane images were preserved. X38 track12/41 changes object phase: track12 is actual through1079 then reflection1080–1559; track41 is actual1080–1634 and behind-glass1635–1649. Do not blanket-delete or relabel the actual span.

All historical `X*_PENDING.md` and previous handoff statements are superseded by this file and the current validated package. Transferred clips are owned by root/scene_b; their old local review coverage is not the final global ledger.

For import use baseline track indices, never indices regenerated after splitting/relabeling. Do not rerun mutation helpers against this frozen package. No background process is running.
