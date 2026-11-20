"""SQLite append-only revision history with atomic compare-and-swap writes.

The DB lives alongside (not inside) a PES-14 project. Writers must present both
expected revision and expected SHA. No force-overwrite option is exposed.
"""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import os
import tempfile
import hashlib
from datetime import datetime, timezone
from contextlib import contextmanager
from .core import canonical_bytes, digest
from .validation import validate, errors_only

class StoreError(RuntimeError):pass
class Conflict(StoreError):pass
class StoreValidation(StoreError):pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


class CanonicalStore:
    def __init__(self, path: str|Path):
        self.path=Path(path).resolve()

    def _connect(self):
        if not self.path.is_file():
            raise StoreError(f'store not found: {self.path}; run store-init first')
        db=sqlite3.connect(str(self.path), timeout=15, isolation_level=None)
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        db.row_factory=sqlite3.Row
        return db

    @contextmanager
    def connection(self):
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    def init(self, snapshot:dict, actor:str, reason:str='initialize PES-15 canonical store'):
        if not actor.strip() or not reason.strip():raise StoreError('actor and reason required')
        issues=errors_only(validate(snapshot))
        if issues:raise StoreValidation(f'cannot initialize invalid PES-15 snapshot: {issues[0].code} {issues[0].path}: {issues[0].message}')
        if snapshot['artifact']['profile']!='canonical_snapshot':
            raise StoreValidation('bootstrap_template cannot become canonical without explicit project identity and canonical_snapshot artifact')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.exists():
            raise StoreError('destination path already exists; refusing to initialize/overwrite a legacy or existing DB')
        db=sqlite3.connect(str(self.path),timeout=15,isolation_level=None)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS head (name TEXT PRIMARY KEY CHECK(name="canonical"), revision INTEGER NOT NULL, sha256 TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS history (revision INTEGER PRIMARY KEY, sha256 TEXT NOT NULL, parent_event_hash TEXT, event_hash TEXT NOT NULL UNIQUE, data TEXT NOT NULL, created_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL)')
            entry=self._append(db,snapshot,1,None,actor,reason)
            db.execute('INSERT INTO head(name,revision,sha256) VALUES ("canonical",?,?)',(entry['revision'],entry['sha256']))
            db.commit()
            return entry
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _append(db, snapshot, revision, parent_event_hash,actor,reason):
        data=canonical_bytes(snapshot).decode('utf-8')
        sha=digest(snapshot)
        created=_now()
        event={'revision':revision,'snapshot_sha256':sha,'parent_event_hash':parent_event_hash,
               'created_at':created,'actor':actor,'reason':reason}
        event_hash=digest(event)
        db.execute('INSERT INTO history(revision,sha256,parent_event_hash,event_hash,data,created_at,actor,reason) VALUES(?,?,?,?,?,?,?,?)',
                   (revision,sha,parent_event_hash,event_hash,data,created,actor,reason))
        return {'revision':revision,'sha256':sha,'event_hash':event_hash,'actor':actor,'created_at':created,'reason':reason}

    @staticmethod
    def _current(db):
        row=db.execute('SELECT h.revision,h.sha256,a.event_hash,a.data FROM head h JOIN history a ON h.revision=a.revision WHERE h.name="canonical"').fetchone()
        if row is None:raise StoreError('store missing canonical head; do not write until repaired')
        value=json.loads(row['data'])
        if digest(value)!=row['sha256']:
            raise StoreError('canonical snapshot SHA mismatch: possible corruption; refusing to use data')
        return row,value

    def head(self):
        with self.connection() as db:
            row,data=self._current(db)
            return {'revision':row['revision'],'sha256':row['sha256'],'event_hash':row['event_hash'],'data':data}

    def commit(self,snapshot:dict,expected_revision:int,expected_sha256:str,actor:str,reason:str):
        if type(expected_revision) is not int or expected_revision<1 or not isinstance(expected_sha256,str):
            raise StoreError('expected_revision (integer) and expected_sha256 (string) are both required')
        if not actor.strip() or not reason.strip():raise StoreError('actor and reason are mandatory for audit trail')
        with self.connection() as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                row,current=self._current(db)
                if row['revision']!=expected_revision or row['sha256']!=expected_sha256:
                    raise Conflict(f'stale PES-15 write rejected: expected revision={expected_revision} sha={expected_sha256[:12]}, actual revision={row["revision"]} sha={row["sha256"][:12]}; re-fetch and reconcile')
                issues=errors_only(validate(snapshot,baseline=current))
                if issues:
                    raise StoreValidation('snapshot validation failed: '+ '; '.join(f'{x.code} {x.path}' for x in issues[:6]))
                if snapshot['artifact']['profile']!='canonical_snapshot':
                    raise StoreValidation('canonical head cannot switch to bootstrap/overlay')
                entry=self._append(db,snapshot,row['revision']+1,row['event_hash'],actor,reason)
                db.execute('UPDATE head SET revision=?, sha256=? WHERE name="canonical"', (entry['revision'],entry['sha256']))
                db.commit()
                return entry
            except Exception:
                db.rollback()
                raise

    def history(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute('SELECT revision,sha256,parent_event_hash,event_hash,created_at,actor,reason FROM history ORDER BY revision')]

    def snapshot_at(self,revision:int):
        with self.connection() as db:
            row=db.execute('SELECT data,sha256 FROM history WHERE revision=?',(revision,)).fetchone()
            if row is None:raise StoreError(f'unknown revision {revision}')
            obj=json.loads(row['data'])
            if digest(obj)!=row['sha256']:raise StoreError(f'corrupted snapshot at revision {revision}')
            return obj

    def verify(self):
        errors=[]
        with self.connection() as db:
            integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
            if integrity!='ok':errors.append(f'sqlite integrity_check: {integrity}')
            rows=db.execute('SELECT * FROM history ORDER BY revision').fetchall()
            previous_hash=None
            for n,row in enumerate(rows,1):
                if row['revision']!=n:errors.append(f'nonconsecutive revision {row["revision"]}, expected {n}')
                try:snapshot=json.loads(row['data'])
                except json.JSONDecodeError as e:
                    errors.append(f'JSON malformed at {n}: {e}');continue
                if digest(snapshot)!=row['sha256']:errors.append(f'snapshot hash mismatch at revision {n}')
                if row['parent_event_hash']!=previous_hash:errors.append(f'broken parent hash at revision {n}')
                event={'revision':row['revision'],'snapshot_sha256':row['sha256'],
                       'parent_event_hash':row['parent_event_hash'], 'created_at':row['created_at'],
                       'actor':row['actor'],'reason':row['reason']}
                if digest(event)!=row['event_hash']:errors.append(f'event hash mismatch at revision {n}')
                previous_hash=row['event_hash']
            head=db.execute('SELECT revision,sha256 FROM head WHERE name="canonical"').fetchone()
            if not head or not rows or head['revision']!=rows[-1]['revision'] or head['sha256']!=rows[-1]['sha256']:
                errors.append('canonical head does not match final history revision')
        return {'ok':not errors,'revision_count':len(rows),'errors':errors,
                'last_event_hash':previous_hash}

    def backup(self, destination: str|Path):
        """SQLite online backup to a NEW path; verified hash-chain and no-overwrite publish.

        This creates an independent recoverable file, not an in-place rollback.
        """
        dest = Path(destination).resolve()
        if dest == self.path or dest.exists():
            raise StoreError('backup destination must be a NEW distinct file; no overwrites')
        verified = self.verify()
        if not verified['ok']:
            raise StoreError('source store failed verification; refusing to create a trusted backup')
        dest.parent.mkdir(parents=True,exist_ok=True)
        fd,temp_name=tempfile.mkstemp(prefix='.'+dest.name+'.',suffix='.backup.tmp',dir=dest.parent)
        os.close(fd)
        try:
            # SQLite online backup includes transactions committed into WAL.
            with self.connection() as source:
                target=sqlite3.connect(temp_name)
                try:
                    source.backup(target)
                    target.commit()
                finally:
                    target.close()
            backup_check=CanonicalStore(temp_name).verify()
            if not backup_check['ok']:
                raise StoreError('backup content failed hash-chain verification')
            with open(temp_name,'rb') as f:
                os.fsync(f.fileno())
            # Atomic no-clobber publication; fails safely on unsupported filesystems.
            os.link(temp_name,dest)
            if os.name=='posix':
                directory_fd=os.open(str(dest.parent),os.O_RDONLY)
                try:os.fsync(directory_fd)
                finally:os.close(directory_fd)
            with open(dest,'rb') as f:
                fingerprint=hashlib.sha256(f.read()).hexdigest()
            return {'destination':str(dest),'sha256':fingerprint,'revisions':backup_check['revision_count'],
                'event_hash':backup_check['last_event_hash']}
        finally:
            try:os.unlink(temp_name)
            except FileNotFoundError:pass
