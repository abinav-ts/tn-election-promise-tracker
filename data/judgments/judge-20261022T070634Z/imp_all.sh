#!/bin/zsh
# import every finished, not-yet-imported strong batch; apply logged tokens
S=/private/tmp/claude-501/-Users-abinavts-Projects-Election-Promise-Tracking/f2505556-9f82-4c66-b127-72f3b18d8563/scratchpad
R=judge-20261022T070634Z
cd /Users/abinavts/Projects/Election-Promise-Tracking && source .venv/bin/activate
for d in $S/sj/sj-20261022T070634Z-batch_*; do
  name=${d##*-}; f=$d/out/verdicts.jsonl; dst=data/judgments/$R/out/$name.jsonl
  [ -s $f ] && [ ! -e $dst ] && mkdir -p data/judgments/$R/out && cp $f $dst
done
python -m ept judge import --run $R --model claude-opus-5-5 2>&1 | tail -1
[ -f $S/tokens.txt ] && while read n t; do python3 $S/tok.py $n $t; done < $S/tokens.txt
python3 - <<PY
import json
m=json.load(open('data/judgments/$R/manifest.json'))
b=[x for x in m['batches'] if not x.get('retry_of')]
imp=[x for x in b if x.get('status','').startswith('imported')]
print("imported", len(imp), "/", len(b), "| with failures:", [x['n'] for x in imp if x.get('failed')], "| tokens logged:", sum(1 for x in imp if x.get('tokens')))
PY
