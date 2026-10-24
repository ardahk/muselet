import sys, json
sys.path.insert(0,'ml/src'); sys.path.insert(0,'evals')
from brain.plan_bank import load_bank, PlanBank
import planner_offline as po
bank = load_bank('v2-tune'); pb = PlanBank(bank)
v2 = [json.loads(l) for l in open('evals/planner_scenarios_v2.jsonl') if l.strip()]
tune_obs = {r['id']: r['observation'] for r in v2 if r['split']=='v2-tune'}
sets = {'v1-holdout': po.HOLDOUT, 'v1-holdout2': po.HOLDOUT2, 'v1-tune': po.TUNE,
        'v2-holdout': [r for r in v2 if r['split']=='v2-holdout']}
for name, S in sets.items():
    same=copy_pass=0; ex=[]
    for s in S:
        d = pb.retrieve(s['goal'], s['observation'], 1)
        if not d: continue
        d=d[0]
        sm = tune_obs.get(d.id)==s['observation']
        g = po.grade(s, d.batch)
        same+=sm; copy_pass+=bool(g['pass'])
        if g['pass']: ex.append((s['id'], d.id, sm))
    print(name, 'n',len(S),'same_screen_top1',same,'copying_retrieved_gold_passes',copy_pass)
    print('   ', ex[:40])
