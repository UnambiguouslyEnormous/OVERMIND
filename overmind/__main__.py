import argparse
import json
from pathlib import Path
import sys

from .data import load
from .hardware import inspect
from .lab import DEFAULTS, config_checked, worker
from .store import Store
from .security import harden_process, redacted_output, redact


def main():
    with redacted_output():
        try:
            harden_process()
            return _main()
        except KeyboardInterrupt:
            return 130
        except Exception as error:
            print('GAFAW:',redact(str(error)),file=sys.stderr)
            return 1


def _main():
    parser=argparse.ArgumentParser(description='GAFAW — bounded, verifiable local AI experiments')
    parser.add_argument('--data',default=str(Path(__file__).resolve().parent.parent/'lab-data'),help='Persistent laboratory directory')
    commands=parser.add_subparsers(dest='command')
    commands.add_parser('desktop',help='Launch the native desktop (default)')
    commands.add_parser('hardware',help='Inspect actual hardware')
    commands.add_parser('ollama',help='Discover local Ollama installation, server and models')
    models=commands.add_parser('models',help='Authenticated metadata discovery; no paid inference')
    models.add_argument('provider',choices=['openai','anthropic','ollama','compatible'])
    models.add_argument('--url',default='http://127.0.0.1:11434')
    run=commands.add_parser('run',help='Run the CPU weight-training vertical slice, or a JSON experiment configuration')
    run.add_argument('--config',help='Configuration JSON; cloud mentors require explicit authorization and rates')
    run.add_argument('--dataset',help='Licensed dataset JSON; default is original CC0 routing benchmark')
    run.add_argument('--epochs',type=int)
    commands.add_parser('list',help='List persisted experiments')
    show=commands.add_parser('show',help='Read a run and its report');show.add_argument('id')
    resume=commands.add_parser('recover',help='Recover an interrupted run');resume.add_argument('id')
    w=commands.add_parser('worker',help=argparse.SUPPRESS);w.add_argument('id')
    export=commands.add_parser('example-dataset');export.add_argument('path')
    predict=commands.add_parser('predict',help='Use a trained weight artifact');predict.add_argument('artifact');predict.add_argument('text');predict.add_argument('--allow-local-inference',action='store_true',help='Authorize one bounded local LLM request for a prompt/retrieval artifact')
    args=parser.parse_args()
    try:
        if args.command=='worker':return worker(args.data,args.id)
        if args.command in (None,'desktop'):
            from .desktop import launch
            launch(args.data);return 0
        if args.command=='ollama':
            from .ollama import discover
            print(json.dumps(redact(discover()),indent=2));return 0
        if args.command=='models':
            from .providers import provider
            print(json.dumps(redact(provider({'kind':args.provider,'model':'discovery','url':args.url}).models()),indent=2));return 0
        if args.command=='hardware':print(json.dumps(redact(inspect()),indent=2));return 0
        if args.command=='example-dataset':Path(args.path).write_text(json.dumps(load(),indent=2));return 0
        if args.command=='predict':
            from .inference import predict_artifact
            path=Path(args.artifact)
            if path.stat().st_size>8_000_000:raise ValueError('Artifact exceeds 8 MB.')
            artifact=json.loads(path.read_text())
            print(predict_artifact(artifact,args.text,args.allow_local_inference));return 0
        store=Store(args.data)
        if args.command=='list':
            for r in store.list():print(r['id'],r['status'])
            return 0
        if args.command=='show':
            print(json.dumps(redact(store.get(args.id)),indent=2));return 0
        if args.command=='recover':
            if store.get(args.id)['status'] not in ('interrupted','ready'):raise ValueError('Recovery requires a ready or interrupted experiment.')
            return worker(args.data,args.id)
        if args.command=='run':
            c=json.loads(Path(args.config).read_text()) if args.config else dict(DEFAULTS)
            if args.epochs is not None:c['epochs']=args.epochs
            rid=store.create(config_checked(c),load(args.dataset));print('Experiment:',rid,flush=True)
            result=worker(args.data,rid)
            run=store.get(rid);print('Status:',run['status'])
            if 'report' in run['state']:print(json.dumps(redact(run['state']['report']),indent=2))
            else:
                for e in store.events(rid):print(e['kind']+':',e['message'])
            print('Artifacts:',store.root/rid)
            return result
    except (ValueError,OSError,KeyError,RuntimeError,ImportError,json.JSONDecodeError) as e:
        print('GAFAW:',str(e),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
