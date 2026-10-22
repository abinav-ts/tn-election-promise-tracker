import json, sys
p='/Users/abinavts/Projects/Election-Promise-Tracking/data/judgments/judge-20261022T070634Z/manifest.json'
m=json.load(open(p))
for b in m['batches']:
    if b['n']==int(sys.argv[1]) and not b.get('retry_of'):
        b['tokens']=int(sys.argv[2])
json.dump(m, open(p,'w'), indent=1, ensure_ascii=False)
