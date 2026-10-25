"""Coordinated PostgreSQL/private-attachment backup and isolated restore drill.

Run while application writes are paused. No command overwrites an existing database.
Database passwords are passed through the child environment, never command arguments.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4
from sqlalchemy import create_engine,text,inspect,select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from backend.config import ROOT,settings
from backend.persistence.models import Record,FilingSnapshot
from backend.domain.filing import digest
from backend.storage import attachments,LocalAttachments,checked_key


def sha(data):return hashlib.sha256(data).hexdigest()


def pg(tool,url,stream):
    u=make_url(url);env=dict(os.environ)
    env.update(PGHOST=u.host or 'localhost',PGPORT=str(u.port or 5432),PGUSER=u.username or '',PGPASSWORD=u.password or '',PGDATABASE=u.database or '')
    if u.query.get('sslmode'):env['PGSSLMODE']=u.query['sslmode']
    command=[tool]
    if not shutil.which(tool):
        command=['docker','compose','exec','-T']
        for name in ('PGHOST','PGPORT','PGUSER','PGPASSWORD','PGDATABASE','PGSSLMODE'):
            if name in env:command+=['-e',name]
        command+=['db',tool]
    command+=['--no-owner','--no-privileges']
    if tool=='pg_dump':command+=['--format=custom']
    else:command+=['--exit-on-error','--dbname',u.database]
    result=subprocess.run(command,cwd=ROOT,env=env,stdin=stream if tool=='pg_restore' else None,
        stdout=stream if tool=='pg_dump' else subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:raise RuntimeError(tool+' failed; check PostgreSQL availability, permissions and client/server versions.')


def proof(engine):
    result={}
    with engine.connect() as db:
        for name in sorted(inspect(db).get_table_names(schema='public')):
            quoted=db.dialect.identifier_preparer.quote(name)
            rows=db.execute(text(f'SELECT to_jsonb(t)::text FROM public.{quoted} t')).scalars().all()
            result[name]={'rows':len(rows),'sha256':sha('\n'.join(sorted(rows)).encode())}
    return result


def create(url,directory,store):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False,mode=0o700)
    engine=create_engine(url)
    try:
        before=proof(engine)
        with (directory/'database.dump').open('xb') as dump:pg('pg_dump',url,dump)
        (directory/'database.dump').chmod(0o600)
        files={};dest=directory/'attachments';dest.mkdir(mode=0o700)
        with Session(engine) as db:
            rows=db.scalars(select(Record).where(Record.kind=='attachment')).all()
            for row in rows:
                key=checked_key(row.payload['storage_key']);data=store.read(key)
                if sha(data)!=row.payload['sha256']:raise RuntimeError('Attachment checksum mismatch; backup aborted')
                (dest/key).write_bytes(data);(dest/key).chmod(0o600)
                files[key]={'sha256':sha(data),'bytes':len(data)}
        after=proof(engine)
        if before!=after:raise RuntimeError('Database changed during backup. Pause app writes and retry into a new directory.')
        manifest={'version':1,'created_at':datetime.now(timezone.utc).isoformat(),'database_sha256':sha((directory/'database.dump').read_bytes()),'tables':after,'attachments':files}
        (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(directory/'manifest.json').chmod(0o600)
        return manifest
    finally:engine.dispose()


def restore(url,directory,destination):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['version']!=1 or sha((directory/'database.dump').read_bytes())!=manifest['database_sha256']:raise RuntimeError('Invalid database backup checksum')
    for key,item in manifest['attachments'].items():
        if sha((directory/'attachments'/checked_key(key)).read_bytes())!=item['sha256']:raise RuntimeError('Invalid attachment backup checksum')
    destination=Path(destination)
    if destination.exists() and any(destination.iterdir()):raise RuntimeError('Attachment restore directory must be empty')
    engine=create_engine(url)
    try:
        with engine.connect() as db:
            if inspect(db).get_table_names(schema='public'):raise RuntimeError('Restore target database must be empty; existing tables were not touched')
        with (directory/'database.dump').open('rb') as dump:pg('pg_restore',url,dump)
        destination.mkdir(parents=True,exist_ok=True,mode=0o700)
        for key in manifest['attachments']:
            shutil.copyfile(directory/'attachments'/key,destination/key);(destination/key).chmod(0o600)
        if proof(engine)!=manifest['tables']:raise RuntimeError('Restored database verification failed')
        return {'tables_verified':len(manifest['tables']),'attachments_verified':len(manifest['attachments'])}
    finally:engine.dispose()


def drill(url,directory,store):
    """Clone the local database; add a synthetic attachment/snapshot only to the clone; round-trip it."""
    base=make_url(url)
    if base.host not in {'localhost','127.0.0.1'}:raise RuntimeError('The automated drill is restricted to local PostgreSQL')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False,mode=0o700)
    control=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT')
    names=['miraflores_drill_'+uuid4().hex for _ in range(2)]
    made=[]
    try:
        for name in names:
            with control.connect() as db:db.execute(text('CREATE DATABASE '+name))
            made.append(name)
        first=base.set(database=names[0]).render_as_string(hide_password=False)
        second=base.set(database=names[1]).render_as_string(hide_password=False)
        create(url,directory/'source-backup',store)
        restore(first,directory/'source-backup',directory/'source-attachments')
        local=LocalAttachments(directory/'source-attachments');data=b'Synthetic Day 9 restore-drill attachment; never added to live work.\n';key=local.put(data)
        engine=create_engine(first)
        with Session(engine) as db,db.begin():
            packet_id=db.execute(text('SELECT id FROM packet_imports LIMIT 1')).scalar_one()
            db.add(Record(packet_id=packet_id,ref='restore-drill:attachment',kind='attachment',revision=7,payload={'storage_key':key,'sha256':sha(data),'filename':'drill.txt'}))
            content={'purpose':'Synthetic restore-drill snapshot, isolated clone only'}
            db.add(FilingSnapshot(id='restore-drill-snapshot',packet_id=packet_id,branch_ref='restore-drill',content=content,digest=digest(content),actor_id='st-01',at='2026-10-23T00:00:00Z'))
        engine.dispose()
        create(first,directory/'drill-backup',local)
        result=restore(second,directory/'drill-backup',directory/'restored-attachments')
        if LocalAttachments(directory/'restored-attachments').read(key)!=data:raise RuntimeError('Restored attachment bytes differ')
        engine=create_engine(second)
        with Session(engine) as db:
            if db.query(Record).filter_by(ref='restore-drill:attachment').one().revision!=7:raise RuntimeError('Restored revision differs')
        protected=False
        try:
            with engine.begin() as db:db.execute(text("UPDATE filing_snapshots SET digest='invalid' WHERE id='restore-drill-snapshot'"))
        except DBAPIError:protected=True
        engine.dispose()
        if not protected:raise RuntimeError('Restored immutable-snapshot trigger was not enforced')
        result.update(snapshot_guard_verified=True,revision_verified=True,live_database_changed=False)
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    finally:
        for name in made:
            with control.connect() as db:db.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
        control.dispose()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['create','restore','drill']);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--database-env',default='DATABASE_URL');p.add_argument('--attachment-dir',type=Path)
    args=p.parse_args()
    url=os.environ.get(args.database_env) or (settings.database_url if args.database_env=='DATABASE_URL' else None)
    if not url:raise SystemExit('Set the selected database environment variable')
    url=settings.postgres_driver(url)
    if args.command=='restore':
        if args.database_env=='DATABASE_URL':raise SystemExit('Use --database-env RESTORE_DATABASE_URL for an explicit empty target')
        if not args.attachment_dir:raise SystemExit('Provide an empty --attachment-dir')
        result=restore(url,args.directory,args.attachment_dir)
    else:result=(create if args.command=='create' else drill)(url,args.directory,attachments)
    print(json.dumps(result if args.command!='create' else {'backup_created':str(args.directory),'tables':len(result['tables']),'attachments':len(result['attachments'])},indent=2))

if __name__=='__main__':main()
