# Scene A final targeted-correction handoff

Stable cumulative checkpoint: **223 patches**, including **31 new targeted corrections after the earlier192**. First192 patch objects are structurally unchanged; their exact previous file is preserved as checkpoint_192_before_remaining.json.

checkpoint_patches.json SHA256: aec22efe465d8ec9329c570a6bf2b6454fdd6731d8a09f4a1fa1772aa945170e.

All223 patches applied successfully in memory to the frozen baselines. Original baseline hashes/samples and evidence files were checked. See checkpoint_validation.json. CVAT/Git/shared sources were not modified by this agent.

All10 owned videos meet the user-requested source0,5,10,... plus final-frame screening:2372/2372 selected frames, remaining0. Earlier dense review remains preserved (10147 full-frame source frames). This is not exhaustive validation of every original label/geometry; complete flags remain false for that reason.

## Confirmed findings now corrected

| Video | New targeted corrections |
|---|---|
| X1 | Reflection9 head/body50-59; client/cashier reflection separation175-194; missing hanging palm57-59 and both palms150-164. |
| X2 | Reflection8 head/body109-119; returning palm34 at470-472. Native selected105 shows the other palm behind glass, so no unverified missing hand was added. Existing corrected19 from110 and handle18 retained. |
| X3 | Early client reflection0-14 including visible shoe; cashier reflection175-194; mixed client16 tightened175-209; missing hanging palm60-69; palm28 follows handle110-119; palm50 follows return560-569. |
| X4 | Palm49 at390-399; machine return59 at800-809; existing66 corrected810-819 (no duplicate new track); palm67 at820-829; partial exiting reflection25 at1609-1613. |
| X5 | Exiting9 follows remaining body/foot1810-1826, then ghost1827-1829 removed. White client remains visible through1826; deletion from1820 would have been wrong. Duplicate32 removed1785-1829; new closed-glass entrant relabeled reflection1830-1884 and first geometry tightened1830-1839. Fixed-left-pane31/35/37 relabeled reflection. |
| X13 | Palm81 drops left1220-1229; partial reflections31 at1795-1814 and34 at1910-1922 tightened to visible fragments. |

New add_tracks contain dense samples with explicit outside boundaries; temporal positions between visually inspected anchors use actual source PTS. Corrected overlay verification caused source66 reuse in X4 and shoe-envelope expansion in X3 before final checkpoint.

## Remaining uncertain candidates; no unsupported deletion

- X1: possible merged/duplicate palms34/36/37/38/57/58/59/60; reflection20 at705-734 may contain only a remaining arm or empty glass.
- X3: exact open-door boundary45-49; palm47 tail575-579. Two real palms34/44 at480-489 are retained.
- X4: exact entry boundaries200-207/1670-1689, hanging palm208-214, handle38 tail240-249/40 at260-269; reflection17 tail1608-1610 and14 boundary1580-1589. Possible reflection fragment consolidation24/17 and30/33. Clasped/overlapping palms and possible lap-palm gaps require further evidence before deletion/addition.
- X5: palms77/79 at760-769 and85/86 at820-829 may be separate close palms. Other moving-hand fine geometry near machine/cabinet is not exhaustively refined; no additional exact error is asserted from screening alone. Source95/96/97 are real banknote-holding palms and retained.
- X8: possible person overlap6/10 at555-569 and fragments825-854 need native reconciliation; no new deletion from screening alone.
- X10: possible missed second palms100-129/460-466 remain uncertain. Mostly hidden phone after69 and banknote slivers375-376 deliberately omitted.
- X11: doorway hands25/26 at690-695 and person/reflection boundary600-728 need native confirmation; earlier typing/cabinet fine geometry is not exhaustively refined.
- X12: reflection14/15 at720-764 may be fragments of one person; verify union envelope before consolidation.
- X13: narrow reflection fragments1170-1186/1680-1739 may duplicate wider tracks; hand91 at1840-1849 is near closing-door boundary. No unsupported deletion.

No confirmed targeted finding is knowingly left as an unperformed correction. Remaining lists are uncertainty/fine-refinement notes, not claims of verified errors. Do not count generated-but-unviewed X12full24-26 or X13full pages toward coverage.
