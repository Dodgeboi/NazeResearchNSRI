#!/usr/bin/env python3
"""Apply interval frontier certificates and the pre-recorded external checks."""
from __future__ import annotations

import argparse
import importlib.util
import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.frontier_certificates import certify_frontier, two_objective_frontier
from grrc.interpretation import make_bank
from grrc.multiobjective import pareto_mask
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ['resource_constrained','intermediate_capacity','high_capacity']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-dirty',action='store_true')
    args=parser.parse_args()
    state=git_state()
    if (not state.get('available') or state['dirty']) and not args.allow_dirty:
        raise SystemExit('Commit source and benchmark inputs before generation.')
    out=ROOT/'data/frontier_certificates'
    out.mkdir(exist_ok=True)
    outputs=[]
    def save(name, rows):
        path=out/(name+'.csv')
        write_csv(pd.DataFrame(rows),path)
        outputs.append(path)
    raw_path=ROOT/'data/multiobjective/confirmatory/multiobjective_confirmatory_results.csv'
    summary_path=raw_path.parent/'portfolio_objective_summary.csv'
    columns=['profile','portfolio','scenario_id','paired','entry_point',
        'weighted_service_hours_lost','recovered_within_horizon']+[
        f'sustained_clinical_outage_k{k}' for k in range(1,5)]
    raw=pd.read_csv(raw_path,usecols=columns)
    summary=pd.read_csv(summary_path)
    hospital, details=[],[]
    for profile in PROFILES:
        bank=make_bank(raw,summary,profile,[])
        lower=bank.objectives(k=4)
        upper=lower.copy()
        upper[:,2]=bank.outage[:,:,0].mean(axis=0)
        cert=certify_frontier(lower,upper)
        masks=np.stack([pareto_mask(bank.objectives(k=k)) for k in range(1,5)])
        if any((cert.guaranteed & ~m).any() or (m & ~cert.possible).any() for m in masks):
            raise AssertionError('hospital k frontier outside interval certificate')
        hospital.append({'profile':profile,'candidates':len(bank.names),
            'guaranteed':int(cert.guaranteed.sum()),'observed_k4':int(masks[-1].sum()),
            'possible':int(cert.possible.sum()),'unresolved':int((cert.possible & ~cert.guaranteed).sum()),
            'intersection_of_four':int(masks.all(axis=0).sum()),'union_of_four':int(masks.any(axis=0).sum())})
        for j,name in enumerate(bank.names):
            details.append({'profile':profile,'portfolio':name,'outage_lower':lower[j,2],
                'outage_upper':upper[j,2],'guaranteed':bool(cert.guaranteed[j]),
                'possible':bool(cert.possible[j]),'observed_k4':bool(masks[-1,j]),
                'possible_dominator':bank.names[cert.possible_dominator[j]] if cert.possible_dominator[j]>=0 else '',
                'necessary_dominator':bank.names[cert.necessary_dominator[j]] if cert.necessary_dominator[j]>=0 else ''})
    save('hospital_summary',hospital)
    save('hospital_candidates',details)

    source=ROOT/'vendor/reproblems/reproblem.py'
    spec=importlib.util.spec_from_file_location('reproblems_archived',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    external, samples, candidates, corners=[],[],[],[]
    for p,name in enumerate(['RE21','RE22']):
        problem=getattr(module,name)()
        rng=np.random.default_rng(2026090603+p)
        decision=problem.lbound+(problem.ubound-problem.lbound)*rng.random((128,problem.n_variables))
        values=np.array([problem.evaluate(x) for x in decision])
        if not np.isfinite(values).all() or (values<0).any():
            raise AssertionError('unexpected external objective domain')
        nominal=two_objective_frontier(values)
        span=np.ptp(values,axis=0)
        for j in range(len(values)):
            candidates.append({'problem':name,'candidate':j,**{f'x{k+1}':x for k,x in enumerate(decision[j])},
                               'objective_1':values[j,0],'objective_2':values[j,1],
                               'nominal_efficient':bool(nominal[j])})
        for t,radius in enumerate([.01,.05,.10]):
            lower=np.maximum(0,values-radius*span)
            upper=values+radius*span
            cert=certify_frontier(lower,upper)
            rng=np.random.default_rng(2026090604+3*p+t)
            failures=0
            sizes=[]
            for b in range(1000):
                draw=lower+(upper-lower)*rng.random(values.shape)
                frontier=two_objective_frontier(draw)
                violated=(cert.guaranteed & ~frontier).any() or (frontier & ~cert.possible).any()
                failures+=int(violated)
                sizes.append(int(frontier.sum()))
                samples.append({'problem':name,'radius':radius,'draw':b,
                                'frontier_size':int(frontier.sum()),'certificate_violation':bool(violated)})
            external.append({'problem':name,'radius':radius,'candidates':len(values),
                'guaranteed':int(cert.guaranteed.sum()),'nominal':int(nominal.sum()),
                'possible':int(cert.possible.sum()),'draws':1000,'violations':failures,
                'observed_minimum':min(sizes),'observed_maximum':max(sizes)})
            if failures: raise AssertionError('external frontier outside certificate')
        # A distinct exact oracle: every corner of one uncertain coordinate.
        lower=values[:8].copy(); upper=values[:8].copy()
        lower[:,1]=np.maximum(0,lower[:,1]-.05*span[1]); upper[:,1]+=.05*span[1]
        cert=certify_frontier(lower,upper)
        all_masks=[]
        for bits in product([False,True],repeat=8):
            matrix=lower.copy()
            matrix[:,1]=np.where(bits,upper[:,1],lower[:,1])
            all_masks.append(two_objective_frontier(matrix))
        gmatch=np.array_equal(np.logical_and.reduce(all_masks),cert.guaranteed)
        pmatch=np.array_equal(np.logical_or.reduce(all_masks),cert.possible)
        corners.append({'problem':name,'candidates':8,'corners':len(all_masks),
                        'guaranteed_matches_intersection':gmatch,'possible_matches_union':pmatch})
        if not gmatch or not pmatch: raise AssertionError('exact corner oracle disagrees')
    save('external_summary',external)
    save('external_perturbations',samples)
    save('external_candidates',candidates)
    save('external_corner_checks',corners)
    inputs=[raw_path,summary_path,source,ROOT/'vendor/reproblems/LICENSE.txt',
            ROOT/'vendor/reproblems/PROVENANCE.md',ROOT/'study/FRONTIER_CERTIFICATE_PLAN.md',
            Path(__file__),ROOT/'src/grrc/frontier_certificates.py',ROOT/'src/grrc/interpretation.py',
            ROOT/'src/grrc/multiobjective.py',ROOT/'src/grrc/provenance.py',ROOT/'src/grrc/utilities.py']
    manifest=build_manifest(run_id='frontier-certificates',stage='analysis',
        description='Finite interval efficiency certificates and published engineering benchmark transfer checks.',
        inputs=inputs,outputs=outputs,source_state=state,parameters={
            'external_source_commit':'7876b4e465eac381a256e461d1310b8bb2b92846',
            'candidate_seed':2026090603,'perturbation_seed':2026090604,
            'radii':[.01,.05,.10],'candidates_per_problem':128,'draws_per_setting':1000,
            'hospital_scope':'five objectives fixed; k4-to-k1 candidate-specific outage intervals',
            'limits':'independently defined benchmark problems; same evaluation workflow; no hospital validation or NLP accuracy claim'})
    write_manifest(manifest,out/'certificate_manifest.json')
    print(pd.DataFrame(hospital).to_string(index=False))
    print(pd.DataFrame(external).to_string(index=False))
    print(pd.DataFrame(corners).to_string(index=False))


if __name__=='__main__': main()
