"""PES-15.1 guarantees no automatic promotion between independently tracked task phases."""
from __future__ import annotations
import copy, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from pes15.core import digest, metadata
from pes15.migration import migrate_v14, upgrade_v15_0, MigrationError
from pes15.task_workflow import new_workflow, project_task, set_task_phase
from pes15.validation import validate, errors_only
from pes15.retrieval import context
from pes15.store import CanonicalStore, StoreValidation
ROOT=Path(__file__).resolve().parents[1]
LEGACY=json.loads((ROOT/'examples/portfolio_builder_legacy_v14_demo.json').read_text(encoding='utf-8'))
MIGRATED=migrate_v14(LEGACY)


def codes(snapshot, baseline=None, severity='error'):
    return {x.code for x in validate(snapshot, baseline) if x.severity==severity}


def sample(deliverable='implementation', task_id='TASK-STAGE-NEW'):
    d=copy.deepcopy(MIGRATED)
    d['records']['tasks'].append({
        'record_id':task_id,'title':'Stage example','detail':'Synthetic independent status test',
        'status':'planned','scope_refs':['SC-STORAGE'],'priority':'P2',
        'provenance':{'type':'test_fixture','date':'2026-11-20'},
        'workflow':new_workflow(deliverable),
    })
    return d


def proof(d, group, ref, task_id, status='recorded'):
    d['records'][group].append({'record_id':ref,'title':group+' proof','detail':'Explicit, scoped stage output',
        'status':status,'related_record_ids':[task_id],
        'provenance':{'type':'test_fixture','date':'2026-11-20'}})


class StageIsolationTests(unittest.TestCase):
    def test_native_task_without_workflow_is_rejected(self):
        d=sample();d['records']['tasks'][-1].pop('workflow')
        self.assertIn('TASK_WORKFLOW_REQUIRED',codes(d))

    def test_legacy_task_preserved_unknown_even_if_status_completed(self):
        d=copy.deepcopy(MIGRATED);t=d['records']['tasks'][0];t['status']='completed'
        self.assertNotIn('TASK_WORKFLOW_REQUIRED',codes(d))
        self.assertEqual(project_task(t)['deliverable_complete'],None)
        self.assertEqual(project_task(t)['implementation_complete'],None)
        self.assertIn('TASK_WORKFLOW_UNKNOWN',codes(d,severity='warning'))
        c=context(d,contract_id='RETRIEVAL-PES15-FULL')
        self.assertIn('TASK_PHASES_HISTORIC_UNKNOWN',{w['code'] for w in c['warnings']})
        self.assertFalse(c['task_progress'][t['record_id']]['workflow_known'])

    def test_rank_or_color_never_completes_implementation(self):
        d=sample(); t=d['records']['tasks'][-1]
        t['priority']='P0'
        t['color']='green' # Legacy UI extension must not be interpreted as completion.
        self.assertEqual(project_task(t)['deliverable_complete'],False)
        self.assertEqual(project_task(t)['implementation_complete'],False)
        self.assertEqual(project_task(t)['verification_passed'],False)
        self.assertEqual(project_task(t)['owner_accepted'],False)
        self.assertEqual(codes(d),set())

    def test_prioritization_completed_only_its_phase_not_implementation(self):
        d=sample();proof(d,'decisions','DEC-RANK','TASK-STAGE-NEW')
        after=set_task_phase(d,'TASK-STAGE-NEW','prioritization','completed',record_refs=['DEC-RANK'])
        p=project_task(after['records']['tasks'][-1]);self.assertEqual(p['phase_states']['prioritization'],'completed')
        self.assertEqual(p['phase_states']['implementation'],'not_started')
        self.assertFalse(p['deliverable_complete'])
        self.assertEqual(after['records']['tasks'][-1]['status'],'planned')
        self.assertEqual(after['records']['tasks'][-1]['priority'],'P2')
        self.assertEqual(d['records']['tasks'][-1]['workflow']['phases']['prioritization']['state'],'not_started')
        self.assertEqual(codes(after),set())

    def test_prioritization_deliverable_is_complete_without_code_change(self):
        d=sample('prioritization');proof(d,'decisions','DEC-RANK','TASK-STAGE-NEW')
        after=set_task_phase(d,'TASK-STAGE-NEW','prioritization','completed',record_refs=['DEC-RANK'])
        p=project_task(after['records']['tasks'][-1]);self.assertTrue(p['deliverable_complete'])
        self.assertFalse(p['implementation_complete'])
        self.assertFalse(p['verification_passed'])

    def test_implementation_completed_does_not_verify_or_accept(self):
        d=sample()
        after=set_task_phase(d,'TASK-STAGE-NEW','implementation','completed',source_revision_refs=['git:0123456789abcdef'])
        p=project_task(after['records']['tasks'][-1])
        self.assertTrue(p['deliverable_complete'])
        self.assertTrue(p['implementation_complete'])
        self.assertFalse(p['verification_passed'])
        self.assertFalse(p['owner_accepted'])
        self.assertIn('TASK_IMPLEMENTED_UNVERIFIED',codes(after,severity='warning'))

    def test_cannot_mark_task_completed_just_for_prioritization(self):
        d=sample();proof(d,'decisions','DEC-RANK','TASK-STAGE-NEW')
        after=set_task_phase(d,'TASK-STAGE-NEW','prioritization','completed',record_refs=['DEC-RANK'])
        after['records']['tasks'][-1]['status']='completed'
        self.assertIn('TASK_FALSE_COMPLETION',codes(after))

    def test_can_label_implementation_deliverable_completed_without_tests(self):
        d=sample();after=set_task_phase(d,'TASK-STAGE-NEW','implementation','completed',source_revision_refs=['git:abcd'])
        after['records']['tasks'][-1]['status']='completed'
        self.assertNotIn('TASK_FALSE_COMPLETION',codes(after))
        self.assertFalse(project_task(after['records']['tasks'][-1])['verification_passed'])

    def test_implementation_completed_without_artifact_is_rejected(self):
        d=sample()
        with self.assertRaisesRegex(ValueError,'TASK_PHASE_MISSING_PROOF'):
            set_task_phase(d,'TASK-STAGE-NEW','implementation','completed')

    def test_prioritization_completed_without_decision_is_rejected(self):
        d=sample()
        with self.assertRaisesRegex(ValueError,'TASK_PHASE_MISSING_PROOF'):
            set_task_phase(d,'TASK-STAGE-NEW','prioritization','completed')

    def test_unrelated_decision_cannot_prove_prioritization(self):
        d=sample();proof(d,'decisions','DEC-OTHER','SOMEONE-ELSE')
        with self.assertRaisesRegex(ValueError,'TASK_PHASE_EVIDENCE_LINK'):
            set_task_phase(d,'TASK-STAGE-NEW','prioritization','completed',record_refs=['DEC-OTHER'])

    def test_verification_requires_verification_record_not_priority(self):
        d=sample()
        with self.assertRaisesRegex(ValueError,'TASK_VERIFICATION_PROOF'):
            set_task_phase(d,'TASK-STAGE-NEW','verification','passed')
        proof(d,'verifications','VER-001','TASK-STAGE-NEW',status='passed')
        after=set_task_phase(d,'TASK-STAGE-NEW','verification','passed',record_refs=['VER-001'])
        p=project_task(after['records']['tasks'][-1])
        self.assertTrue(p['verification_passed']);self.assertFalse(p['implementation_complete'])
        self.assertFalse(p['owner_accepted'])

    def test_verification_failed_record_never_passes(self):
        d=sample();proof(d,'verifications','VER-FAILED','TASK-STAGE-NEW',status='failed')
        with self.assertRaisesRegex(ValueError,'TASK_VERIFICATION_PROOF'):
            set_task_phase(d,'TASK-STAGE-NEW','verification','passed',record_refs=['VER-FAILED'])
        failed=set_task_phase(d,'TASK-STAGE-NEW','verification','failed',record_refs=['VER-FAILED'])
        self.assertFalse(project_task(failed['records']['tasks'][-1])['verification_passed'])

    def test_acceptance_requires_approval_record(self):
        d=sample()
        with self.assertRaisesRegex(ValueError,'TASK_ACCEPTANCE_PROOF'):
            set_task_phase(d,'TASK-STAGE-NEW','acceptance','accepted')
        proof(d,'acceptances','ACC-001','TASK-STAGE-NEW',status='accepted')
        after=set_task_phase(d,'TASK-STAGE-NEW','acceptance','accepted',record_refs=['ACC-001'])
        self.assertTrue(project_task(after['records']['tasks'][-1])['owner_accepted'])
        self.assertFalse(project_task(after['records']['tasks'][-1])['implementation_complete'])

    def test_verification_cannot_stand_in_for_acceptance(self):
        d=sample();proof(d,'verifications','VER-001','TASK-STAGE-NEW',status='passed')
        with self.assertRaisesRegex(ValueError,'TASK_PHASE_EVIDENCE_TYPE'):
            set_task_phase(d,'TASK-STAGE-NEW','acceptance','accepted',record_refs=['VER-001'])

    def test_phase_update_is_pure_and_preserves_other_phases(self):
        d=sample();before=copy.deepcopy(d)
        result=set_task_phase(d,'TASK-STAGE-NEW','prioritization','in_progress')
        self.assertEqual(d,before)
        for x in ('analysis','implementation','verification','acceptance'):
            self.assertEqual(result['records']['tasks'][-1]['workflow']['phases'][x],before['records']['tasks'][-1]['workflow']['phases'][x])

    def test_reopen_completed_phase_requires_reason(self):
        d=sample();yes=set_task_phase(d,'TASK-STAGE-NEW','implementation','completed',source_revision_refs=['sha-1'])
        with self.assertRaisesRegex(ValueError,'TASK_PHASE_REOPEN_UNJUSTIFIED'):
            set_task_phase(yes,'TASK-STAGE-NEW','implementation','in_progress')
        reopened=set_task_phase(yes,'TASK-STAGE-NEW','implementation','in_progress',reopen_reason='new defect found')
        self.assertIn('sha-1',reopened['records']['tasks'][-1]['workflow']['phases']['implementation']['source_revision_refs'])

    def test_proof_references_cannot_be_erased(self):
        d=sample();yes=set_task_phase(d,'TASK-STAGE-NEW','implementation','completed',source_revision_refs=['sha-1'])
        broken=copy.deepcopy(yes)
        broken['records']['tasks'][-1]['workflow']['phases']['implementation']['source_revision_refs']=[]
        self.assertIn('TASK_PHASE_HISTORY_LOSS',codes(broken,yes))

    def test_deliverable_type_cannot_silently_change(self):
        d=sample();bad=copy.deepcopy(d)
        bad['records']['tasks'][-1]['workflow']['deliverable_phase']='prioritization'
        self.assertIn('TASK_DELIVERABLE_MUTATION',codes(bad,d))

    def test_store_commit_rejects_false_completion(self):
        d=sample()
        with tempfile.TemporaryDirectory() as td:
            store=CanonicalStore(Path(td)/'stages.sqlite')
            head=store.init(d,actor='test')
            base=store.head()
            fake=base['data'];fake['records']['tasks'][-1]['status']='completed'
            with self.assertRaises(StoreValidation):
                store.commit(fake,base['revision'],base['sha256'],'agent','fake completed')
            self.assertEqual(store.head()['revision'],1)

    def test_store_preserves_nonmatching_phases_in_history(self):
        d=sample()
        with tempfile.TemporaryDirectory() as td:
            store=CanonicalStore(Path(td)/'stages.sqlite')
            store.init(d,actor='test')
            h=store.head()
            after=set_task_phase(h['data'],'TASK-STAGE-NEW','prioritization','in_progress')
            store.commit(after,h['revision'],h['sha256'],'agent','prioritization only')
            self.assertTrue(store.verify()['ok'])
            self.assertEqual(store.snapshot_at(1)['records']['tasks'][-1]['workflow']['phases']['prioritization']['state'],'not_started')
            self.assertFalse(project_task(store.head()['data']['records']['tasks'][-1])['deliverable_complete'])

    def test_migrate_v14_preserves_unknown_phases(self):
        d=migrate_v14(LEGACY)
        self.assertEqual(d['records'],LEGACY['records'])
        self.assertEqual(d['_pes']['legacy_exceptions']['task_workflow_missing'],['TASK-DEMO-LEGACY-001'])
        self.assertEqual(d['_pes']['schema_revision'],'15.1.0')
        self.assertEqual(codes(d),set())

    def test_opt_in_copy_upgrade_from_15_0_does_not_invent_phase_state(self):
        legacy=copy.deepcopy(MIGRATED);legacy['_pes']['schema_revision']='15.0.0'
        legacy['_pes']['legacy_exceptions'].pop('task_workflow_missing')
        legacy['_pes'].update({
            'schema_digest':'fad97eb7073888eb08a644370d1fe4e22de41f0b3baf78d7d883909a2b562a45',
            'semantic_rules_digest':'467b7020d3bcc383243fc8b5d7e79c6716ca276f5b99642cf05dea497108a931',
            'compatibility_profile_digest':'8fc0e26a50ababa9688dbd1f406d3d1e6626c5b508da561cd3684e44ad6c9cd4',
        })
        before=copy.deepcopy(legacy)
        upgraded=upgrade_v15_0(legacy)
        self.assertEqual(legacy,before)
        self.assertEqual(upgraded['records'],legacy['records'])
        self.assertEqual(upgraded['_pes']['upgrade']['source_sha256'],digest(legacy))
        self.assertEqual(upgraded['_pes']['legacy_exceptions']['task_workflow_missing'],['TASK-DEMO-LEGACY-001'])
        self.assertEqual(codes(upgraded),set())

    def test_historical_completed_label_is_not_used_to_initialize_stages(self):
        from pes15.task_workflow import initialize_historical_workflow
        old=copy.deepcopy(MIGRATED);old['records']['tasks'][0]['status']='completed'
        initialized=initialize_historical_workflow(old,'TASK-DEMO-LEGACY-001','implementation')
        projected=project_task(initialized['records']['tasks'][0])
        self.assertIsNone(projected['deliverable_complete'])
        self.assertIsNone(projected['verification_passed'])
        self.assertIn('TASK_HISTORIC_STATUS_NOT_PROOF',codes(initialized,severity='warning'))
        self.assertNotIn('TASK_FALSE_COMPLETION',codes(initialized))

    def test_upgrade_rejects_unknown_15_0_digest(self):
        old=copy.deepcopy(MIGRATED)
        old['_pes']['schema_revision']='15.0.0'
        old['_pes']['schema_digest']='0'*64
        with self.assertRaisesRegex(MigrationError,'resource set'):
            upgrade_v15_0(old)

    def test_historical_initialization_keeps_all_phases_not_started(self):
        from pes15.task_workflow import initialize_historical_workflow
        old=copy.deepcopy(MIGRATED)
        new=initialize_historical_workflow(old,'TASK-DEMO-LEGACY-001','implementation')
        self.assertIn('TASK-DEMO-LEGACY-001',new['_pes']['legacy_exceptions']['task_workflow_missing'])
        self.assertIn('TASK-DEMO-LEGACY-001',old['_pes']['legacy_exceptions']['task_workflow_missing'])
        p=project_task(new['records']['tasks'][0])
        self.assertTrue(p['workflow_known'])
        self.assertIsNone(p['implementation_complete'])
        self.assertIsNone(p['verification_passed'])
        self.assertIsNone(p['owner_accepted'])
        self.assertEqual(codes(new,old),set())

    def test_reject_in_place_or_repeated_upgrade(self):
        with self.assertRaises(MigrationError):upgrade_v15_0(MIGRATED)

    def test_cli_task_status_unknown_for_historic_task(self):
        p=subprocess.run([sys.executable,'-m','pes15','task-status',str(ROOT/'examples/portfolio_builder_migrated_v15_demo.json'),
            '--task','TASK-DEMO-LEGACY-001'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads(p.stdout)
        self.assertIsNone(result['implementation_complete'])

    def test_cli_task_phase_creates_new_file_and_never_changes_source(self):
        with tempfile.TemporaryDirectory() as td:
            input_path=Path(td)/'input.json';output_path=Path(td)/'output.json'
            d=sample();input_path.write_text(json.dumps(d),encoding='utf-8');before=input_path.read_bytes()
            p=subprocess.run([sys.executable,'-m','pes15','task-phase',str(input_path),
                '--task','TASK-STAGE-NEW','--phase','implementation','--state','completed',
                '--source-revision-ref','git-sha-abc','--output',str(output_path)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(input_path.read_bytes(),before)
            self.assertTrue(project_task(json.loads(output_path.read_text(encoding='utf-8'))['records']['tasks'][-1])['implementation_complete'])

    def test_retrieval_reports_phase_projection_and_no_implicit_claim(self):
        d=sample();proof(d,'decisions','DEC-RANK','TASK-STAGE-NEW')
        out=set_task_phase(d,'TASK-STAGE-NEW','prioritization','completed',record_refs=['DEC-RANK'])
        projection=context(out,contract_id='RETRIEVAL-PES15-FULL')
        self.assertFalse(projection['task_progress']['TASK-STAGE-NEW']['deliverable_complete'])
        self.assertIn('PRIORITIZED_NOT_IMPLEMENTED',{w['code'] for w in projection['warnings']})

if __name__=='__main__': unittest.main()
