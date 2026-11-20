"""Rebuildable, source-traceable project context; no secondary truth store."""
from __future__ import annotations
from collections import defaultdict, deque
from datetime import datetime, timezone
from .core import RECORD_GROUPS, SINGULAR
from .validation import validate, errors_only

END_STATES=frozenset(['retired','rejected','superseded','obsolete'])

class RetrievalError(ValueError):pass


def context(data:dict, scope: str|None=None, contract_id: str|None=None, now:datetime|None=None) -> dict:
    problems=errors_only(validate(data))
    if problems:raise RetrievalError(f'cannot retrieve from invalid artifact: {problems[0].code} {problems[0].path}')
    contracts={r['contract_id']:r for r in data['retrieval']['contracts']}
    requested=contract_id or data['retrieval']['default_contract_ref']
    if requested not in contracts: raise RetrievalError(f'retrieval contract not found: {requested}')
    contract=contracts[requested]
    scopes={s['scope_id']:s for s in data['scopes']}
    if scope is not None and scope not in scopes:raise RetrievalError(f'unknown scope: {scope}')
    query_scopes=set(contract.get('subject_scope_refs',[]))
    if scope: query_scopes.add(scope)
    # Include child scopes transitively, because scoped knowledge inherits parent scope concerns.
    changed=True
    while changed:
        n=len(query_scopes)
        query_scopes.update(s['scope_id'] for s in scopes.values() if s.get('parent_scope_ref') in query_scopes)
        changed=n!=len(query_scopes)
    index={r['record_id']:(g,r) for g in RECORD_GROUPS for r in data['records'][g]}
    edges=defaultdict(set)
    for r in data['relationships']:
        if not isinstance(r,dict) or not all(k in r for k in ('source_ref','target_ref','relation_type')):continue # legacy unknown; no invented edges
        a,b=r['source_ref'],r['target_ref']
        edges[a].add(b);edges[b].add(a)
    for rid,(group,r) in index.items():
        for field in ('related_record_ids','evidence_refs'):
            for nxt in r.get(field,[]):
                edges[rid].add(nxt); edges[nxt].add(rid)
    selected={}
    depth=int(contract['relationship_depth'])
    seed={rid for rid,(_,r) in index.items() if not query_scopes or query_scopes.intersection(r.get('scope_refs',[]))}
    frontier=deque((s,0) for s in seed)
    for s in seed: selected[s]='scope'
    while frontier:
        rid,d=frontier.popleft()
        if d>=depth:continue
        for linked in edges[rid]:
            if linked in index and linked not in selected:
                selected[linked]=f'relation_depth_{d+1}'
                frontier.append((linked,d+1))
    output={g:[] for g in RECORD_GROUPS}
    trace=[]; uncovered=[]
    allow=set(contract['include_record_types'])
    now=now or datetime.now(timezone.utc)
    stale=[]
    for rid in sorted(selected):
        group,r=index[rid]
        if contract['current_only'] and r.get('status') in END_STATES:
            continue
        included=SINGULAR[group] in allow
        trace.append({'record_id':rid,'record_type':SINGULAR[group],
            'selection_reason':selected[rid], 'included':included,
            'provenance':r.get('provenance',{}),
            'implementation_state':r.get('implementation_state','unknown')})
        if included:output[group].append(r)
        else:uncovered.append(rid)
        valid_until=r.get('valid_until')
        if valid_until:
            try:
                expired=datetime.fromisoformat(valid_until.replace('Z','+00:00'))<now
                if expired:stale.append(rid)
            except ValueError:stale.append(rid)
    warnings=[]
    if uncovered:warnings.append({'code':'CONTRACT_EXCLUDES_RECORDS','detail':f'{len(uncovered)} selected records excluded by include_record_types','record_ids':uncovered})
    if stale:warnings.append({'code':'EXPIRED_RECORDS','detail':'Validity expired; do not represent as current','record_ids':stale})
    v={k:data.get('views',{}).get(k) for k in contract['required_views']}
    if contract.get('require_source_alignment'):
        for name,obj in v.items():
            state=obj.get('freshness_state','unknown') if isinstance(obj,dict) else 'unknown'
            if state not in ('confirmed','verified_current','aligned','current'):
                warnings.append({'code':'UNVERIFIED_SOURCE_ALIGNMENT',
                    'detail':f'{name}: freshness {state}; source repository has not been checked against revision','view':name})
    if data['_pes']['legacy_exceptions']['task_priority_missing']:
        warnings.append({'code':'HISTORIC_PRIORITY_UNKNOWN','detail':'Migrated tasks lack recorded priority','record_ids':data['_pes']['legacy_exceptions']['task_priority_missing']})
    if data['_pes']['legacy_exceptions']['observation_time_missing']:
        warnings.append({'code':'HISTORIC_OBSERVATION_TIME_UNKNOWN','detail':'Migrated observations lack observed_at','record_ids':data['_pes']['legacy_exceptions']['observation_time_missing']})
    # Absence of acceptance records is not interpreted as approval, even if task.status=completed.
    if any('target_external_ref' in r for r in data['relationships'] if isinstance(r,dict)):
        warnings.append({'code':'EXTERNAL_RELATION_UNVERIFIED','detail':'External relationship targets are declared references, not proof of external object existence'})
    if not data['records']['acceptances']:
        warnings.append({'code':'NO_OWNER_ACCEPTANCE_EVIDENCE','detail':'No explicit Acceptance records; Task completion and Verification do not imply acceptance'})
    return {'format':'PES-15-CONTEXT-1','source_artifact_id':data['artifact']['artifact_id'],
        'project_id':data['project']['project_id'],'contract_id':requested,'subject_scope':scope,
        'records':output,'traceability':trace,'derived_views':v,
        'warnings':warnings,'canonical_authority':'source snapshot (context is read-only and rebuildable)',
        'claim_of_live_source_alignment':False}
