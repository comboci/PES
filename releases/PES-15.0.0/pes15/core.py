"""Canonical JSON and digest helpers. No writes to legacy PES-14 files."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent / 'resources'
RESOURCE_NAMES = ('PES-15.schema.json', 'PES-15.semantic-rules.json', 'PES-15.compatibility-profile.json')
RECORD_GROUPS = ('statements','ideas','questions','analyses','solutions','findings',
    'business_rules','technical_contracts','requirements','decisions','tasks',
    'evidence','verifications','acceptances','observations')
SINGULAR = dict(zip(RECORD_GROUPS, ('statement','idea','question','analysis','solution','finding',
    'business_rule','technical_contract','requirement','decision','task','evidence',
    'verification','acceptance','observation')))
TYPE_TO_GROUP = {v:k for k,v in SINGULAR.items()}
PRIORITIES = frozenset(['P0','P1','P2','P3','unassigned'])


def canonical_bytes(value: object) -> bytes:
    """Stable UTF-8 representation; normal JSON object key order is not material."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: str | Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False, allow_nan=False) + '\n'


def resources_digest() -> dict[str,str]:
    return {x: file_sha256(RESOURCES/x) for x in RESOURCE_NAMES}


def metadata(legacy: dict | None = None, migration: dict | None = None) -> dict:
    d = resources_digest()
    result = {'standard':'PES-15','schema_revision':'15.0.0',
        'schema_digest':d['PES-15.schema.json'],
        'semantic_rules_digest':d['PES-15.semantic-rules.json'],
        'compatibility_profile_digest':d['PES-15.compatibility-profile.json'],
        'legacy_exceptions':legacy or {'task_priority_missing':[], 'observation_time_missing':[], 'relationship_legacy_indices':[]}}
    if migration:
        result['migration'] = copy.deepcopy(migration)
    return result


def load_schema() -> dict:
    return read_json(RESOURCES / RESOURCE_NAMES[0])


def full_contract(contract_id: str = 'RETRIEVAL-PES15-FULL') -> dict:
    return {'contract_id':contract_id, 'title':'Complete PES-15 traceable continuation context',
        'subject_scope_refs':[], 'include_record_types':list(SINGULAR.values()),
        'required_views':['current_architecture','current_operational_context'],
        'relationship_depth':2, 'current_only':False,
        'require_source_alignment':True, 'output_profile':'standard'}


def blank_bootstrap() -> dict:
    """All unknown facts stay explicitly unknown; no fake timestamps or approvals."""
    return {
        '_pes':metadata(),
        'project':{'project_id':None, 'project_name':None, 'namespace':None},
        'artifact':{'artifact_id':None,'profile':'bootstrap_template','lifecycle':'active',
            'lineage_role':'root','acceptance_state':'draft','created_at':None,
            'parent_artifact_ids':[], 'base_artifact_id':None, 'source_modification_authorized':False},
        'release_context':{'software_release':None,'project_evolution_version':'15.0.0','base_project_evolution_version':None},
        'coordination':{'canonical_store_type':'unconfigured','canonical_store_ref':None,
            'startup_document_ref':'PES-15-START-HERE.md','write_concurrency':'sqlite_cas_v1'},
        'purpose':{'primary_goal':{'value':None,'knowledge_state':'not_yet_determined'},
            'problem':{'value':None,'knowledge_state':'not_yet_determined'},'success_criteria':[],'intent_notes':[]},
        'scopes':[], 'records':{k:[] for k in RECORD_GROUPS}, 'relationships':[],
        'views':{'current_architecture':None,'current_operational_context':None},
        'retrieval':{'contracts':[full_contract()],'default_contract_ref':'RETRIEVAL-PES15-FULL'},
        'open_state':{'open_question_ids':[],'open_conflict_relationship_ids':[],
            'blocked_record_ids':[],'next_work_record_ids':[],'candidate_solution_ids':[]},
        'continuation':{'current_summary':'PES-15 bootstrap only; not a canonical assessment.',
            'must_read_record_ids':[], 'known_limits':['Project and authoritative source not configured.']}}
