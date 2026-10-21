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
    workshop=commands.add_parser('prepare-dataset',help='Import, deduplicate, split and export a labeled dataset version')
    workshop.add_argument('source');workshop.add_argument('output')
    workshop.add_argument('--license',default='',help='Required permission statement for unsplit files')
    workshop.add_argument('--seed',type=int,default=42)
    local=commands.add_parser('inspect-model',help='Read local HF checkpoint metadata without loading weights or code')
    local.add_argument('path')
    bundle=commands.add_parser('export-bundle',help='Export private local evidence; dataset text/weights excluded by default')
    bundle.add_argument('id');bundle.add_argument('output')
    bundle.add_argument('--include-dataset',action='store_true');bundle.add_argument('--include-weights',action='store_true')
    check_bundle=commands.add_parser('check-bundle',help='Verify a bundle without extracting or executing contents')
    check_bundle.add_argument('path')
    comparison=commands.add_parser('compare',help='Compare two completed runs using recorded evidence')
    comparison.add_argument('left');comparison.add_argument('right')
    preflight=commands.add_parser('lora-preflight',help='Check an existing local Qwen checkpoint and the isolated optional ML runtime')
    preflight.add_argument('--model',required=True);preflight.add_argument('--model-license',required=True)
    preflight.add_argument('--device',choices=['cpu','cuda'],default='cpu');preflight.add_argument('--precision',choices=['fp32','fp16'],default='fp32')
    preflight.add_argument('--max-length',type=int,default=256);preflight.add_argument('--memory-mb',type=int,default=8192)
    preflight.add_argument('--runtime',action='store_true',help=argparse.SUPPRESS)
    commands.add_parser('example-instructions',help='Print original CC0 instruction dataset with explicit splits for review')
    playground=commands.add_parser('playground',help='Generate matched stock/prompted/adapter responses for a completed local LoRA run')
    playground.add_argument('id');playground.add_argument('prompt');playground.add_argument('--runtime',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:
        if args.command=='example-instructions':
            from .sft_data import example
            print(json.dumps(example(),indent=2));return 0
        if args.command=='lora-preflight':
            from .lora import preflight,python_executable
            if not args.runtime:
                import subprocess
                from .security import subprocess_environment
                env=subprocess_environment();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
                result=subprocess.run([python_executable(),'-m','overmind',*sys.argv[1:],'--runtime'],env=env,timeout=30)
                return result.returncode
            result=preflight(args.model,{'model_license':args.model_license,'device':args.device,'precision':args.precision,'max_length':args.max_length},args.memory_mb,runtime=True)
            print(json.dumps(redact(result),indent=2));return 0 if result['ready'] else 2
        if args.command=='check-bundle':
            from .bundle import validate_bundle
            print(json.dumps(redact(validate_bundle(args.path)),indent=2));return 0
        if args.command=='prepare-dataset':
            from .workshop import import_file,export_version,summary
            dataset=import_file(args.source,args.license,args.seed)
            export_version(dataset,args.output)
            print(json.dumps(summary(dataset),indent=2));return 0
        if args.command=='inspect-model':
            from .inventory import inspect_local
            print(json.dumps(redact(inspect_local(args.path)),indent=2));return 0
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
        if args.command=='playground':
            if not args.runtime:
                import subprocess
                from .lora import python_executable
                from .security import subprocess_environment
                env=subprocess_environment();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
                return subprocess.run([python_executable(),'-m','overmind',*sys.argv[1:],'--runtime'],env=env,timeout=store.get(args.id)['config']['minutes']*60).returncode
            from .lora import playground
            print(json.dumps(redact(playground(store,args.id,args.prompt)),indent=2));return 0
        if args.command=='export-bundle':
            from .bundle import export_bundle
            print(json.dumps(export_bundle(store,args.id,args.output,args.include_dataset,args.include_weights),indent=2));return 0
        if args.command=='compare':
            from .science import compare
            print(json.dumps(redact(compare(store,args.left,args.right)),indent=2));return 0
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
            if c.get('student',{}).get('kind')=='local_lora':
                from .lab import Manager
                import time
                manager=Manager(args.data);manager.start(rid)
                try:
                    while manager.process.poll() is None:manager.poll();time.sleep(.2)
                    manager.poll();result=manager.process.returncode
                except KeyboardInterrupt:manager.stop();raise
            else:result=worker(args.data,rid)
            run=store.get(rid);print('Status:',run['status'])
            if 'report' in run['state']:print(json.dumps(redact(run['state']['report']),indent=2))
            else:
                for e in store.events(rid):print(e['kind']+':',e['message'])
            print('Artifacts:',store.root/rid)
            return result
    except (ValueError,OSError,KeyError,RuntimeError,ImportError,json.JSONDecodeError) as e:
        print('GAFAW:',str(e),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
