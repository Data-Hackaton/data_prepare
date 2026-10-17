"""Preserve the original classes and allow explicitly unobservable states."""
import json
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT, HOST, credentials

def main():
    with make_client(HOST, credentials=credentials()) as client:
        project=client.projects.retrieve(1)
        labels=project.get_labels()
        backup=ROOT/'labels-before-annotation.json'
        if not backup.exists():
            backup.write_text(json.dumps([v.to_dict() for v in labels],indent=2),encoding='utf-8')
        changed=[]
        for label in labels:
            attrs=[a.to_dict() for a in label.attributes]
            dirty=False
            for attr in attrs:
                if (label.name,attr['name']) in {('computer','screen'),('safe','state'),('door','state')}:
                    if 'unknown' not in attr['values']:
                        attr['values'].append('unknown')
                        dirty=True
            if dirty:
                client.api_client.labels_api.partial_update(label.id,patched_label_request={'attributes':attrs})
                changed.append(label.name)
        current=project.get_labels()
        assert {x.name for x in current}=={x.name for x in labels}
        assert {x.id for x in current}=={x.id for x in labels}
        (ROOT/'labels-annotation.json').write_text(json.dumps([v.to_dict() for v in current],indent=2),encoding='utf-8')
        print(json.dumps({'updated_labels':changed,'label_count':len(current),'attribute_ids_preserved':True}))

if __name__=='__main__':main()
