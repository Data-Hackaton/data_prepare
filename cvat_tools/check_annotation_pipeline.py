"""Boundary checks for dense coverage, disappearance, and changing attributes."""
from assemble_annotations import densify,split_dense,nearest,reflection

times=[0,.033,.071,.103,.139,.170]
assert nearest(times,.067)==2
track={'label':'door','attributes':{'state':'closed'},'keyframes':[
    {'time_sec':0,'box':[1,2,31,42],'attributes':{'state':'closed'}},
    {'time_sec':.103,'box':[4,2,34,42],'attributes':{'state':'open'}},
    {'time_sec':.170,'box':[6,2,36,42],'attributes':{'state':'open'}}]}
samples=densify(track,times)['samples']
assert [s['frame'] for s in samples]==list(range(6))
assert [s['attributes']['state'] for s in samples]==['closed','unknown','unknown','open','open','open']
assert samples[3]['box']==[4.,2.,34.,42.]
money={'label':'banknotes','keyframes':[
    {'time_sec':.033,'box':[2,4,12,9]},
    {'time_sec':.103,'box':[5,4,15,9],'outside':True}]}
samples=densify(money,times)['samples']
assert [(s['frame'],s['outside']) for s in samples]==[(1,False),(2,False),(3,True)]
base={'box':[1,2,3,4],'outside':False,'occluded':False,'attributes':{}}
parts=split_dense([('person',dict(base,frame=0)),('reflection',dict(base,frame=1)),
                   ('reflection',dict(base,frame=3))],9,'test')
assert len(parts)==3
assert parts[0]['samples'][-1]['outside'] and parts[0]['samples'][-1]['frame']==1
assert parts[1]['samples'][-1]['outside'] and parts[1]['samples'][-1]['frame']==2
manual={'reflection_regions':[{'polygon':[[0,0],[100,0],[100,400],[0,400]],'kind':'closed_door'}],
        'room_entry_boundary':{'conservative_glass_person_max_bottom_y':320}}
assert reflection([10,100,80,300],0,manual,{0:'closed'})
assert not reflection([10,100,80,300],0,manual,{0:'open'})
assert not reflection([10,100,80,420],0,manual,{0:'closed'})
print('PASS: variable frame timestamps, state uncertainty, outside boundaries, label changes, reflection exceptions')
