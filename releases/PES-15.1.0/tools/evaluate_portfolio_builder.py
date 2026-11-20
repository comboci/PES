#!/usr/bin/env python3
"""Read-only PES-14 -> isolated PES-15 runtime acceptance harness.

Works with the representative fixture or an explicitly supplied current GitHub
source file. NEVER modifies source or canonical repository, writes new outputs only.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pes15.core import digest, read_json, RECORD_GROUPS
from pes15.task_workflow import new_workflow
from pes15.cli import write_new
from pes15.migration import migrate_v14
from pes15.retrieval import context
from pes15.store import CanonicalStore, Conflict
from pes15.validation import validate, errors_only

ROOT=Path(__file__).resolve().parents[1]

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'examples'/'portfolio_builder_legacy_v14_demo.json',
        help='PES-14 input source; must remain unchanged')
    p.add_argument('--output-dir',type=Path,required=True,help='NEW independent output directory')
    args=p.parse_args(argv)
    source=args.source.resolve();out=args.output_dir.resolve()
    if not source.is_file():p.error('source not found')
    if source == out or source in out.parents:p.error('output must not replace source')
    out.mkdir(parents=True,exist_ok=True)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    old=read_json(source)
    migrated=migrate_v14(old)
    if migrated['records']!=old['records'] or migrated['scopes']!=old['scopes'] or migrated['relationships']!=old['relationships']:
        raise RuntimeError('legacy facts changed during copy migration')
    migrated_issues=validate(migrated)
    if errors_only(migrated_issues):raise RuntimeError('invalid migration result')
    write_new(out/'migrated_pes15.json',migrated)
    new_contract=next(c['contract_id'] for c in migrated['retrieval']['contracts'] if c['contract_id'].startswith('RETRIEVAL-PES15-FULL'))
    scope='SC-STORAGE' if any(x['scope_id']=='SC-STORAGE' for x in migrated['scopes']) else None
    extracted=context(migrated,scope=scope,contract_id=new_contract)
    write_new(out/'context_pes15.json',extracted)
    store=CanonicalStore(out/'demo_canonical.sqlite')
    initial=store.init(migrated,actor='pes15-demo',reason='read-only migration demonstration')
    old_head=store.head()
    first=copy.deepcopy(old_head['data']); second=copy.deepcopy(old_head['data'])
    existing={r['record_id'] for g in RECORD_GROUPS for r in migrated['records'][g]}
    def new_id(suffix):
        base=f'TASK-PES15-DEMO-{suffix}';n=1;candidate=base
        while candidate in existing:candidate=base+'-'+str(n);n+=1
        return candidate
    for data,letter in ((first,'A'),(second,'B')):
        data['records']['tasks'].append({'record_id':new_id(letter),
            'title':f'Demo-only isolated concurrent writer {letter}',
            'detail':'Synthetic task produced only in an independent PES-15 demo store; no Portfolio Builder code edit.',
            'scope_refs':[scope] if scope else [],'status':'planned','priority':'unassigned',
            'workflow':new_workflow('implementation'),
            'provenance':{'type':'pes15_demo_fixture','date':date.today().isoformat()},
            'implementation_state':'not_implemented'})
    succeeded=store.commit(first,old_head['revision'],old_head['sha256'],actor='demo-writer-A',reason='synthetic test task')
    rejected=False
    try:
        store.commit(second,old_head['revision'],old_head['sha256'],actor='demo-writer-B',reason='stale synthetic task')
    except Conflict:
        rejected=True
    if not rejected:raise RuntimeError('unexpected: stale writer was not rejected')
    proof=store.verify()
    if not proof['ok']:raise RuntimeError('integrity verification failed')
    backup=store.backup(out/'demo_backup.sqlite')
    if not CanonicalStore(out/'demo_backup.sqlite').verify()['ok']:
        raise RuntimeError('disaster-recovery backup verification failed')
    write_new(out/'demo_head.json',store.head()['data'])
    after=hashlib.sha256(source.read_bytes()).hexdigest()
    if before!=after:raise RuntimeError('PES-14 source file changed unexpectedly')
    report={
      'run_type':'isolated_PES15_integration_test','source':str(source),
      'source_is_portfolio_builder_repository_canonical':source.name=='Project-Evolution-V1-PES-14.json',
      'source_sha256_before':before,'source_sha256_after':after,
      'source_unchanged':before==after,'legacy_records_exactly_preserved':migrated['records']==old['records'],
      'legacy_scopes_exactly_preserved':migrated['scopes']==old['scopes'],
      'legacy_relationships_exactly_preserved':migrated['relationships']==old['relationships'],
      'record_counts':{group:len(old['records'][group]) for group in RECORD_GROUPS},
      'total_records':sum(len(old['records'][g]) for g in RECORD_GROUPS),
      'scope_count':len(old['scopes']),
      'legacy_unknown_priority_tasks':len(migrated['_pes']['legacy_exceptions']['task_priority_missing']),
      'legacy_unknown_time_observations':len(migrated['_pes']['legacy_exceptions']['observation_time_missing']),
      'legacy_untyped_relationships':len(migrated['_pes']['legacy_exceptions']['relationship_legacy_indices']),
      'migration_valid':not errors_only(migrated_issues),
      'migration_warning_codes':sorted(set(x.code for x in migrated_issues if x.severity=='warning')),
      'retrieval_contract_used':new_contract,'retrieval_warning_codes':[x['code'] for x in extracted['warnings']],
      'demo_commit_revision':succeeded['revision'],'stale_writer_rejected':rejected,
      'sqlite_history_integrity_ok':proof['ok'],'sqlite_revisions':proof['revision_count'],
      'verified_backup_revisions':backup['revisions'],
      'limitations':['No Portfolio Builder application code, build, or runtime is modified by this harness.',
         'Legacy records are not automatically accepted/verified by their migration.',
         'The representative fixture is a subset and includes one synthetic Task; the full GitHub snapshot requires --source pointing to a local copy.']
    }
    write_new(out/'integration_report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
