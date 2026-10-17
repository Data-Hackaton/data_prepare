# X44/X45/X46 sampled continuation

Latest user instruction changed the target to source indices 0,5,10,... plus final source frame. All selected full-frame samples were actually viewed: X44 124/124, X45 200/200, X46 116/116, total440. Source MOVs were always decoded sequentially from0. No random seeking.

Stable import: `c_extra_checkpoint.json`, identical to `c_extra_patches.json`, 50 new baseline-index patches (X44 10, X45 26, X46 14). Import exactly one of these files. Prior scene_c patches are not duplicated: its only existing X44 patch, person7 f275–284, remains independent and was included in application validation and visual previews.

`c_extra_validation.json` confirms application with frozen hashes and valid coordinates. Combined prior C + new patches touch960/1126/385 distinct object-frames respectively; these counts include the one prior C patch. New tracks have explicit dense per-frame samples, attributes, method and terminal outside markers. Geometry between manual anchors uses actual source timestamps.

Confirmed changes remove hand duplicates and a stationary equipment false reflection, correct reflected person classes, restore reflection gaps X45 690–704 and X46 315–329, restore the visible upright X44 banknote bundle405–420, trim X44 amodal person bottoms without inventing feet, and include X46 cashier arms previously cut from person8. X46 cup-side hand26 is moved from the cup to the actual fingers/palm. Applied-overlay pages were actually inspected, including the frozen hand23 sequence360–529 at step5; their paths and all native probes are recorded in the ledger.

`c_extra_review.json` records the exact sampled frames and native probe frames. `sampled_coverage_complete=true` does not mean pixel-perfect geometry. `complete=false` and `geometry_complete=false` remain explicit. Residuals: exact reflected arm contours, brief inter-sample events, fine note/hand occlusion geometry. X46 hand15/17 continuity160–199 was inspected but no unsupported new track was invented. Final known-boundary refinement includes X45 reflection9/15 left arms, X44 reflection8 both arm fragments, and X46 hand23 around the cup. These are limitations, not unviewed selected full-frame samples.

X39/X40/X43 are root-owned and were not reviewed/modified by this continuation. No CVAT, Git or files outside scene_b were modified.
