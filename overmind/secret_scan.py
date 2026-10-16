"""Offline Git secret check. Output contains filenames/categories, never matched values."""
import argparse
import json
from pathlib import PurePosixPath
import subprocess
import sys

from .secret_patterns import detections
from .security import redact, subprocess_environment


def git_environment():
    env=subprocess_environment()
    # Git may supply a temporary index for partial commits; inspect that exact snapshot.
    import os
    for name in ('GIT_INDEX_FILE','GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES'):
        if name in os.environ:env[name]=os.environ[name]
    return env


def git(*args):
    result=subprocess.run(['git','--no-optional-locks',*args],capture_output=True,env=git_environment())
    if result.returncode:raise ValueError('Cannot inspect Git data. Secret check failed closed.')
    return result.stdout


def sensitive_path(name):
    path=PurePosixPath(name)
    base=path.name.lower()
    if base in ('.env.example','.env.sample','credentials.example.json','secrets.example.json'):return False
    return (base=='.env' or base.startswith('.env.') or
        (base in {'credentials','secrets'} or (path.stem in {'credentials','secrets'} and path.suffix.lower() in {'.json','.yaml','.yml','.toml','.ini','.env'})) or base.startswith('lab.sqlite3') or base=='worker.lock' or
        base.endswith(('.key','.pem','.p12','.pfx','.log','.tmp','.temp','.swp','.swo')) or
        base.endswith(('.local.json','.local.yml','.local.yaml')) or name=='config.json' or
        name in ('.aws/credentials','.aws/config','.codex/auth.json') or
        'lab-data' in path.parts)


def inspect_files(mode):
    if mode=='staged':
        names=git('diff','--cached','--name-only','--diff-filter=ACMR','-z')
    else:names=git('ls-files','-z')
    ignored_result=subprocess.run(['git','--no-optional-locks','check-ignore','--no-index','--stdin','-z'],input=names,capture_output=True,env=git_environment())
    if ignored_result.returncode not in (0,1):raise ValueError('Cannot inspect ignore rules.')
    ignored=set(ignored_result.stdout.split(b'\0'))
    for raw_name in names.split(b'\0'):
        if not raw_name:continue
        name=raw_name.decode('utf-8','surrogateescape')
        content=git('show',':'+name).decode('utf-8','replace')
        kinds=detections(content)
        if sensitive_path(name) or raw_name in ignored:kinds.append('private/local file must not be committed')
        if kinds:yield name,sorted(set(kinds))


def inspect_history():
    # rev-list includes reachable commits; no network access or history modification.
    records=git('rev-list','--objects','--all').decode('utf-8','replace').splitlines()
    for record in records:
        oid,_,name=record.partition(' ')
        kind=git('cat-file','-t',oid).strip()
        if kind not in (b'blob',b'commit',b'tag'):continue
        content=git('cat-file',kind.decode(),oid).decode('utf-8','replace')
        kinds=detections(content)
        if kinds:yield name or '(Git metadata)',kinds


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    flags=parser.add_mutually_exclusive_group()
    flags.add_argument('--staged',action='store_true',help='Check staged snapshots, not working tree contents (default)')
    flags.add_argument('--tracked',action='store_true',help='Check all index snapshots (CI checkout)')
    flags.add_argument('--history',action='store_true',help='Check objects reachable from local refs; does not fetch')
    args=parser.parse_args(argv)
    try:
        findings=list(inspect_history() if args.history else inspect_files('tracked' if args.tracked else 'staged'))
    except (OSError,ValueError):
        print('Secret check could not complete; commit/check blocked.',file=sys.stderr);return 2
    for name,kinds in findings:
        print('BLOCKED '+json.dumps(redact(name),ensure_ascii=True)+': '+', '.join(kinds))
    if findings:
        print('Remove private files or secret values from the proposed commit. Matched content is intentionally withheld.')
        return 1
    print('Secret check passed (pattern-based; not proof that all sensitive data is absent).')
    return 0

if __name__=='__main__':raise SystemExit(main())
