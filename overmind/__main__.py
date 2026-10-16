import argparse
import json
from pathlib import Path
import sys

from .data import load
from .hardware import inspect
from .lab import DEFAULTS, config_checked, worker
from .store import Store


def main():
    parser=argparse.ArgumentParser(description='OVERMIND — bounded, verifiable local AI experiments')
    parser.add_argument('--data',default=str(Path(__file__).resolve().parent.parent/'lab-data'),help='Persistent laboratory directory')
    commands=parser.add_subparsers(dest='command')
    commands.add_parser('desktop',help='Launch the native desktop (default)')
    commands.add_parser('hardware',help='Inspect actual hardware')
    run=commands.add_parser('run',help='Run the CPU weight-training vertical slice, or a JSON experiment configuration')
    run.add_argument('--config',help='Configuration JSON; local providers only')
    run.add_argument('--dataset',help='Licensed dataset JSON; default is original CC0 routing benchmark')
    run.add_argument('--epochs',type=int)
    commands.add_parser('list',help='List persisted experiments')
    show=commands.add_parser('show',help='Read a run and its report');show.add_argument('id')
    resume=commands.add_parser('recover',help='Recover an interrupted run');resume.add_argument('id')
    w=commands.add_parser('worker',help=argparse.SUPPRESS);w.add_argument('id')
    export=commands.add_parser('example-dataset');export.add_argument('path')
    predict=commands.add_parser('predict',help='Use a trained weight artifact');predict.add_argument('artifact');predict.add_argument('text')
    args=parser.parse_args()
    try:
        if args.command=='worker':return worker(args.data,args.id)
        if args.command in (None,'desktop'):
            from .desktop import launch
            launch(args.data);return 0
        if args.command=='hardware':print(json.dumps(inspect(),indent=2));return 0
        if args.command=='example-dataset':Path(args.path).write_text(json.dumps(load(),indent=2));return 0
        if args.command=='predict':
            from .model import TextStudent
            artifact=json.loads(Path(args.artifact).read_text())
            if artifact.get('format')!='overmind.softmax.v1':raise ValueError('CLI prediction currently supports trained classifier artifacts only.')
            print(TextStudent.restore(artifact).predict(args.text));return 0
        store=Store(args.data)
        if args.command=='list':
            for r in store.list():print(r['id'],r['status'])
            return 0
        if args.command=='show':
            print(json.dumps(store.get(args.id),indent=2));return 0
        if args.command=='recover':
            if store.get(args.id)['status'] not in ('interrupted','ready'):raise ValueError('Recovery requires a ready or interrupted experiment.')
            return worker(args.data,args.id)
        if args.command=='run':
            c=json.loads(Path(args.config).read_text()) if args.config else dict(DEFAULTS)
            if args.epochs is not None:c['epochs']=args.epochs
            rid=store.create(config_checked(c),load(args.dataset));print('Experiment:',rid,flush=True)
            result=worker(args.data,rid)
            run=store.get(rid);print('Status:',run['status'])
            if 'report' in run['state']:print(json.dumps(run['state']['report'],indent=2))
            else:
                for e in store.events(rid):print(e['kind']+':',e['message'])
            print('Artifacts:',store.root/rid)
            return result
    except (ValueError,OSError,KeyError,RuntimeError,ImportError,json.JSONDecodeError) as e:
        print('OVERMIND:',str(e),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
