#!/usr/bin/env python3
"""Generate the methods paper's numeric macros, tables and vector figures.

--check re-derives all generated TeX without writing. Final generation requires
a clean source tree and captures that state before writing outputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from grrc.provenance import build_manifest, git_state, write_manifest, verify_manifest
from audit_interpretation_claims import audit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/interpretation"
PAPER = ROOT / "docs/manuscript"
CERT = ROOT / "data/frontier_certificates"
HIST = ROOT / "data/multiobjective"
PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
LABELS = ["Resource-constrained", "Intermediate", "High-capacity"]


def content():
    verify_manifest(DATA / "analysis_manifest.json")
    verify_manifest(CERT / "certificate_manifest.json")
    verify_manifest(HIST / "structural_sensitivity/structural_sensitivity_manifest.json")
    verify_manifest(HIST / "confirmatory/parameter_sensitivity_manifest.json")
    tables = {p.stem: pd.read_csv(p) for p in DATA.glob("*.csv")}
    ep = tables["endpoint_by_stage_profile"]
    con = ep[ep.stage == "confirmation"].set_index("profile").loc[PROFILES]
    if not np.allclose(ep.k1_minus_k4_pp, 100 * ep.between_share, atol=1e-7):
        raise AssertionError("nested endpoint identity fails")
    report = audit()
    if not report["all_expected_outcomes"]:
        raise AssertionError("interpretation assertions failed")
    best = tables["baseline_contrasts"].query("profile == 'high_capacity'").sort_values("mean_hours_saved").iloc[-1]
    bs = tables["frontier_bootstrap_summary"].query("profile == 'all_profiles'").set_index("metric")
    parameters = json.loads((DATA / "analysis_manifest.json").read_text())["parameters"]
    config = yaml.safe_load((ROOT/'configs/multiobjective_portfolio.yaml').read_text())
    hospital = pd.read_csv(CERT/'hospital_summary.csv').set_index('profile').loc[PROFILES]
    external = pd.read_csv(CERT/'external_summary.csv')
    corners = pd.read_csv(CERT/'external_corner_checks.csv')
    structure = pd.read_csv(HIST/'structural_sensitivity/structural_frontier_agreement.csv')
    movement = pd.read_csv(HIST/'structural_sensitivity/structural_objective_movement.csv').set_index(['profile','structural_arm'])
    sensitivity = json.loads((HIST/'confirmatory/parameter_sensitivity_summary.json').read_text())
    structural_parameters = json.loads((HIST/'structural_sensitivity/structural_sensitivity_manifest.json').read_text())['parameters']
    macros = {"PrimaryK": str(config['simulation']['sustained_outage_min_services']),
              "RevisionExecutions": f"{int(con.trials.sum()):,}", "RevisionScenarios": str(int(con.scenarios.iloc[0])),
              "BootstrapDraws": str(parameters["bootstrap"]), "WeightDraws": str(parameters["weight_draws"]),
              "WeightRejected": str(parameters["rejected_nonmonotone_tariffs"]),
              "ContrastFamily": str(parameters["contrast_family_size"]),
              "HighGap": f"{con.loc['high_capacity','k1_minus_k4_pp']:.2f}",
              "HighSaving": f"{best.mean_hours_saved:.2f}", "HighPairedSE": f"{best.paired_se:.3f}",
              "HighIndependentSE": f"{best.independent_se:.3f}", "HighLower": f"{best.simultaneous_lower:.2f}",
              "HighUpper": f"{best.simultaneous_upper:.2f}",
              "FrontierLow": f"{bs.loc['full_frontier','p025']:.0f}", "FrontierHigh": f"{bs.loc['full_frontier','p975']:.0f}",
              "OmittedLow": f"{bs.loc['omitted_efficient','p025']:.0f}", "OmittedHigh": f"{bs.loc['omitted_efficient','p975']:.0f}",
              "ArtifactPositive": f"{100*bs.loc['restricted_artifacts','positive_share']:.1f}",
              "FullFrontier": str(int(tables['frontier_point_counts'].full_frontier.sum())),
              "RestrictedFrontier": str(int(tables['frontier_point_counts'].restricted_frontier.sum())),
              "OmittedCandidates": str(int(tables['frontier_point_counts'].omitted_efficient.sum())),
              "CorrectContracts": str(len(report['current'])), "HistoricalContracts": str(len(report['historical'])),
              "MutationContracts": str(len(report['mutations']))}
    macros.update({
        'CertGuaranteedTotal': str(int(hospital.guaranteed.sum())),
        'CertObservedTotal': str(int(hospital.observed_k4.sum())),
        'CertGuaranteedPercent': f'{100*hospital.guaranteed.sum()/hospital.observed_k4.sum():.1f}',
        'CertHighGuaranteed': str(int(hospital.loc['high_capacity','guaranteed'])),
        'CertHighAdditional': str(int(hospital.loc['high_capacity','possible']-hospital.loc['high_capacity','observed_k4'])),
        'BenchmarkDraws': f'{external.draws.sum():,}',
        'BenchmarkCorners': str(int(corners.corners.sum())),
        'BenchmarkEmptySettings': str(int((external.guaranteed==0).sum())),
        'StructuralCandidates': str(int(structure.candidates_tested.sum())),
        'StructuralTrials': str(structural_parameters['trials_per_candidate']),
        'StructuralOnlyGated': str(int(structure.only_under_gated.sum())),
        'StructuralOnlyParallel': str(int(structure.only_under_parallel.sum())),
        'StructuralIntermediateGated': f"{movement.loc[('intermediate_capacity','gated_primary'),'mean_mean_hours_lost']:.2f}",
        'StructuralIntermediateParallel': f"{movement.loc[('intermediate_capacity','parallel_alternative'),'mean_mean_hours_lost']:.2f}",
        'ParameterWorstRank': f"{sensitivity['worst_rank_stability']:.3f}",
        'SampledCoefficients': str(sensitivity['parameters_sampled'])})
    pool = tables['pooling_comparison'].set_index('stage')
    for stage,prefix in [('discovery','Discovery'),('confirmation','Confirmation')]:
        for col,suffix in [('pooled_between_share','Pooled'),('equal_profile_between_share','Equal')]:
            macros[prefix+suffix] = f"{100*pool.loc[stage,col]:.2f}"
    for profile,prefix in zip(PROFILES,['Resource','Intermediate','High']):
        macros[prefix+'Weight'] = f"{100*con.loc[profile,'stage_weight']:.0f}"
        macros[prefix+'DiscoveryGap'] = f"{ep.loc[(ep.stage=='discovery')&(ep.profile==profile),'k1_minus_k4_pp'].iloc[0]:.2f}"
    generated = {"methods_numbers.tex": "% Generated; do not edit. Values are within-model, retrospective.\n" +
                 "\n".join("\\newcommand{\\" + k + "}{" + v + "}" for k,v in macros.items()) + "\n"}
    def table(name, heading, rows):
        generated[name + ".tex"] = heading + "\n" + "\n".join(" & ".join(row) + r" \\" for row in rows) + "\n"
    table('table_certificate_rows', '% Counts for the full independent endpoint box, five objectives fixed.', [
        [label]+[str(int(hospital.loc[p,c])) for c in ('candidates','guaranteed','observed_k4','possible')]
        for p,label in zip(PROFILES,LABELS)])
    table('table_transfer_rows', '% All planned problem/radius settings; independent benchmark definitions.', [
        [row.problem,f'{100*row.radius:.0f}\\%',str(row.guaranteed),str(row.nominal),str(row.possible)]
        for row in external.itertuples()])
    portfolios = pd.read_csv(HIST/'confirmatory/portfolio_objective_summary.csv')
    budget_rows, budget_selections = [], []
    for p,label in zip(PROFILES,LABELS):
        frame = portfolios[portfolios.profile==p]
        baseline = frame[frame.implementation_cost_points==0]
        if len(baseline)!=1:
            raise AssertionError('expected one free baseline per profile')
        budget = config['profiles'][p]['budget']
        chosen = frame[frame.implementation_cost_points<=budget].sort_values(['mean_hours_lost','portfolio']).iloc[0]
        budget_rows.append([label,str(budget),f'{baseline.iloc[0].mean_hours_lost:.2f}',
                            f'{chosen.mean_hours_lost:.2f}',f'{100*chosen.sustained_outage_probability_k4:.2f}'])
        budget_selections.append({'profile':p,'budget_points':budget,'selected_portfolio':chosen.portfolio,
            'free_mean_hours_lost':baseline.iloc[0].mean_hours_lost,
            'selected_mean_hours_lost':chosen.mean_hours_lost,
            'selected_cost_points':chosen.implementation_cost_points,
            'selected_burden_points':chosen.operational_burden_points,
            'selected_k4_frequency':chosen.sustained_outage_probability_k4})
    table('table_budget_rows', '% Mean-loss minimum among candidates within the declared profile budget.',budget_rows)
    generated['budget_portfolio_selections.csv'] = pd.DataFrame(budget_selections).to_csv(index=False,lineterminator='\n')
    ef = tables['endpoint_frontier_sensitivity'].query('k == 1').set_index('profile')
    table('table_endpoint_rows', '% Confirmation only: frequency percent; gap percentage points; Jaccard fraction.', [
        [label] + [f"{100*con.loc[p, f'k{k}_probability']:.2f}" for k in (1,4)] +
        [f"{con.loc[p,'k1_minus_k4_pp']:.2f}",f"{ef.loc[p,'jaccard_vs_k4']:.3f}"]
        for p,label in zip(PROFILES,LABELS)])
    resolution = tables['paired_resolution'].set_index('profile')
    table('table_pairing_rows', '% Matched stratified estimates and common bootstrap draws.', [
        [label] + [f"{int(resolution.loc[p,col]):,}" for col in ('candidate_pairs','independent_one_se_near_pairs','paired_one_se_near_pairs')]
        for p,label in zip(PROFILES,LABELS)])
    point = tables['frontier_point_counts'].set_index('profile')
    table('table_frontier_rows', '% Counts at the original confirmation bank.', [
        [label] + [str(int(point.loc[p,c])) for c in ('full_frontier','restricted_frontier','omitted_efficient','restricted_artifacts')]
        for p,label in zip(PROFILES,LABELS)])
    weights = tables['component_weight_sensitivity']
    table('table_weight_rows', '% Analyst-chosen component-weight stress; no probability interpretation.', [
        [label, f"{weights.loc[weights.profile == p,'jaccard'].median():.3f}",
         f"{weights.loc[weights.profile == p,'jaccard'].min():.3f}",
         str(int(weights.loc[weights.profile == p,'added'].max())), str(int(weights.loc[weights.profile == p,'removed'].max()))]
        for p,label in zip(PROFILES,LABELS)])
    ab = tables['objective_ablation']
    table('table_ablation_rows', '% Minimum/median/maximum frontier sizes across every subset of a given dimension.', [
        [str(d)] + [f"{g.min():.0f}/{g.median():g}/{g.max():.0f}" for p in PROFILES
                     for g in [ab.loc[(ab.profile == p)&(ab.dimensions == d),'frontier_size']]] for d in range(1,7)])
    return generated, tables


def figures(tables):
    plt.rcParams.update({'font.size':8, 'font.family':'DejaVu Sans', 'axes.spines.top':False,
        'axes.spines.right':False, 'pdf.fonttype':42, 'savefig.facecolor':'white'})
    folder = PAPER / 'methods_figures'
    folder.mkdir(exist_ok=True)
    paths = []
    def save(fig, name):
        fig.tight_layout()
        for suffix in ('pdf','png'):
            path = folder / (name + '.' + suffix)
            fig.savefig(path, dpi=200, bbox_inches='tight', metadata={'Creator':'Matplotlib'})
            paths.append(path)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.55))
    endpoint = tables['endpoint_by_stage_profile']
    for ax, stage in zip(axes, ('discovery','confirmation')):
        frame = endpoint[endpoint.stage == stage].set_index('profile')
        for profile, label, color in zip(PROFILES,LABELS,('#00738a','#b85824','#694c91')):
            ax.plot(range(1,5),[100*frame.loc[profile,f'k{k}_probability'] for k in range(1,5)],
                    marker='o',ms=4,color=color,label=label)
        ax.set(xticks=range(1,5),ylim=(0,100),xlabel='Required qualifying clinical services, k',
               ylabel='Candidate-average event frequency (%)', title=stage.capitalize())
        ax.grid(axis='y',alpha=.2)
    axes[1].legend(fontsize=7,loc='upper right',bbox_to_anchor=(1,.78),frameon=False)
    save(fig,'endpoint_ladder')
    draws = tables['frontier_bootstrap_draws'].groupby('draw').sum(numeric_only=True)
    fig, axes = plt.subplots(1, 2, figsize=(7.05,2.25))
    for ax, col, original, label in zip(axes,('omitted_efficient','restricted_artifacts'),(38,0),
           ('Omitted efficient candidates','Restricted-view artifacts')):
        x = draws[col]
        ax.hist(x, bins=np.arange(x.min()-.5,x.max()+1.5),color='#00738a',edgecolor='white',linewidth=.3)
        ax.axvline(original,color='#b85824',ls='--',label=f'Original count: {original}')
        ax.set(xlabel=label,ylabel='Conditional resampling draws')
        ax.legend(fontsize=7)
    save(fig,'conditional_frontier')
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--allow-dirty',action='store_true')
    args = parser.parse_args()
    state = git_state()
    generated,tables = content()
    if args.check:
        for name,value in generated.items():
            if (PAPER/name).read_text(encoding='utf-8') != value:
                raise AssertionError(f'stale generated TeX: {name}')
        verify_manifest(PAPER/'methods_manifest.json')
        print('paper values and manifest verified')
        return
    if (not state.get('available') or state['dirty']) and not args.allow_dirty:
        raise SystemExit('Commit source before final paper generation.')
    outputs = []
    for name,value in generated.items():
        path = PAPER/name
        path.write_text(value,encoding='utf-8',newline='\n')
        outputs.append(path)
    outputs += figures(tables)
    inputs = list(DATA.glob('*.csv')) + list(CERT.glob('*.csv')) + [DATA/'analysis_manifest.json',
        CERT/'certificate_manifest.json', HIST/'confirmatory/portfolio_objective_summary.csv',
        HIST/'confirmatory/parameter_sensitivity_summary.json', HIST/'confirmatory/parameter_sensitivity_manifest.json',
        HIST/'structural_sensitivity/structural_frontier_agreement.csv',
        HIST/'structural_sensitivity/structural_objective_movement.csv',
        HIST/'structural_sensitivity/structural_sensitivity_manifest.json',
        ROOT/'study/interpretation_contracts.json', ROOT/'src/grrc/claim_contracts.py', ROOT/'configs/multiobjective_portfolio.yaml',
        Path(__file__), ROOT/'scripts/audit_interpretation_claims.py']
    manifest = build_manifest(run_id='interpretation-paper',stage='analysis',
        description='Generated values, certificate and transfer tables, and figures for the final research manuscript.',
        inputs=inputs,outputs=outputs,parameters={'scope':'registered values and assertions, not all prose'},source_state=state)
    write_manifest(manifest,PAPER/'methods_manifest.json')
    print(f'generated {len(outputs)} paper artifacts')


if __name__ == '__main__':
    main()
