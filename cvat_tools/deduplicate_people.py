"""Conservative per-frame deduplication of dense person/reflection tracks.

Pure Python, no inference or I/O. Input is the list produced inside
make_dynamic: track label/original_id and samples with frame/box/score/method.
Coordinates are native 464x848 pixels. The function does not infer identity
from overlap alone: it requires almost matching upper edges, containment,
three consecutive supporting frames, and distinctly stronger evidence.

Usage before rebuilding segments with split_dense::

    people, diagnostics = deduplicate_people(people)
    # Rebuild each track using only samples where outside is false.

Existing outside samples are preserved; callers MUST split at the new gaps
and regenerate outside boundaries. Boxes, labels and identities are never
changed. Equal-confidence pairs and uncertain geometry are intentionally
retained. A surviving detector box can still have inaccurate extent; this
filter is not a substitute for reviewing that box.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from copy import deepcopy
from itertools import combinations


def _same_upper_extent(a, b):
    """A conservative same-head proxy, not ordinary IoU NMS.

    Top-aligned duplicates can have very different lower bounds (the detector
    includes the table). Nested people with different head heights, and people
    alongside one another, must not be collapsed just because one box is large.
    """
    if len(a)!=4 or len(b)!=4 or not all(math.isfinite(v) for v in (*a,*b)):
        return False
    aw,ah=a[2]-a[0],a[3]-a[1]
    bw,bh=b[2]-b[0],b[3]-b[1]
    if min(aw,ah,bw,bh)<=0:return False
    mw,mh=min(aw,bw),min(ah,bh)
    if abs(a[1]-b[1])>min(8.0,.08*mh):return False
    if max(aw,bw)>2.25*mw or max(ah,bh)>3.0*mh:return False
    iw=max(0.0,min(a[2],b[2])-max(a[0],b[0]))
    ih=max(0.0,min(a[3],b[3])-max(a[1],b[1]))
    if iw<.90*mw or iw*ih<.80*min(aw*ah,bw*bh):return False
    center_delta=abs((a[0]+a[2]-b[0]-b[2])/2)
    if center_delta>.50*mw:return False
    # A side-aligned partial box needs a shared edge as well as containment.
    edge_delta=min(abs(a[0]-b[0]),abs(a[2]-b[2]))
    return center_delta<=.25*mw or edge_delta<=.18*mw


def _score(sample):
    score=sample.get('score')
    if not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=1:
        return None
    return float(score)


def conservative_person_mask(tracks, *, include_decisions=False):
    """Return a parallel list of keep masks and JSON-serializable diagnostics.

    Unknown scores, non-person labels and outside samples are left untouched.
    At least three *consecutive* geometry matches are required, including at
    the beginning/end of an overlap; lookahead is permitted in this offline
    operation. Ranking uses detector confidence, freshness and method, never
    box area or original_id. A weak candidate (score <= .55) needs an evidence
    disadvantage of >= .12 before it can be suppressed. Two confident people
    are deliberately retained even when their boxes nearly coincide.
    """
    masks=[[True]*len(t['samples']) for t in tracks]
    frames=defaultdict(list)
    quality={}
    raw_scores={}
    for ti,t in enumerate(tracks):
        if t.get('label') not in ('person','reflection'):continue
        last_detection=None
        for si,s in sorted(enumerate(t['samples']),key=lambda item:item[1]['frame']):
            if s.get('outside',False):continue
            score=_score(s)
            if score is None:continue
            method=s.get('method','')
            if method=='detector':last_detection=s['frame']
            age=0 if last_detection is None else max(0,s['frame']-last_detection)
            # Flow scores are carried forward unchanged by track_videos.py.
            # Discount stale evidence modestly instead of treating it as new.
            q=score-min(age,30)*.003
            if method=='detector':q+=.02
            elif method=='hold_uncertain':q-=.12
            quality[ti,si]=q
            raw_scores[ti,si]=score
            frames[s['frame'],t['label']].append((ti,si))

    candidates=defaultdict(list)
    for (frame,label),refs in frames.items():
        for (ti,si),(tj,sj) in combinations(refs,2):
            if ti==tj:continue
            if _same_upper_extent(tracks[ti]['samples'][si]['box'],tracks[tj]['samples'][sj]['box']):
                if ti>tj:ti,tj,si,sj=tj,ti,sj,si
                candidates[ti,tj].append((frame,si,sj))

    supported=defaultdict(set)
    for (ti,tj),rows in candidates.items():
        rows.sort()
        start=0
        for end in range(1,len(rows)+1):
            if end<len(rows) and rows[end][0]==rows[end-1][0]+1:continue
            if end-start>=3:
                for frame,si,sj in rows[start:end]:
                    supported[frame,tracks[ti]['label']].add(frozenset(((ti,si),(tj,sj))))
            start=end

    removed=Counter()
    pair_counts=Counter()
    ambiguous=0
    decisions=[]
    for key,edges in supported.items():
        # Greedy direct comparisons avoid transitive A~B~C chains deleting C
        # when only B overlaps it and A/C are actually different people.
        refs=sorted(frames[key],key=lambda ref:quality[ref],reverse=True)
        survivors=[]
        for ref in refs:
            suppressor=None
            for kept in survivors:
                if frozenset((ref,kept)) not in edges:continue
                if raw_scores[ref]<=.55 and quality[kept]-quality[ref]>=.12:
                    suppressor=kept
                    break
                ambiguous+=1
            if suppressor is None:
                survivors.append(ref)
                continue
            ti,si=ref
            ki,ks=suppressor
            masks[ti][si]=False
            label=tracks[ti]['label']
            removed[label]+=1
            pair_counts[label,ki,ti]+=1
            if include_decisions:
                decisions.append({'frame':key[0],'label':label,
                    'kept_original_id':tracks[ki].get('original_id'),
                    'removed_original_id':tracks[ti].get('original_id'),
                    'kept_score':raw_scores[suppressor],'removed_score':raw_scores[ref],
                    'kept_evidence':round(quality[suppressor],4),
                    'removed_evidence':round(quality[ref],4)})
    report={
        'duplicate_people_samples_removed':sum(removed.values()),
        'duplicate_people_removed_by_label':dict(removed),
        'duplicate_people_ambiguous_pair_samples_kept':ambiguous,
        'duplicate_people_pairs':[{'label':label,
            'kept_original_id':tracks[ki].get('original_id'),
            'removed_original_id':tracks[ti].get('original_id'),'samples_removed':count}
            for (label,ki,ti),count in sorted(pair_counts.items())],
    }
    if include_decisions:report['duplicate_people_decisions']=decisions
    return masks,report


def deduplicate_people(tracks, *, include_decisions=False):
    """Return detached filtered tracks and diagnostics, without mutating input.

    Tracks retaining only outside markers are dropped. Any surviving track
    keeps its original metadata, sample order and outside markers; the caller
    rebuilds continuous segments and outside markers after filtering.
    """
    masks,report=conservative_person_mask(tracks,include_decisions=include_decisions)
    result=[]
    for track,mask in zip(tracks,masks):
        kept=[s for s,keep in zip(track['samples'],mask) if keep]
        if track.get('label') in ('person','reflection') and not any(not s.get('outside',False) for s in kept):
            continue
        item=deepcopy(track)
        item['samples']=deepcopy(kept)
        result.append(item)
    return result,report
