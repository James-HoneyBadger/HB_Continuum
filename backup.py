"""Create and validate independent local archive snapshots."""
import hashlib,json,os,sqlite3,shutil,tempfile
from pathlib import Path
from contextlib import closing
from sync_lock import sync_lock

DATABASES=('archive.sqlite3','research.sqlite3')
CONFIG=('preferences.json','schedule.json','schedule-status.json')
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def connect(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
def copydb(source,target):
    with closing(connect(source)) as src,closing(sqlite3.connect(target)) as dst:src.backup(dst)
def validate_snapshot(root):
    root=Path(root)
    if (root/'backup-manifest.json').is_symlink():raise ValueError('Unsafe manifest')
    manifest=json.loads((root/'backup-manifest.json').read_text())
    if manifest.get('version')!=1 or not isinstance(manifest.get('files'),dict):raise ValueError('Invalid backup manifest')
    expected=manifest['files']
    entries=list(root.rglob('*'))
    if any(p.is_symlink() or not (p.is_dir() or p.is_file()) for p in entries):raise ValueError('Unsafe snapshot entry')
    actual={p.relative_to(root).as_posix() for p in entries if p.is_file() and p!=root/'backup-manifest.json'}
    allowed=set(DATABASES+CONFIG)
    if any(name not in allowed and not (name.startswith('raw/') and len(name)==72 and name.endswith('.eml') and all(c in '0123456789abcdef' for c in name[4:-4])) for name in actual):raise ValueError('Unexpected snapshot file')
    if set(expected)!=actual:raise ValueError('Backup file set mismatch')
    for name,h in expected.items():
        p=root/name
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) or digest(p)!=h:raise ValueError('Backup hash mismatch: '+name)
    for name in DATABASES:
        if name not in expected:
            if name=='archive.sqlite3':raise ValueError('Missing archive database')
            continue
        with closing(connect(root/name)) as db:
            if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('SQLite integrity failure')
            if db.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Foreign key failure')
            if name=='archive.sqlite3':
                hashes={h for h, in db.execute('SELECT hash FROM messages')}
                indexed={h for h, in db.execute('SELECT hash FROM search')}
                if hashes!=indexed or len(indexed)!=db.execute('SELECT count(*) FROM search').fetchone()[0]:raise ValueError('Search index mismatch')
                for h in hashes:
                    if expected.get('raw/'+h+'.eml')!=h:raise ValueError('Original message missing or altered: '+h)
    return {'files':len(expected),'verified':True}

def publish_stage(stage,dest):
    # Reserve destination atomically; never replace an existing backup.
    dest.mkdir(mode=0o700)
    try:
        for child in stage.iterdir():child.rename(dest/child.name)
    except BaseException:
        shutil.rmtree(dest);raise

def backup(root,destination):
    root=Path(root).expanduser().resolve();dest=Path(destination).expanduser().resolve()
    if dest.is_relative_to(root) or root.is_relative_to(dest):raise ValueError('Backup must be outside archive')
    if dest.exists():raise FileExistsError(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    if (root/'raw').is_symlink():raise ValueError('Unsafe source raw directory')
    with sync_lock(root),tempfile.TemporaryDirectory(dir=dest.parent,prefix='.hb-backup-') as tmp:
        stage=Path(tmp);(stage/'raw').mkdir(mode=0o700)
        for name in DATABASES:
            if (root/name).is_file():
                if (root/name).is_symlink():raise ValueError('Unsafe source database')
                copydb(root/name,stage/name)
        for name in CONFIG:
            if (root/name).is_file():
                if (root/name).is_symlink():raise ValueError('Unsafe source configuration')
                shutil.copyfile(root/name,stage/name)
        with closing(connect(stage/'archive.sqlite3')) as db:
            for h, in db.execute('SELECT hash FROM messages'):
                if len(h)!=64 or any(x not in '0123456789abcdef' for x in h):raise ValueError('Invalid message hash')
                source=root/'raw'/(h+'.eml')
                if source.is_symlink():raise ValueError('Unsafe source message')
                shutil.copyfile(source,stage/'raw'/(h+'.eml'))
        files={p.relative_to(stage).as_posix():digest(p) for p in stage.rglob('*') if p.is_file()}
        (stage/'backup-manifest.json').write_text(json.dumps({'version':1,'files':files},indent=2))
        result=validate_snapshot(stage)
        publish_stage(stage,dest)
        return result

def restore(snapshot,destination):
    src=Path(snapshot).expanduser().resolve();dest=Path(destination).expanduser().resolve()
    if dest.is_relative_to(src) or src.is_relative_to(dest):raise ValueError('Restore must use independent destination')
    if dest.exists():raise FileExistsError(dest)
    validate_snapshot(src)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent,prefix='.hb-restore-') as tmp:
        stage=Path(tmp)
        for child in src.iterdir():
            if child.is_dir():shutil.copytree(child,stage/child.name)
            else:shutil.copyfile(child,stage/child.name)
        result=validate_snapshot(stage)
        # Restored profiles must not begin background jobs automatically.
        path=stage/'schedule.json'
        if path.exists():
            profiles=json.loads(path.read_text())
            for profile in profiles.values():profile['enabled']=False
            path.write_text(json.dumps(profiles,indent=2))
        (stage/'backup-manifest.json').unlink()
        publish_stage(stage,dest)
        return result
