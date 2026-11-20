"""Build deterministic, explicitly non-authoritative Portfolio Builder test fixtures."""
from pathlib import Path
import copy
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pes15.core import blank_bootstrap,dumps
from pes15.migration import migrate_v14

ROOT=Path(__file__).resolve().parents[1]
legacy=blank_bootstrap()
legacy['_pes']={'standard':'PES-14','schema_revision':'14.0.0',
 'schema_digest':'0461a63f0a08f299a0f8ece052f38cdc8848a1437b6f2d102be6ab0f187e4c7f',
 'semantic_rules_digest':'375af191f6fb9a8b17db77a347419b89cd649b18a90849561d03e54ffb4c6497',
 'compatibility_profile_digest':'62b52c8a14ceaf6ac5816e8c6dacaa25d6880c01c69e8ed63020b6fa248468e9'}
legacy['project']={'project_id':'NSP-PORTFOLIO-BUILDER','project_name':'NSP Portfolio Builder','namespace':'NSP-PB'}
legacy['artifact'].update({'artifact_id':'PES14-PORTFOLIO-REPRESENTATIVE-TEST-FIXTURE',
    'profile':'canonical_snapshot','created_at':'2026-11-19T06:36:00Z'})
legacy['release_context']={'software_release':'fixture_only','project_evolution_version':'PES-14','base_project_evolution_version':None}
legacy['coordination']={'canonical_store_type':'test_fixture','canonical_store_ref':None,
    'startup_document_ref':'PROJECT-EVOLUTION-START-HERE-PES-14.md','write_concurrency':'not_applicable_to_test'}
legacy['purpose']['primary_goal']={'value':'Exercise PE-15 logic with selected Portfolio Builder domain facts','knowledge_state':'test_fixture_only'}
legacy['purpose']['problem']={'value':'Demonstrate safe migration, traceable retrieval and concurrent writers','knowledge_state':'test_fixture_only'}
legacy['scopes']=[
 {'scope_id':'SC-PROJECTS','scope_type':'module','name':'Project workspaces','parent_scope_ref':None,'status':'active'},
 {'scope_id':'SC-PORTFOLIOS','scope_type':'module','name':'Multiple portfolio documents','parent_scope_ref':None,'status':'active'},
 {'scope_id':'SC-LIBRARY','scope_type':'module','name':'Project and global image library','parent_scope_ref':None,'status':'active'},
 {'scope_id':'SC-TEMPLATES','scope_type':'module','name':'Master and page templates','parent_scope_ref':None,'status':'active'},
 {'scope_id':'SC-STORAGE','scope_type':'module','name':'Tauri and SQLite persistence','parent_scope_ref':None,'status':'active'},
 {'scope_id':'SC-ONCE','scope_type':'feature','name':'One-off and repeated elements','parent_scope_ref':None,'status':'active'}]

def rec(record_id,title,detail,scope,status='approved_intent',pt='user_conversation',impl='unverified_against_live_source'):
    return {'record_id':record_id,'title':title,'detail':detail,'scope_refs':[scope],
       'status':status,'provenance':{'type':pt,'date':'2026-11-19'},'implementation_state':impl}
legacy['records']['statements']=[rec('ST-001','System purpose','Author multiple architecture portfolios per project using globally reusable live-inherited templates and centrally managed image assets.','SC-PROJECTS')]
legacy['records']['solutions']=[rec('SOL-001','Implementation direction',
'Use system-wide template entities and dependency tracking; propagate master changes to all descendants. Model assets, project ownership and usage references separately in SQLite; apply foreign keys and transactional cascades plus guarded asset garbage collection.','SC-STORAGE')]
legacy['records']['business_rules']=[rec('BR-001','Page-specific once elements',
'Text Once and Image Once are page-only, never master-template elements; deleting the owning page deletes them.','SC-ONCE')]
legacy['records']['decisions']=[rec('DEC-001','Project-first organization',
'Project is primary workspace and contains independent portfolios. Templates are defined in a centralized system-wide template library, independent of projects and portfolios.','SC-PROJECTS')]
legacy['records']['tasks']=[rec('TASK-DEMO-LEGACY-001','Synthetic historical task lacking priority',
'Demo-only record to exercise PES-14 historical missing priority; not a claim about an actual repository task.',
'SC-STORAGE',status='planned',pt='fixture_synthetic',impl='not_implemented')]
legacy['records']['observations']=[{
    'record_id':'OBS-001', 'title':'Owner V80 runtime review feedback',
    'status':'source_only_addressed_except_autosave',
    'detail':'V80 owner review: Add button left alignment, inherited-page count, layer-delete cascade, editor Library removal, project/public library selection and autosave with unsaved-exit protection requested. V81 source commits 2d657fb9 and 72c1b33b cover first five categories. Autosave toggle and warning remain pending. No owner acceptance yet.',
    'scope_refs':['SC-TEMPLATES','SC-PORTFOLIOS','SC-LIBRARY'],
    'provenance':{'type':'user_runtime_report','date':'2026-11-19','source_revision_ref':'0f07fdbe7b5488205daa5901b5b793755dd6d6e2'},
    'implementation_state':'V81_source_changes_committed_runtime_unverified'}]
legacy['views']={'current_architecture':{'freshness_state':'unknown','note':'Fixture: not source-aligned'},
    'current_operational_context':{'freshness_state':'unknown','note':'Fixture: not an operational live observation'}}
legacy['retrieval']={'contracts':[{ 'contract_id':'RETRIEVAL-DEFAULT','title':'Default PES-14 continuation context',
'subject_scope_refs':[],'include_record_types':['business_rule','technical_contract','requirement','decision','solution','finding','question','verification','acceptance','observation','task'],
'required_views':['current_architecture'],'relationship_depth':2,'current_only':False,
'require_source_alignment':True,'output_profile':'standard'}], 'default_contract_ref':'RETRIEVAL-DEFAULT'}
legacy['open_state']={'open_question_ids':[],'open_conflict_relationship_ids':[],'blocked_record_ids':[],
'next_work_record_ids':['TASK-DEMO-LEGACY-001'],'candidate_solution_ids':[]}
legacy['continuation']={'current_summary':'Non-authoritative miniature integration fixture for PES-15; not the real repository canonical record.',
    'must_read_record_ids':['DEC-001','BR-001'], 'known_limits':[
        'Selected historical facts adapted from NSP-Portfolio-Builder PE14 as inspected on 2026-11-20.',
        'A synthetic historical task demonstrates missing priority; this is not a live Task ID.',
        'This partial test fixture is not a replacement for the full GitHub canonical snapshot.']}
(ROOT/'examples'/'portfolio_builder_legacy_v14_demo.json').write_text(dumps(legacy),encoding='utf-8')
converted=migrate_v14(legacy)
(ROOT/'examples'/'portfolio_builder_migrated_v15_demo.json').write_text(dumps(converted),encoding='utf-8')
(ROOT/'examples'/'PES-15-empty-bootstrap.json').write_text(dumps(blank_bootstrap()),encoding='utf-8')
print('created representative fixture; full real repo sample intentionally not embedded')
