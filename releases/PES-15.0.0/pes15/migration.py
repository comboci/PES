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
        'relationship_legacy_indices':[n for n,r in enumerate(source['relationships']) if not isinstance(r,dict) or any(k not in r for k in ['relationship_id','source_ref','target_ref','relation_type','status'])]
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
