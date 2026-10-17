"""Regression checks for track reuse, duplicates, additions and removals."""
from revise_incremental_annotations import select_delta

def track(tid,x):
    return dict(id=tid,label_id=1,frame=0,source='auto',attributes=[],shapes=[dict(
        frame=0,type='rectangle',points=[x,0,x+5,5],outside=False,occluded=False,attributes=[])])

old=[track(10,0),track(11,0),track(12,20)]
desired=[track(0,0),track(0,30)]
kept,added,removed=select_delta(old,desired)
assert kept==[10]
assert added==[desired[1]]
assert [t['id'] for t in removed]==[11,12]
assert select_delta(old,old)==([10,11,12],[],[])
assert select_delta(old,[])==([],[],old)
assert select_delta([],desired)==([],desired,[])
print('PASS: unchanged tracks reused; duplicate multiplicity, additions and removals preserved')
