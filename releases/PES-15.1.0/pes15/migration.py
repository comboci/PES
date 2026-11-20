"""Explicit copy migration PES-14 -> PES-15. Never writes or alters the PES-14 source."""
from __future__ import annotations
import copy
from .core import canonical_bytes, digest, full_contract, metadata, RECORD_GROUPS
from .validation import validate, errors_only

class MigrationError(ValueError):
    pass


def migrate_v14(source: dict) -> dict:
    if not isinstance(source,dict) or source.get('_pes',{}).get('standard')!='PES-14':
        raise MigrationError('input must be a PES-14 JSON artifact; no implicit upgrade or downgrade')
    for group in ('project','artifact','records','scopes','relationships','retrieval','open_state','continuation','views'):
        if group not in source:
            raise MigrationError(f'PES-14 source missing {group}; refusing to invent historical data')
    if not isinstance(source['records'],dict) or any(not isinstance(source['records'].get(k),list) for k in RECORD_GROUPS):
        raise MigrationError('PES-14 records are incomplete; refusing lossy migration')
    if not isinstance(source['relationships'],list):
        raise MigrationError('PES-14 relationships must be an array')
    # All original domain content, scopes, IDs and state remain byte-equivalent as JSON data.
    result=copy.deepcopy(source)
    legacy={
        'task_priority_missing':[r['record_id'] for r in source['records']['tasks'] if isinstance(r,dict) and isinstance(r.get('record_id'),str) and 'priority' not in r],
        'observation_time_missing':[r['record_id'] for r in source['records']['observations'] if isinstance(r,dict) and isinstance(r.get('record_id'),str) and 'observed_at' not in r],
        'relationship_legacy_indices':[n for n,r in enumerate(source['relationships']) if not isinstance(r,dict) or any(k not in r for k in ['relationship_id','source_ref','target_ref','relation_type','status'])],
        'task_workflow_missing':[r['record_id'] for r in source['records']['tasks'] if isinstance(r,dict) and isinstance(r.get('record_id'),str) and 'workflow' not in r]
    }
    migration={'source_standard':'PES-14','source_revision':str(source['_pes'].get('schema_revision','unknown')),
        'source_sha256':digest(source), 'source_schema_digest':source['_pes'].get('schema_digest'), 'method':'opt_in_copy'}
    result['_pes']=metadata(legacy=legacy,migration=migration)
    # A new reference retrieval contract is opt-in; legacy default is NOT replaced.
    if not isinstance(result['retrieval'],dict) or not isinstance(result['retrieval'].get('contracts'),list):
        raise MigrationError('legacy retrieval contracts malformed; no safe migration available')
    existing={r.get('contract_id') for r in result['retrieval']['contracts'] if isinstance(r,dict)}
    new_id='RETRIEVAL-PES15-FULL'
    suffix=2
    while new_id in existing:
        new_id=f'RETRIEVAL-PES15-FULL-{suffix}';suffix+=1
    result['retrieval']['contracts'].append(full_contract(new_id))
    problems=errors_only(validate(result))
    if problems:
        # No corrupted/partial artifact is returned or written.
        summary='; '.join(f'{v.code} at {v.path}: {v.message}' for v in problems[:8])
        raise MigrationError('source is incompatible or inconsistent; manual reconciliation required: '+summary)
    return result


def upgrade_v15_0(source: dict) -> dict:
    """Explicit opt-in copy upgrade from 15.0.0; historical phase states remain unknown.

    Never modifies source or an existing PES-15 store. Does not infer stages from status.
    """
    if not isinstance(source,dict) or source.get('_pes',{}).get('standard')!='PES-15' or source.get('_pes',{}).get('schema_revision')!='15.0.0':
        raise MigrationError('upgrade-v15 requires a PES-15/15.0.0 JSON snapshot')
    if not isinstance(source.get('records'),dict) or any(not isinstance(source['records'].get(k),list) for k in RECORD_GROUPS):
        raise MigrationError('incomplete PES-15/15.0.0 source records')
    # Source metadata must match the original released PES-15.0.0 resource set.
    # This is a compatibility check, NOT a substitute for validating old data
    # with its original 15.0.0 engine before migration.
    known={
        'schema_digest':'fad97eb7073888eb08a644370d1fe4e22de41f0b3baf78d7d883909a2b562a45',
        'semantic_rules_digest':'467b7020d3bcc383243fc8b5d7e79c6716ca276f5b99642cf05dea497108a931',
        'compatibility_profile_digest':'8fc0e26a50ababa9688dbd1f406d3d1e6626c5b508da561cd3684e44ad6c9cd4',
    }
    if any(source['_pes'].get(k)!=v for k,v in known.items()):
        raise MigrationError('source metadata does not identify the released PES-15.0.0 resource set')
    result=copy.deepcopy(source)
    exceptions=copy.deepcopy(source['_pes'].get('legacy_exceptions',{}))
    exceptions['task_workflow_missing']=[r['record_id'] for r in source['records']['tasks'] if isinstance(r,dict) and isinstance(r.get('record_id'),str) and 'workflow' not in r]
    upgrade={'source_schema_revision':'15.0.0','source_sha256':digest(source),'method':'opt_in_copy'}
    result['_pes']=metadata(legacy=exceptions,migration=source['_pes'].get('migration'),upgrade=upgrade)
    if isinstance(result.get('release_context'),dict):
        result['release_context']['project_evolution_version']='15.1.0'
    problems=errors_only(validate(result))
    if problems:
        raise MigrationError('PES-15.0.0 is incompatible with PES-15.1.0; reconcile first: '+
            '; '.join(f'{i.code} at {i.path}: {i.message}' for i in problems[:6]))
    if source['records']!=result['records']:
        raise MigrationError('record preservation invariant failed')
    return result
