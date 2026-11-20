"""Independent, evidence-backed PES-15 task phases (never colors or priority)."""
from __future__ import annotations
import copy
from .core import WORKFLOW_PHASES, WORKFLOW_SUCCESS, RECORD_GROUPS
from .validation import validate, errors_only


def new_workflow(deliverable_phase: str, *, historical_unknown: bool = False) -> dict:
    """Create independent empty states; no phase completion is inferred."""
    if deliverable_phase not in WORKFLOW_PHASES:
        raise ValueError('invalid deliverable phase')
    return {'deliverable_phase':deliverable_phase, 'phases':{phase:{'state':'unknown' if historical_unknown else ('not_requested' if phase=='acceptance' else 'not_started'),
        'record_refs':[], 'source_revision_refs':[]} for phase in WORKFLOW_PHASES}}


def project_task(task: dict) -> dict:
    """Read-only projection: no workflow means UNKNOWN, even if status=completed."""
    workflow=task.get('workflow')
    if not isinstance(workflow,dict) or not isinstance(workflow.get('phases'),dict):
        return {'record_id':task.get('record_id'),'workflow_known':False,
            'deliverable_complete':None,'implementation_complete':None, 'verification_passed':None, 'owner_accepted':None,
            'phase_states':None,'deliverable_phase':None}
    states={name:workflow['phases'][name]['state'] for name in WORKFLOW_PHASES}
    deliverable=workflow['deliverable_phase']
    def projected(name):
        value=states[name]
        return None if value=='unknown' else value==WORKFLOW_SUCCESS[name]
    return {'record_id':task.get('record_id'),'workflow_known':True,'deliverable_phase':deliverable,
        'phase_states':states, 'deliverable_complete':projected(deliverable),
        'implementation_complete':projected('implementation'),
        'verification_passed':projected('verification'),'owner_accepted':projected('acceptance')}


def set_task_phase(snapshot: dict, task_id: str, phase: str, state: str,
                   *, record_refs: list[str] | None = None, source_revision_refs: list[str] | None = None,
                   reopen_reason: str | None = None) -> dict:
    """Return new validated snapshot updating *only* the selected task phase.

    Does not change Task.status, Task.priority, other phases, or the input. The caller
    commits via CanonicalStore CAS, never by overwriting a canonical PES-14 file.
    """
    if phase not in WORKFLOW_PHASES:
        raise ValueError('invalid task phase: '+phase)
    output=copy.deepcopy(snapshot)
    found=[r for r in output['records']['tasks'] if r.get('record_id')==task_id]
    if len(found)!=1:
        raise ValueError('task must exist exactly once: '+task_id)
    task=found[0]
    if not isinstance(task.get('workflow'),dict):
        raise ValueError('historical task workflow is unknown; explicit evidence-backed initialization required')
    target=task['workflow']['phases'][phase]
    target['state']=state
    for attr,new_refs in [('record_refs',record_refs),('source_revision_refs',source_revision_refs)]:
        if new_refs is not None:
            if not isinstance(new_refs,list) or any(not isinstance(x,str) for x in new_refs):
                raise ValueError(attr+' must be string list')
            target[attr]=list(dict.fromkeys(target[attr]+new_refs))
    if reopen_reason is not None:
        target['reopen_reason']=reopen_reason
    errors=errors_only(validate(output,baseline=snapshot))
    if errors:
        raise ValueError('invalid phase transition: '+'; '.join(f'{e.code} {e.path}' for e in errors[:5]))
    return output


def initialize_historical_workflow(snapshot: dict, task_id: str, deliverable_phase: str) -> dict:
    """Explicitly initialize a historical task's EMPTY workflow, no inferred progress.

    Retains the immutable original-migration exception and sets all phases UNKNOWN.
    A report of prior completion never becomes a phase success automatically.
    """
    if deliverable_phase not in WORKFLOW_PHASES:
        raise ValueError('invalid deliverable phase')
    out=copy.deepcopy(snapshot)
    matching=[task for task in out['records']['tasks'] if task.get('record_id')==task_id]
    if len(matching)!=1:
        raise ValueError('expected exactly one historic task')
    if 'workflow' in matching[0]:
        raise ValueError('workflow already exists; refusing to replace phase history')
    exceptions=out['_pes']['legacy_exceptions']['task_workflow_missing']
    if task_id not in exceptions:
        raise ValueError('task is not in the historic workflow exemption allowlist')
    matching[0]['workflow']=new_workflow(deliverable_phase,historical_unknown=True)
    # Preserve immutable original-legacy provenance: exemption tracks what
    # was missing at migration, not whether a workflow object now exists.
    issues=errors_only(validate(out, baseline=snapshot))
    if issues:
        raise ValueError('historical task workflow initialization rejected: '+
            '; '.join(f'{i.code} {i.path}' for i in issues[:6]))
    return out
