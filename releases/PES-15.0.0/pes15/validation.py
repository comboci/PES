"""PES-15 structural, referential, semantic and historical validation."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import re
from typing import Any
from jsonschema import Draft202012Validator, FormatChecker
from .core import (RECORD_GROUPS, SINGULAR, TYPE_TO_GROUP, PRIORITIES,
    load_schema, resources_digest)

@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str

    def to_dict(self):
        return asdict(self)


def _issue(errors, code, path, message, severity='error'):
    errors.append(Issue(severity, code, path, message))


def _items(data, name):
    obj = data.get('records') if isinstance(data,dict) else None
    if isinstance(obj,dict) and isinstance(obj.get(name),list):
        return [v for v in obj[name] if isinstance(v,dict)]
    return []


def _lists(data, group):
    return data.get(group,[]) if isinstance(data.get(group),list) else []


def _lookup(data):
    indexed={}
    for g in RECORD_GROUPS:
        for record in _items(data,g):
            rid=record.get('record_id')
            if isinstance(rid,str) and rid not in indexed:
                indexed[rid]=(g,record)
    return indexed


def _identities(data):
    found=defaultdict(list)
    for g in RECORD_GROUPS:
        for i,rec in enumerate(_items(data,g)):
            found[rec.get('record_id')].append(f'records.{g}[{i}]')
    for group,field in [('scopes','scope_id'),('relationships','relationship_id')]:
        for i, obj in enumerate(_lists(data,group)):
            if isinstance(obj,dict) and isinstance(obj.get(field),str):
                found[obj[field]].append(f'{group}[{i}]')
    contracts=data.get('retrieval',{}).get('contracts',[]) if isinstance(data.get('retrieval'),dict) else []
    for i, obj in enumerate(contracts):
        if isinstance(obj,dict) and isinstance(obj.get('contract_id'),str):
            found[obj['contract_id']].append(f'retrieval.contracts[{i}]')
    return found


def _is_iso_datetime(s):
    try:
        parsed = datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return parsed.tzinfo is not None
    except (TypeError, ValueError):
        return False


def validate(data: Any, baseline: dict | None = None) -> list[Issue]:
    out=[]
    schema=load_schema()
    validator=Draft202012Validator(schema,format_checker=FormatChecker())
    for e in validator.iter_errors(data):
        loc='$' + ''.join(f'[{part}]' if isinstance(part,int) else f'.{part}' for part in e.absolute_path)
        _issue(out,'SCHEMA',loc,e.message)
    if not isinstance(data,dict):
        return sorted(out,key=lambda e:(e.severity,e.code,e.path))
    # Short-circuit on malformed top-level collections, preventing untrusted JSON from crashing the validator.
    if not isinstance(data.get('records'),dict) or not isinstance(data.get('retrieval'),dict) or not isinstance(data.get('_pes'),dict):
        return sorted(out,key=lambda e:(e.severity,e.code,e.path))
    md=data['_pes']; current_digests=resources_digest()
    for name,expected in [('schema_digest',current_digests['PES-15.schema.json']),
        ('semantic_rules_digest',current_digests['PES-15.semantic-rules.json']),
        ('compatibility_profile_digest',current_digests['PES-15.compatibility-profile.json'])]:
        if md.get(name)!=expected:
            _issue(out,'RESOURCE_DIGEST',f'_pes.{name}',f'does not match installed PES-15 resource digest ({expected})')
    idx=_lookup(data); scope_index={r.get('scope_id'):r for r in _lists(data,'scopes') if isinstance(r,dict) and isinstance(r.get('scope_id'),str)}
    relationships=_lists(data,'relationships')
    rel_index={r.get('relationship_id'):r for r in relationships if isinstance(r,dict) and isinstance(r.get('relationship_id'),str)}
    contracts=data['retrieval'].get('contracts',[])
    contract_ids={r.get('contract_id') for r in contracts if isinstance(r,dict) and isinstance(r.get('contract_id'),str)}
    for ident, paths in _identities(data).items():
        if isinstance(ident,str) and len(paths)>1:
            _issue(out,'DUPLICATE_ID',paths[0],f'{ident} appears at {", ".join(paths)}')
    for sid,scope in scope_index.items():
        parent=scope.get('parent_scope_ref')
        if parent is not None and parent not in scope_index:
            _issue(out,'SCOPE_REF',f'scopes.{sid}.parent_scope_ref',f'unknown parent {parent}')
        visited={sid}; cursor=parent
        while cursor in scope_index and cursor is not None:
            if cursor in visited:
                _issue(out,'SCOPE_CYCLE',f'scopes.{sid}',f'parent chain contains a cycle at {cursor}')
                break
            visited.add(cursor); cursor=scope_index[cursor].get('parent_scope_ref')
    legacy=md.get('legacy_exceptions',{})
    if not isinstance(legacy,dict): legacy={}
    task_exceptions=set(legacy.get('task_priority_missing',[]) if isinstance(legacy.get('task_priority_missing'),list) else [])
    obs_exceptions=set(legacy.get('observation_time_missing',[]) if isinstance(legacy.get('observation_time_missing'),list) else [])
    relation_exceptions=set(legacy.get('relationship_legacy_indices',[]) if isinstance(legacy.get('relationship_legacy_indices'),list) else [])
    migrated=md.get('migration',{}).get('source_standard')=='PES-14' if isinstance(md.get('migration'),dict) else False
    if not migrated and (task_exceptions or obs_exceptions or relation_exceptions):
        _issue(out,'LEGACY_NOT_MIGRATED','_pes.legacy_exceptions','legacy exemptions require a PES-14 migration provenance')
    for group in RECORD_GROUPS:
        for rec in _items(data,group):
            rid=rec.get('record_id')
            loc=f'records.{group}.{rid}'
            for field,target in [('scope_refs',scope_index),('related_record_ids',idx),('evidence_refs',idx)]:
                for ref in rec.get(field,[]) if isinstance(rec.get(field,[]),list) else []:
                    if isinstance(ref,str) and ref not in target:
                        _issue(out,'DANGLING_REF',f'{loc}.{field}',f'{ref} does not exist')
            provenance=rec.get('provenance',{})
            if isinstance(provenance,dict):
                for ref in provenance.get('record_refs',[]) if isinstance(provenance.get('record_refs',[]),list) else []:
                    if isinstance(ref,str) and ref not in idx:
                        _issue(out,'DANGLING_REF',f'{loc}.provenance.record_refs',f'{ref} does not exist')
            if group=='tasks' and rec.get('priority') not in PRIORITIES:
                if rid in task_exceptions and 'priority' not in rec:
                    _issue(out,'LEGACY_UNKNOWN',f'{loc}.priority','historic task priority was never recorded','warning')
                else:
                    _issue(out,'TASK_PRIORITY',f'{loc}.priority','PES-15 task must specify P0, P1, P2, P3 or unassigned')
            if group=='observations' and 'observed_at' not in rec:
                if rid in obs_exceptions:
                    _issue(out,'LEGACY_UNKNOWN',f'{loc}.observed_at','historic observation timestamp was never recorded','warning')
                else:
                    _issue(out,'OBSERVATION_TIME',f'{loc}.observed_at','new observation requires a timezone-aware timestamp')
            if group=='observations':
                for field in ['observed_at','confirmed_at','valid_from','valid_until']:
                    if field in rec and not _is_iso_datetime(rec[field]):
                        _issue(out,'TIMEZONE',f'{loc}.{field}',f'{field} must contain a timezone offset or Z')
                if rec.get('valid_from') and rec.get('valid_until') and _is_iso_datetime(rec.get('valid_from')) and _is_iso_datetime(rec.get('valid_until')):
                    if datetime.fromisoformat(rec['valid_from'].replace('Z','+00:00'))>datetime.fromisoformat(rec['valid_until'].replace('Z','+00:00')):
                        _issue(out,'INVALID_TIME_INTERVAL',loc,'valid_from must not be after valid_until')
    # Material decisions and acceptance records must not be inferred from prose or Task status.
    for group in ('solutions','verifications','acceptances'):
        for rec in _items(data,group):
            rid=rec.get('record_id')
            related=set(rec.get('related_record_ids',[]) if isinstance(rec.get('related_record_ids',[]),list) else [])
            for rel in relationships:
                if not isinstance(rel,dict):continue
                if rel.get('source_ref')==rid and isinstance(rel.get('target_ref'),str):related.add(rel['target_ref'])
                if rel.get('target_ref')==rid and isinstance(rel.get('source_ref'),str):related.add(rel['source_ref'])
            if group=='solutions' and rec.get('status') in ('selected','adopted','approved_for_implementation'):
                if not any(ref in idx and idx[ref][0]=='decisions' for ref in related):
                    _issue(out,'SOLUTION_WITHOUT_DECISION',f'records.solutions.{rid}',
                           'selected/adopted Solution requires an explicit linked Decision')
            if group in ('verifications','acceptances') and not related:
                _issue(out,'UNLINKED_VERIFICATION_ACCEPTANCE',f'records.{group}.{rid}',
                       'Verification/Acceptance must name its subject via a linked record, not generic prose')
    for group,exceptions,missing_field in [('tasks',task_exceptions,'priority'),('observations',obs_exceptions,'observed_at')]:
        for ident in exceptions:
            if ident not in idx or idx[ident][0]!=group or missing_field in idx[ident][1]:
                _issue(out,'INVALID_LEGACY_EXCEPTION',f'_pes.legacy_exceptions.{group}',f'{ident} is not an existing {group} item missing {missing_field}')
    for n,rel in enumerate(relationships):
        loc=f'relationships[{n}]'
        if n in relation_exceptions:
            _issue(out,'LEGACY_RELATIONSHIP',loc,'historic untyped relation was preserved; do not treat as verified typed relation','warning')
            continue
        if not isinstance(rel,dict):
            _issue(out,'RELATIONSHIP_TYPE',loc,'new relationships must be typed objects')
            continue
        for e in Draft202012Validator({'$schema':schema['$schema'],'$defs':schema['$defs'],'$ref':'#/$defs/relationship'}).iter_errors(rel):
            _issue(out,'RELATIONSHIP_TYPE',loc,e.message)
        for field in ['source_ref','target_ref']:
            value=rel.get(field)
            if isinstance(value,str) and value not in idx:
                _issue(out,'DANGLING_RELATION',f'{loc}.{field}',f'{value} is not a record ID (external references require a separate explicit contract)')
        if isinstance(rel.get('target_external_ref'),dict):
            _issue(out,'EXTERNAL_REF_UNVERIFIED',f'{loc}.target_external_ref','external target is declared, but its existence and source revision are not verified locally','warning')
        if rel.get('source_ref') and rel.get('source_ref')==rel.get('target_ref'):
            _issue(out,'SELF_RELATION',loc,'a record cannot relate to itself')
    for n in relation_exceptions:
        if type(n) is not int or n<0 or n>=len(relationships):
            _issue(out,'INVALID_LEGACY_EXCEPTION','_pes.legacy_exceptions.relationship_legacy_indices',f'unknown relationship index {n}')
    # Explicit external refs: source_revision_refs / git SHAs are intentionally NOT local record pointers.
    for i,contract in enumerate(contracts if isinstance(contracts,list) else []):
        if not isinstance(contract,dict):continue
        for ref in contract.get('subject_scope_refs',[]) if isinstance(contract.get('subject_scope_refs'),list) else []:
            if isinstance(ref,str) and ref not in scope_index:
                _issue(out,'RETRIEVAL_SCOPE',f'retrieval.contracts[{i}]',f'unknown scope {ref}')
    dref=data['retrieval'].get('default_contract_ref')
    if dref is not None and dref not in contract_ids:
        _issue(out,'RETRIEVAL_DEFAULT','retrieval.default_contract_ref',f'unknown contract {dref}')
    open_state=data.get('open_state',{})
    if isinstance(open_state,dict):
        field_groups={'open_question_ids':'questions','candidate_solution_ids':'solutions','next_work_record_ids':'tasks'}
        for key in ('open_question_ids','candidate_solution_ids','next_work_record_ids','blocked_record_ids','open_conflict_relationship_ids'):
            values=open_state.get(key,[])
            if not isinstance(values,list):
                _issue(out,'OPEN_STATE_TYPE',f'open_state.{key}','expected an array of stable IDs')
                continue
            if len(values)!=len(set(v for v in values if isinstance(v,str))):
                _issue(out,'OPEN_STATE_DUPLICATE',f'open_state.{key}','duplicate record references')
            for ref in values:
                if not isinstance(ref,str):
                    _issue(out,'OPEN_STATE_TYPE',f'open_state.{key}','expected string ID'); continue
                if key=='open_conflict_relationship_ids':
                    if ref not in rel_index:
                        _issue(out,'OPEN_STATE_REF',f'open_state.{key}',f'unknown relationship {ref}')
                    elif rel_index[ref].get('relation_type')!='conflicts_with':
                        _issue(out,'OPEN_STATE_REF',f'open_state.{key}',f'{ref} is not a conflict relation')
                elif ref not in idx or (key in field_groups and idx[ref][0]!=field_groups[key]):
                    _issue(out,'OPEN_STATE_REF',f'open_state.{key}',f'{ref} does not point to the required record type')
    continuation=data.get('continuation',{})
    if isinstance(continuation,dict):
        for ref in continuation.get('must_read_record_ids',[]) if isinstance(continuation.get('must_read_record_ids',[]),list) else []:
            if isinstance(ref,str) and ref not in idx:
                _issue(out,'CONTINUATION_REF','continuation.must_read_record_ids',f'unknown record {ref}')
    # Warnings are deliberately not acceptance approvals or verified source facts.
    for key in ('current_architecture','current_operational_context'):
        view=data.get('views',{}).get(key) if isinstance(data.get('views'),dict) else None
        if isinstance(view,dict):
            if 'freshness_state' not in view:
                _issue(out,'FRESHNESS_UNKNOWN',f'views.{key}', 'no freshness_state; current-state claim not established','warning')
            elif view['freshness_state'] in ('unknown','stale','source_prepared_runtime_unknown','unverified','unconfirmed'):
                _issue(out,'FRESHNESS_UNKNOWN',f'views.{key}',f'freshness is {view["freshness_state"]}; do not treat as live truth','warning')
    if data.get('artifact',{}).get('profile')=='canonical_snapshot':
        for k in ('project_id','project_name','namespace'):
            if not isinstance(data.get('project',{}).get(k),str) or not data['project'][k].strip():
                _issue(out,'CANONICAL_IDENTITY',f'project.{k}','canonical snapshot requires a populated project identity')
        if not _is_iso_datetime(data.get('artifact',{}).get('created_at')):
            _issue(out,'CANONICAL_IDENTITY','artifact.created_at','canonical snapshot requires actual timestamp with timezone')
        if not isinstance(data.get('artifact',{}).get('artifact_id'),str) or not data['artifact']['artifact_id'].strip():
            _issue(out,'CANONICAL_IDENTITY','artifact.artifact_id','canonical snapshot requires a stable artifact ID')
    # Detect only high-confidence secret material, never broad guesses from ordinary content.
    _scan_secrets(data,out)
    if baseline is not None:
        if baseline.get('_pes',{}).get('standard')!='PES-15':
            _issue(out,'BASELINE_STANDARD','baseline._pes','baseline must be PES-15')
        else:
            for group in RECORD_GROUPS:
                old={r['record_id'] for r in _items(baseline,group) if isinstance(r.get('record_id'),str)}
                new={r['record_id'] for r in _items(data,group) if isinstance(r.get('record_id'),str)}
                for missing in old-new:
                    _issue(out,'HISTORY_DELETION',f'records.{group}',f'cannot remove or move record {missing}; retire or supersede it')
            for group,id_field in [('scopes','scope_id'),('relationships','relationship_id')]:
                old={r.get(id_field) for r in _lists(baseline,group) if isinstance(r,dict) and isinstance(r.get(id_field),str)}
                new={r.get(id_field) for r in _lists(data,group) if isinstance(r,dict) and isinstance(r.get(id_field),str)}
                for missing in old-new:
                    _issue(out,'HISTORY_DELETION',group,f'cannot remove historic {group} ID {missing}')
            oc={x['contract_id'] for x in baseline.get('retrieval',{}).get('contracts',[]) if isinstance(x,dict) and isinstance(x.get('contract_id'),str)}
            nc={x['contract_id'] for x in contracts if isinstance(x,dict) and isinstance(x.get('contract_id'),str)}
            for missing in oc-nc:
                _issue(out,'HISTORY_DELETION','retrieval.contracts',f'cannot remove historic contract {missing}')
            olegacy=baseline.get('_pes',{}).get('legacy_exceptions',{})
            for field in ('task_priority_missing','observation_time_missing','relationship_legacy_indices'):
                old=set(olegacy.get(field,[]));new=set(legacy.get(field,[]))
                for added in new-old:
                    _issue(out,'LEGACY_EXCEPTION_EXPANSION',f'_pes.legacy_exceptions.{field}',f'cannot add a legacy exception {added} after migration')
            old_relationships=baseline.get('relationships',[])
            for n in olegacy.get('relationship_legacy_indices',[]):
                if n<len(old_relationships) and n<len(relationships) and relationships[n]!=old_relationships[n]:
                    _issue(out,'LEGACY_RELATIONSHIP_MUTATION',f'relationships[{n}]','legacy relationship is frozen until an explicit typed conversion is implemented')
            # Prevent cross-project redirection under the same canonical store.
            if baseline.get('_pes',{}).get('migration') != md.get('migration'):
                _issue(out,'MIGRATION_PROVENANCE_MUTATION','_pes.migration','migration origin digest and source are immutable')
            if baseline.get('artifact',{}).get('artifact_id') != data.get('artifact',{}).get('artifact_id'):
                _issue(out,'ARTIFACT_ID_MUTATION','artifact.artifact_id','canonical artifact stable ID cannot change')
            if baseline.get('project',{}).get('project_id')!=data.get('project',{}).get('project_id'):
                _issue(out,'PROJECT_ID_MUTATION','project.project_id','canonical project identity is immutable')
    return sorted(out,key=lambda e:(e.severity!='error',e.code,e.path,e.message))


def _scan_secrets(data, issues):
    hidden_keys={'private_key','password','passwords','client_secret','access_token','refresh_token','api_secret','api_key','token'}
    secret_pattern=re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|\bgithub_pat_[A-Za-z0-9_]{12,}|\bgh[pousr]_[A-Za-z0-9]{20,}',re.I)
    def walk(obj,path):
        if isinstance(obj,dict):
            for key,val in obj.items():
                p=f'{path}.{key}'
                if key.lower() in hidden_keys and val is not None and not (isinstance(val,str) and val.startswith('ref:')):
                    _issue(issues,'SECRET_VALUE',p,'plaintext secret-like field; store secure ref:<identifier> instead')
                walk(val,p)
        elif isinstance(obj,list):
            for i,val in enumerate(obj):walk(val,f'{path}[{i}]')
        elif isinstance(obj,str) and secret_pattern.search(obj):
            _issue(issues,'SECRET_VALUE',path,'possible credential or private key content detected')
    walk(data,'$')


def errors_only(issues):
    return [x for x in issues if x.severity=='error']
