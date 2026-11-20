"""Windows/Linux command line interface for PES-15."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from .core import blank_bootstrap, dumps, read_json
from .migration import migrate_v14, upgrade_v15_0, MigrationError
from .task_workflow import project_task, set_task_phase, initialize_historical_workflow
from .validation import validate, errors_only
from .retrieval import context, RetrievalError
from .store import CanonicalStore, Conflict, StoreError, StoreValidation


def write_new(path: Path, obj):
    """No-clobber atomic publish: flush temp, then create hard link; never overwrite."""
    path=path.resolve()
    if path.exists():raise FileExistsError(f'{path} already exists; use a NEW output path (no force overwrite)')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
            f.write(dumps(obj));f.flush();os.fsync(f.fileno())
        # link is an atomic no-overwrite publish on POSIX and NTFS; unsupported FS fails closed.
        os.link(name,path)
        if os.name=='posix':
            dir_fd=os.open(str(path.parent),os.O_RDONLY)
            try:os.fsync(dir_fd)
            finally:os.close(dir_fd)
    finally:
        try:os.unlink(name)
        except FileNotFoundError:pass


def build_parser():
    ap=argparse.ArgumentParser(prog='pes15',description='PES-15 reference engine; never changes PES-14 in place')
    sub=ap.add_subparsers(dest='cmd',required=True)
    def p(name,help):return sub.add_parser(name,help=help)
    x=p('init-bootstrap','create an empty PES-15 Bootstrap template (not canonical)');x.add_argument('--output',required=True,type=Path)
    x=p('validate','validate a PES-15 JSON file; warnings are not failures');x.add_argument('file',type=Path);x.add_argument('--baseline',type=Path);x.add_argument('--json',action='store_true')
    x=p('migrate','opt-in copy migration from PES-14 to a separate PES-15 file');x.add_argument('source',type=Path);x.add_argument('--output',required=True,type=Path)
    x=p('upgrade-v15','opt-in NEW-copy PES-15.0.0 to PES-15.1.0');x.add_argument('source',type=Path);x.add_argument('--output',required=True,type=Path)
    x=p('task-workflow-init','create an explicit EMPTY workflow for one historical task');x.add_argument('source',type=Path);x.add_argument('--task',required=True);x.add_argument('--deliverable-phase',required=True);x.add_argument('--output',required=True,type=Path)
    x=p('task-status','read independent stages and deliverable completion for a task');x.add_argument('source',type=Path);x.add_argument('--task',required=True)
    x=p('task-phase','prepare a new isolated snapshot with ONE changed phase, not a canonical store write');x.add_argument('source',type=Path);x.add_argument('--task',required=True);x.add_argument('--phase',required=True);x.add_argument('--state',required=True);x.add_argument('--record-ref',action='append',default=[]);x.add_argument('--source-revision-ref',action='append',default=[]);x.add_argument('--reopen-reason');x.add_argument('--output',required=True,type=Path)
    x=p('retrieve','build traceable read-only context from a PES-15 snapshot');x.add_argument('file',type=Path);x.add_argument('--scope');x.add_argument('--contract');x.add_argument('--output',type=Path)
    x=p('store-init','create a NEW SQLite store from validated canonical snapshot');x.add_argument('file',type=Path);x.add_argument('--db',required=True,type=Path);x.add_argument('--actor',required=True)
    x=p('head','show current store revision, SHA and snapshot');x.add_argument('--db',required=True,type=Path);x.add_argument('--full',action='store_true')
    x=p('commit','atomic compare-and-swap commit; both revision and SHA required');x.add_argument('file',type=Path);x.add_argument('--db',required=True,type=Path);x.add_argument('--expected-rev',type=int,required=True);x.add_argument('--expected-sha',required=True);x.add_argument('--actor',required=True);x.add_argument('--reason',required=True)
    x=p('history','list append-only revisions');x.add_argument('--db',required=True,type=Path)
    x=p('verify-store','verify SQLite integrity and full event SHA chain');x.add_argument('--db',required=True,type=Path)
    x=p('export','export stored revision to NEW JSON file, never overwrite');x.add_argument('--db',required=True,type=Path);x.add_argument('--revision',type=int);x.add_argument('--output',required=True,type=Path)
    x=p('store-backup','create a verified no-overwrite online SQLite backup');x.add_argument('--db',required=True,type=Path);x.add_argument('--output',required=True,type=Path)
    x=p('verify-package','check included package manifest digests')
    return ap


def main(argv=None):
    args=build_parser().parse_args(argv)
    try:
        if args.cmd=='init-bootstrap':
            write_new(args.output,blank_bootstrap());print(f'PES-15 bootstrap created: {args.output}')
        elif args.cmd=='validate':
            issues=validate(read_json(args.file),read_json(args.baseline) if args.baseline else None)
            if args.json:print(json.dumps({'valid':not errors_only(issues),'issues':[x.to_dict() for x in issues]},ensure_ascii=False,indent=2))
            else:
                for issue in issues:print(f'{issue.severity.upper()} {issue.code} {issue.path}: {issue.message}')
                print(f'{"PASS" if not errors_only(issues) else "FAIL"}: {sum(x.severity=="error" for x in issues)} error(s), {sum(x.severity=="warning" for x in issues)} warning(s)')
            return 1 if errors_only(issues) else 0
        elif args.cmd=='migrate':
            if args.source.resolve()==args.output.resolve():raise ValueError('source and output cannot be the same file')
            migrated=migrate_v14(read_json(args.source))
            write_new(args.output,migrated)
            print(f'PES-15 copy migration complete: {args.output}; source PES-14 unchanged; check legacy warning list')
        elif args.cmd=='upgrade-v15':
            if args.source.resolve()==args.output.resolve():raise ValueError('source and output cannot be the same file')
            write_new(args.output,upgrade_v15_0(read_json(args.source)))
            print(f'PES-15.1.0 copy upgrade created: {args.output}; PES-15.0.0 original unchanged')
        elif args.cmd=='task-workflow-init':
            if args.source.resolve()==args.output.resolve():raise ValueError('source and output cannot be the same file')
            new=initialize_historical_workflow(read_json(args.source),args.task,args.deliverable_phase)
            write_new(args.output,new)
            print(f'PES-15 historical workflow initialized with all phases unknown/not started: {args.output}')
        elif args.cmd=='task-status':
            snapshot=read_json(args.source)
            matching=[r for r in snapshot['records']['tasks'] if r.get('record_id')==args.task]
            if len(matching)!=1:raise ValueError('task not found or duplicate')
            print(dumps(project_task(matching[0])),end='')
        elif args.cmd=='task-phase':
            if args.source.resolve()==args.output.resolve():raise ValueError('source and output cannot be the same file')
            new=set_task_phase(read_json(args.source),args.task,args.phase,args.state,
                record_refs=args.record_ref,source_revision_refs=args.source_revision_ref,
                reopen_reason=args.reopen_reason)
            write_new(args.output,new)
            print(f'PES-15 isolated phase change prepared: {args.output}; canonical store unchanged')
        elif args.cmd=='retrieve':
            result=context(read_json(args.file),scope=args.scope,contract_id=args.contract)
            if args.output:write_new(args.output,result);print(f'PES-15 context created: {args.output}')
            else:print(dumps(result),end='')
        elif args.cmd=='store-init':
            result=CanonicalStore(args.db).init(read_json(args.file),actor=args.actor)
            print(dumps(result),end='')
        elif args.cmd=='head':
            h=CanonicalStore(args.db).head()
            if not args.full:h={k:v for k,v in h.items() if k!='data'}
            print(dumps(h),end='')
        elif args.cmd=='commit':
            result=CanonicalStore(args.db).commit(read_json(args.file),args.expected_rev,args.expected_sha,args.actor,args.reason)
            print(dumps(result),end='')
        elif args.cmd=='history':print(dumps(CanonicalStore(args.db).history()),end='')
        elif args.cmd=='verify-store':
            result=CanonicalStore(args.db).verify();print(dumps(result),end='')
            return 0 if result['ok'] else 1
        elif args.cmd=='export':
            store=CanonicalStore(args.db)
            data=store.snapshot_at(args.revision) if args.revision else store.head()['data']
            write_new(args.output,data)
            print(f'exported read-only snapshot: {args.output}')
        elif args.cmd=='store-backup':
            print(dumps(CanonicalStore(args.db).backup(args.output)),end='')
        elif args.cmd=='verify-package':
            root=Path(__file__).resolve().parents[1]
            manifest=read_json(root/'PES-15.package-manifest.json')
            from .core import file_sha256
            problems=[]
            for item in manifest['files']:
                path=root/item['path']
                if not path.is_file() or path.stat().st_size!=item['size_bytes'] or file_sha256(path)!=item['sha256']:
                    problems.append(item['path'])
            if problems:
                print('FAIL manifest mismatch:',', '.join(problems));return 1
            print(f'PASS package manifest: {len(manifest["files"])} files')
        return 0
    except (OSError,ValueError,TypeError,KeyError,MigrationError,RetrievalError,StoreError) as e:
        print(f'ERROR {type(e).__name__}: {e}',file=sys.stderr)
        return 2
