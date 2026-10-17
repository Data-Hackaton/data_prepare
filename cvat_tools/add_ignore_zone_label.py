"""Add the repository's missing glass-zone class while preserving existing IDs."""
import json
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT, HOST, credentials


def main():
    schema=json.loads((ROOT.parent/'data_prepare_publish/cvat/labels.json').read_text(encoding='utf-8'))
    definition=next(label for label in schema if label['name']=='ignore_zone')
    assert definition['type']=='rectangle'
    with make_client(HOST,credentials=credentials()) as client:
        project=client.projects.retrieve(1)
        old={label.name:label.to_dict() for label in project.get_labels()}
        backup=ROOT/'qa_20261017/baseline/labels.json'
        if not backup.exists():backup.write_text(json.dumps(list(old.values()),indent=2),encoding='utf-8')
        if 'ignore_zone' not in old:
            # ProjectWriteSerializer.update_labels updates only supplied labels.
            project.update({'labels':[definition]})
        new={label.name:label.to_dict() for label in project.get_labels()}
        assert set(new)==set(old)|{'ignore_zone'}
        assert all(new[name]==label for name,label in old.items())
        actual=new['ignore_zone']
        assert actual['type']=='rectangle'
        assert actual['attributes'][0]['values']==['glass','window','other']
        (ROOT/'labels-annotation.json').write_text(json.dumps(list(new.values()),indent=2),encoding='utf-8')
        print(json.dumps({'added_label':'ignore_zone','labels':len(new),'existing_labels_unchanged':True}))


if __name__=='__main__':main()
