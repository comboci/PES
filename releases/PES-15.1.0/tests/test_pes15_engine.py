from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from jsonschema import Draft202012Validator
from pes15.core import blank_bootstrap, digest, load_schema, metadata, read_json, full_contract
from pes15.validation import validate, errors_only
from pes15.migration import migrate_v14, MigrationError
from pes15.retrieval import context, RetrievalError
from pes15.store import CanonicalStore, Conflict, StoreValidation, StoreError
from pes15.cli import write_new
from pes15.task_workflow import new_workflow

ROOT=Path(__file__).resolve().parents[1]
LEGACY=read_json(ROOT/'examples'/'portfolio_builder_legacy_v14_demo.json')
MIGRATED=read_json(ROOT/'examples'/'portfolio_builder_migrated_v15_demo.json')

def codes(obj,baseline=None,severity='error'):
    return {issue.code for issue in validate(obj,baseline) if issue.severity==severity}

def task(id,priority='P2'):
    r={'record_id':id,'title':'integration test','detail':'synthetic record for PES-15 tests',
       'scope_refs':['SC-STORAGE'],'status':'planned','workflow':new_workflow('implementation'),
       'provenance':{'type':'test_fixture','date':'2026-11-20'}}
    if priority is not None:r['priority']=priority
    return r

class SchemaTests(unittest.TestCase):
    def test_schema_is_valid_draft202012(self):
        Draft202012Validator.check_schema(load_schema())

    def test_bootstrap_valid(self):
        self.assertEqual(codes(blank_bootstrap()),set())

    def test_migrated_fixture_valid_with_warning(self):
        self.assertEqual(codes(MIGRATED),set())
        self.assertIn('LEGACY_UNKNOWN',codes(MIGRATED,severity='warning'))

    def test_all_fifteen_groups_require_record_objects(self):
        for group in MIGRATED['records']:
            with self.subTest(group=group):
                d=copy.deepcopy(MIGRATED);d['records'][group].append('broken')
                self.assertIn('SCHEMA',codes(d))

    def test_invalid_task_priority_rejected(self):
        d=copy.deepcopy(MIGRATED);d['records']['tasks'].append(task('TASK-NEW',priority='P99'))
        self.assertTrue({'TASK_PRIORITY','SCHEMA'} & codes(d))

    def test_missing_new_task_priority_rejected_without_baseline(self):
        d=copy.deepcopy(MIGRATED);d['records']['tasks'].append(task('TASK-NEW',priority=None))
        self.assertIn('TASK_PRIORITY',codes(d))

    def test_missing_new_observation_timestamp_rejected(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['observations'].append({'record_id':'OBS-NEW','title':'New observation','detail':'No timestamp','status':'recorded','provenance':{'type':'test'}})
        self.assertIn('OBSERVATION_TIME',codes(d))

    def test_new_observation_with_timezone_valid(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['observations'].append({'record_id':'OBS-NEW','title':'New observation','detail':'Timestamp present',
            'observed_at':'2026-11-20T10:00:00+03:30','status':'recorded','provenance':{'type':'test'}})
        self.assertNotIn('OBSERVATION_TIME',codes(d))

    def test_naive_observation_timestamp_rejected(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['observations'].append({'record_id':'OBS-NEW','title':'New observation','detail':'Naive timestamp',
            'observed_at':'2026-11-20T10:00:00','status':'recorded','provenance':{'type':'test'}})
        self.assertIn('TIMEZONE',codes(d))

    def test_observation_reverse_interval_rejected(self):
        d=copy.deepcopy(MIGRATED);r=copy.deepcopy(d['records']['observations'][0]);r['record_id']='OBS-NEW'
        r['observed_at']='2026-11-20T08:00:00Z';r['valid_from']='2026-11-22T08:00:00Z';r['valid_until']='2026-11-21T08:00:00Z'
        d['records']['observations'].append(r)
        self.assertIn('INVALID_TIME_INTERVAL',codes(d))

    def test_duplicate_id_across_types_rejected(self):
        d=copy.deepcopy(MIGRATED);r=task('DEC-001');d['records']['tasks'].append(r)
        self.assertIn('DUPLICATE_ID',codes(d))

    def test_duplicate_id_across_scope_record_rejected(self):
        d=copy.deepcopy(MIGRATED);d['scopes'][0]['scope_id']='DEC-001'
        self.assertIn('DUPLICATE_ID',codes(d))

    def test_bad_scope_ref_rejected(self):
        d=copy.deepcopy(MIGRATED);d['records']['decisions'][0]['scope_refs']=['MISSING-SCOPE']
        self.assertIn('DANGLING_REF',codes(d))

    def test_bad_related_record_ref_rejected(self):
        d=copy.deepcopy(MIGRATED);d['records']['decisions'][0]['related_record_ids']=['DEC-404']
        self.assertIn('DANGLING_REF',codes(d))

    def test_good_related_record_ref(self):
        d=copy.deepcopy(MIGRATED);d['records']['decisions'][0]['related_record_ids']=['ST-001']
        self.assertNotIn('DANGLING_REF',codes(d))

    def test_scope_parent_cycle_rejected(self):
        d=copy.deepcopy(MIGRATED);d['scopes'][0]['parent_scope_ref']='SC-STORAGE';d['scopes'][4]['parent_scope_ref']='SC-PROJECTS'
        self.assertIn('SCOPE_CYCLE',codes(d))

    def test_missing_default_contract_rejected(self):
        d=copy.deepcopy(MIGRATED);d['retrieval']['default_contract_ref']='NOPE'
        self.assertIn('RETRIEVAL_DEFAULT',codes(d))

    def test_unknown_contract_scope_rejected(self):
        d=copy.deepcopy(MIGRATED);d['retrieval']['contracts'][0]['subject_scope_refs']=['BAD']
        self.assertIn('RETRIEVAL_SCOPE',codes(d))

    def test_open_state_wrong_type_rejected(self):
        d=copy.deepcopy(MIGRATED);d['open_state']['next_work_record_ids']=['DEC-001']
        self.assertIn('OPEN_STATE_REF',codes(d))

    def test_open_state_wrong_field_type_rejected(self):
        d=copy.deepcopy(MIGRATED);d['open_state']['open_question_ids']='Q-001'
        self.assertIn('OPEN_STATE_TYPE',codes(d))

    def test_typed_relationship_valid(self):
        d=copy.deepcopy(MIGRATED)
        d['relationships']=[{'relationship_id':'REL-NEW','source_ref':'DEC-001','target_ref':'ST-001','relation_type':'supports','status':'active'}]
        self.assertEqual(codes(d),set())

    def test_typed_relationship_bad_ref(self):
        d=copy.deepcopy(MIGRATED)
        d['relationships']=[{'relationship_id':'REL-NEW','source_ref':'DEC-001','target_ref':'missing','relation_type':'supports','status':'active'}]
        self.assertIn('DANGLING_RELATION',codes(d))

    def test_untyped_new_relationship_rejected(self):
        d=copy.deepcopy(MIGRATED);d['relationships']=[{'foo':'bar'}]
        self.assertIn('RELATIONSHIP_TYPE',codes(d))

    def test_relationship_self_cycle_rejected(self):
        d=copy.deepcopy(MIGRATED)
        d['relationships']=[{'relationship_id':'REL-NEW','source_ref':'DEC-001','target_ref':'DEC-001','relation_type':'supports','status':'active'}]
        self.assertIn('SELF_RELATION',codes(d))

    def test_wrong_metadata_digest_rejected(self):
        d=copy.deepcopy(MIGRATED);d['_pes']['schema_digest']='0'*64
        self.assertIn('RESOURCE_DIGEST',codes(d))

    def test_provenance_missing_rejected(self):
        d=copy.deepcopy(MIGRATED);d['records']['statements'][0].pop('provenance')
        self.assertIn('SCHEMA',codes(d))

    def test_secret_material_rejected(self):
        d=copy.deepcopy(MIGRATED);d['records']['statements'][0]['private_key']='-----BEGIN RSA PRIVATE KEY-----fake'
        self.assertIn('SECRET_VALUE',codes(d))

    def test_absence_of_owner_acceptance_is_warning_not_success(self):
        result=context(MIGRATED,contract_id='RETRIEVAL-PES15-FULL')
        self.assertIn('NO_OWNER_ACCEPTANCE_EVIDENCE',{w['code'] for w in result['warnings']})

    def test_baseline_deletion_rejected(self):
        d=copy.deepcopy(MIGRATED);d['records']['decisions']=[]
        self.assertIn('HISTORY_DELETION',codes(d,MIGRATED))

    def test_baseline_scope_deletion_rejected(self):
        d=copy.deepcopy(MIGRATED);d['scopes'].pop(4)
        self.assertIn('HISTORY_DELETION',codes(d,MIGRATED))

    def test_legacy_exception_cannot_expand(self):
        d=copy.deepcopy(MIGRATED);d['records']['tasks'].append(task('TASK-NEW',None))
        d['_pes']['legacy_exceptions']['task_priority_missing'].append('TASK-NEW')
        self.assertIn('LEGACY_EXCEPTION_EXPANSION',codes(d,MIGRATED))

    def test_legacy_exception_requires_migration(self):
        d=copy.deepcopy(MIGRATED);d['_pes'].pop('migration')
        self.assertIn('LEGACY_NOT_MIGRATED',codes(d))

    def test_historical_exception_can_be_resolved(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['tasks'][0]['priority']='unassigned'
        d['_pes']['legacy_exceptions']['task_priority_missing']=[]
        self.assertNotIn('LEGACY_EXCEPTION_EXPANSION',codes(d,MIGRATED))
        self.assertNotIn('TASK_PRIORITY',codes(d))

class MigrationTests(unittest.TestCase):
    def test_source_not_mutated(self):
        source=copy.deepcopy(LEGACY);before=digest(source)
        target=migrate_v14(source)
        self.assertEqual(digest(source),before)
        self.assertEqual(source['_pes']['standard'],'PES-14')
        self.assertEqual(target['_pes']['standard'],'PES-15')
        self.assertEqual(target['_pes']['migration']['source_sha256'],before)

    def test_record_semantics_preserved(self):
        target=migrate_v14(LEGACY)
        self.assertEqual(target['records'],LEGACY['records'])
        self.assertEqual(target['scopes'],LEGACY['scopes'])
        self.assertEqual(target['relationships'],LEGACY['relationships'])
        self.assertEqual(target['open_state'],LEGACY['open_state'])
        self.assertEqual(target['retrieval']['default_contract_ref'],LEGACY['retrieval']['default_contract_ref'])
        self.assertIn('RETRIEVAL-PES15-FULL',[r['contract_id'] for r in target['retrieval']['contracts']])

    def test_missing_history_remains_unknown(self):
        result=migrate_v14(LEGACY)
        self.assertEqual(result['_pes']['legacy_exceptions']['task_priority_missing'],['TASK-DEMO-LEGACY-001'])
        self.assertEqual(result['_pes']['legacy_exceptions']['observation_time_missing'],['OBS-001'])
        self.assertNotIn('priority',result['records']['tasks'][0])
        self.assertNotIn('observed_at',result['records']['observations'][0])

    def test_idempotent_deterministic(self):
        self.assertEqual(digest(migrate_v14(LEGACY)),digest(migrate_v14(LEGACY)))

    def test_v15_cannot_migrate_again(self):
        with self.assertRaises(MigrationError):migrate_v14(MIGRATED)

    def test_legacy_untyped_relation_grandfathered(self):
        legacy=copy.deepcopy(LEGACY);legacy['relationships']=[{'old':'untyped relation','note':'history only'}]
        result=migrate_v14(legacy)
        self.assertEqual(result['relationships'],legacy['relationships'])
        self.assertEqual(result['_pes']['legacy_exceptions']['relationship_legacy_indices'],[0])
        self.assertNotIn('RELATIONSHIP_TYPE',codes(result))
        change=copy.deepcopy(result);change['relationships'][0]['old']='tampered'
        self.assertIn('LEGACY_RELATIONSHIP_MUTATION',codes(change,result))

    def test_malformed_source_fails_without_fabrication(self):
        legacy=copy.deepcopy(LEGACY);del legacy['records']['tasks']
        with self.assertRaises(MigrationError):migrate_v14(legacy)

class RetrievalTests(unittest.TestCase):
    def test_scope_filter(self):
        result=context(MIGRATED,scope='SC-STORAGE',contract_id='RETRIEVAL-PES15-FULL')
        self.assertEqual({x['record_id'] for x in result['records']['solutions']},{'SOL-001'})
        self.assertEqual(result['records']['decisions'],[])

    def test_old_contract_is_explicitly_incomplete(self):
        result=context(MIGRATED,scope='SC-PROJECTS',contract_id='RETRIEVAL-DEFAULT')
        self.assertIn('CONTRACT_EXCLUDES_RECORDS',{w['code'] for w in result['warnings']})
        self.assertEqual(result['records']['statements'],[])

    def test_full_contract_keeps_provenance(self):
        result=context(MIGRATED,scope='SC-PROJECTS',contract_id='RETRIEVAL-PES15-FULL')
        self.assertEqual(result['records']['statements'][0]['record_id'],'ST-001')
        self.assertTrue(any(x['record_id']=='DEC-001' and x['provenance']['type']=='user_conversation' for x in result['traceability']))
        self.assertFalse(result['claim_of_live_source_alignment'])

    def test_unknown_scope_fails(self):
        with self.assertRaises(RetrievalError):context(MIGRATED,scope='SC-DOES-NOT-EXIST')

    def test_source_alignment_not_falsely_verified(self):
        result=context(MIGRATED,contract_id='RETRIEVAL-PES15-FULL')
        self.assertIn('UNVERIFIED_SOURCE_ALIGNMENT',{w['code'] for w in result['warnings']})

    def test_current_only_filters_only_explicitly_retired(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['decisions'][0]['status']='retired'
        c=d['retrieval']['contracts'][-1]
        c['current_only']=True
        result=context(d,contract_id=c['contract_id'])
        self.assertEqual(result['records']['decisions'],[])

    def test_relation_expansion(self):
        d=copy.deepcopy(MIGRATED)
        d['relationships']=[{'relationship_id':'REL-TEST','source_ref':'DEC-001','target_ref':'SOL-001','relation_type':'supports','status':'active'}]
        result=context(d,scope='SC-PROJECTS',contract_id='RETRIEVAL-PES15-FULL')
        self.assertIn('SOL-001',{r['record_id'] for r in result['records']['solutions']})

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'pes15.sqlite'
        self.store=CanonicalStore(self.db)
        self.first=self.store.init(copy.deepcopy(MIGRATED),actor='test')

    def tearDown(self):self.tmp.cleanup()

    def test_initialize_does_not_overwrite_existing(self):
        with self.assertRaises(StoreError):self.store.init(MIGRATED,actor='test')

    def test_init_rejects_bootstrap_and_creates_no_store(self):
        path=Path(self.tmp.name)/'second.sqlite'
        with self.assertRaises(StoreValidation):CanonicalStore(path).init(blank_bootstrap(),actor='test')
        self.assertFalse(path.exists())

    def test_read_head(self):
        h=self.store.head()
        self.assertEqual(h['revision'],1)
        self.assertEqual(h['sha256'],digest(MIGRATED))

    def test_successful_commit_and_history(self):
        h=self.store.head();d=h['data'];d['records']['tasks'].append(task('TASK-NEW'))
        entry=self.store.commit(d,h['revision'],h['sha256'],'agent-a','plan task')
        self.assertEqual(entry['revision'],2)
        self.assertEqual(self.store.head()['data']['records']['tasks'][-1]['record_id'],'TASK-NEW')
        self.assertEqual(self.store.snapshot_at(1)['records']['tasks'],MIGRATED['records']['tasks'])
        self.assertTrue(self.store.verify()['ok'])
        self.assertEqual(len(self.store.history()),2)

    def test_stale_write_rejected_and_original_kept(self):
        old=self.store.head()
        a=copy.deepcopy(old['data']);b=copy.deepcopy(old['data'])
        a['records']['tasks'].append(task('TASK-A'));b['records']['tasks'].append(task('TASK-B'))
        self.store.commit(a,old['revision'],old['sha256'],'A','new A')
        with self.assertRaises(Conflict):self.store.commit(b,old['revision'],old['sha256'],'B','new B')
        self.assertNotIn('TASK-B',{r['record_id'] for r in self.store.head()['data']['records']['tasks']})

    def test_delete_historic_record_rejected(self):
        h=self.store.head();h['data']['records']['decisions']=[]
        with self.assertRaises(StoreValidation):self.store.commit(h['data'],h['revision'],h['sha256'],'test','bad delete')
        self.assertEqual(self.store.head()['revision'],1)

    def test_concurrent_threads_exactly_one_commit(self):
        h=self.store.head();barrier=threading.Barrier(2);results=[];rlock=threading.Lock()
        def worker(name):
            data=copy.deepcopy(h['data']);data['records']['tasks'].append(task('TASK-'+name))
            barrier.wait()
            try:
                self.store.commit(data,h['revision'],h['sha256'],name,'parallel test')
                result='ok'
            except Conflict:result='conflict'
            with rlock:results.append(result)
        a=threading.Thread(target=worker,args=('A',));b=threading.Thread(target=worker,args=('B',))
        a.start();b.start();a.join(timeout=15);b.join(timeout=15)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(sorted(results),['conflict','ok'])
        self.assertEqual(self.store.head()['revision'],2)
        self.assertTrue(self.store.verify()['ok'])

    def test_history_tampering_detected(self):
        con=sqlite3.connect(self.db)
        con.execute('UPDATE history SET data=? WHERE revision=1',('{}',))
        con.commit();con.close()
        self.assertFalse(self.store.verify()['ok'])
        with self.assertRaises(StoreError):self.store.head()

class CLITests(unittest.TestCase):
    def test_no_clobber_output(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/'out.json'
            write_new(dest,MIGRATED)
            before=dest.read_bytes()
            with self.assertRaises(FileExistsError):write_new(dest,LEGACY)
            self.assertEqual(dest.read_bytes(),before)

    def test_cli_validate_and_migrate(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/'new-v15.json'
            p=subprocess.run([sys.executable,'-m','pes15','migrate',str(ROOT/'examples'/'portfolio_builder_legacy_v14_demo.json'),
                '--output',str(dest)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([sys.executable,'-m','pes15','validate',str(dest)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('PASS:',p.stdout)

    def test_cli_cannot_migrate_in_place(self):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/'old.json';source.write_text(json.dumps(LEGACY),encoding='utf-8')
            p=subprocess.run([sys.executable,'-m','pes15','migrate',str(source),'--output',str(source)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,2)
            self.assertEqual(read_json(source),LEGACY)

if __name__=='__main__':unittest.main()

# Explicitly add external-reference regression coverage independently of unittest discovery ordering.
class ExternalRelationTests(unittest.TestCase):
    def test_external_ref_is_typed_and_warned_not_assumed_verified(self):
        d=copy.deepcopy(MIGRATED)
        d['relationships']=[{'relationship_id':'REL-EXT-1','source_ref':'DEC-001',
            'target_external_ref':{'namespace':'github','object_id':'comboci/NSP-Portfolio-Builder#main',
                'source_uri':'https://github.com/comboci/NSP-Portfolio-Builder'},
            'relation_type':'relates_to','status':'active'}]
        self.assertEqual(codes(d),set())
        self.assertIn('EXTERNAL_REF_UNVERIFIED',codes(d,severity='warning'))
        self.assertIn('EXTERNAL_RELATION_UNVERIFIED',{w['code'] for w in context(d)['warnings']})

    def test_external_target_requires_full_declaration(self):
        d=copy.deepcopy(MIGRATED)
        d['relationships']=[{'relationship_id':'REL-EXT-1','source_ref':'DEC-001',
            'target_external_ref':{'object_id':'only-id'},'relation_type':'supports','status':'active'}]
        self.assertIn('RELATIONSHIP_TYPE',codes(d))

    def test_cannot_combine_external_and_local_target(self):
        d=copy.deepcopy(MIGRATED)
        d['relationships']=[{'relationship_id':'REL-EXT-1','source_ref':'DEC-001','target_ref':'ST-001',
            'target_external_ref':{'namespace':'github','object_id':'abc'},'relation_type':'supports','status':'active'}]
        self.assertIn('RELATIONSHIP_TYPE',codes(d))

    def test_migration_metadata_immutable_during_commit(self):
        d=copy.deepcopy(MIGRATED)
        d['_pes']['migration']['source_sha256']='f'*64
        self.assertIn('MIGRATION_PROVENANCE_MUTATION',codes(d,MIGRATED))

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'canonical.sqlite'
        self.backup=Path(self.tmp.name)/'backup.sqlite'
        self.store=CanonicalStore(self.db)
        self.store.init(copy.deepcopy(MIGRATED),actor='test')
    def tearDown(self):self.tmp.cleanup()

    def test_consistent_online_backup(self):
        h=self.store.head();candidate=h['data'];candidate['records']['tasks'].append(task('TASK-BACKUP'))
        self.store.commit(candidate,h['revision'],h['sha256'],'test','pre-backup change')
        result=self.store.backup(self.backup)
        self.assertTrue(self.backup.is_file())
        self.assertEqual(result['revisions'],2)
        recovered=CanonicalStore(self.backup)
        self.assertTrue(recovered.verify()['ok'])
        self.assertEqual(recovered.head()['data'],self.store.head()['data'])
        self.assertEqual(recovered.history(),self.store.history())

    def test_backup_never_overwrites(self):
        self.store.backup(self.backup)
        before=self.backup.read_bytes()
        with self.assertRaises(StoreError):self.store.backup(self.backup)
        self.assertEqual(self.backup.read_bytes(),before)
        with self.assertRaises(StoreError):self.store.backup(self.db)

    def test_backup_refuses_corrupted_store(self):
        con=sqlite3.connect(self.db)
        con.execute('UPDATE history SET sha256=? WHERE revision=1',('0'*64,))
        con.commit();con.close()
        with self.assertRaises(StoreError):self.store.backup(self.backup)
        self.assertFalse(self.backup.exists())

class SemanticStateTests(unittest.TestCase):
    def test_selected_solution_requires_attributable_decision(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['solutions'][0]['status']='selected'
        self.assertIn('SOLUTION_WITHOUT_DECISION',codes(d))
        d['records']['solutions'][0]['related_record_ids']=['DEC-001']
        self.assertNotIn('SOLUTION_WITHOUT_DECISION',codes(d))

    def test_verification_without_subject_rejected(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['verifications']=[{'record_id':'VER-001','title':'Verified syntax','detail':'Test only','status':'passed','provenance':{'type':'test'}}]
        self.assertIn('UNLINKED_VERIFICATION_ACCEPTANCE',codes(d))
        d['records']['verifications'][0]['related_record_ids']=['SOL-001']
        self.assertNotIn('UNLINKED_VERIFICATION_ACCEPTANCE',codes(d))

    def test_acceptance_without_subject_rejected(self):
        d=copy.deepcopy(MIGRATED)
        d['records']['acceptances']=[{'record_id':'ACC-001','title':'Owner acceptance','detail':'Test only','status':'accepted','provenance':{'type':'test'}}]
        self.assertIn('UNLINKED_VERIFICATION_ACCEPTANCE',codes(d))
        d['records']['acceptances'][0]['related_record_ids']=['TASK-DEMO-LEGACY-001']
        self.assertNotIn('UNLINKED_VERIFICATION_ACCEPTANCE',codes(d))

class DurabilityAndProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'canonical.sqlite'
        self.store=CanonicalStore(self.db)
        self.store.init(copy.deepcopy(MIGRATED),actor='test')
    def tearDown(self):self.tmp.cleanup()

    def test_two_independent_python_processes_one_wins(self):
        h=self.store.head()
        files=[]
        for letter in 'AB':
            d=copy.deepcopy(h['data']);d['records']['tasks'].append(task('TASK-PROC-'+letter))
            f=Path(self.tmp.name)/('candidate-'+letter+'.json')
            f.write_text(json.dumps(d),encoding='utf-8');files.append(f)
        workers=[]
        for letter,f in zip('AB',files):
            workers.append(subprocess.Popen([sys.executable,'-m','pes15','commit',str(f),'--db',str(self.db),
                '--expected-rev',str(h['revision']),'--expected-sha',h['sha256'],'--actor',letter,
                '--reason','process CAS regression'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        result=[p.communicate(timeout=20) for p in workers]
        return_codes=sorted(p.returncode for p in workers)
        self.assertEqual(return_codes,[0,2],result)
        self.assertTrue(self.store.verify()['ok'])
        self.assertEqual(self.store.head()['revision'],2)

    def test_abrupt_process_exit_rolls_back_uncommitted_transaction(self):
        code=("import sqlite3,os,sys; c=sqlite3.connect(sys.argv[1],isolation_level=None); "
              "c.execute('BEGIN IMMEDIATE'); "
              "c.execute(\"UPDATE head SET revision=999 WHERE name='canonical'\"); os._exit(0)")
        p=subprocess.run([sys.executable,'-c',code,str(self.db)],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(self.store.head()['revision'],1)
        self.assertTrue(self.store.verify()['ok'])

    def test_eight_concurrent_writers_only_one_wins(self):
        h=self.store.head();barrier=threading.Barrier(8);out=[];lock=threading.Lock()
        def run(n):
            d=copy.deepcopy(h['data']);d['records']['tasks'].append(task('TASK-WORKER-'+str(n)))
            barrier.wait(timeout=15)
            try:self.store.commit(d,h['revision'],h['sha256'],'worker-'+str(n),'stress CAS');v='ok'
            except Conflict:v='conflict'
            with lock:out.append(v)
        workers=[threading.Thread(target=run,args=(n,)) for n in range(8)]
        for w in workers:w.start()
        for w in workers:w.join(timeout=30)
        self.assertFalse(any(w.is_alive() for w in workers))
        self.assertEqual(out.count('ok'),1)
        self.assertEqual(out.count('conflict'),7)
        self.assertEqual(self.store.head()['revision'],2)
        self.assertTrue(self.store.verify()['ok'])

class ReleasePackagingTests(unittest.TestCase):
    def test_manifest_hashes(self):
        manifest=read_json(ROOT/'PES-15.package-manifest.json')
        self.assertEqual(manifest['standard'],'PES-15')
        for item in manifest['files']:
            with self.subTest(path=item['path']):
                data=(ROOT/item['path']).read_bytes()
                self.assertEqual(len(data),item['size_bytes'])
                import hashlib
                self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])

    def test_no_pes14_original_modified_by_reference_implementation(self):
        import hashlib
        original=ROOT.parent/'PES-14-Portable-Starter-Pack.zip'
        # This assertion is only meaningful in the evaluation workspace where source ZIP is mounted.
        if original.is_file():
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                '1a25c34d07c3548c70078a050a4ded130d25e7f252536fe0c6159fca3118732e')
