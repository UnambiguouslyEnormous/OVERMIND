"""Optional local causal-LM SFT/LoRA. Imports no ML library until an explicit worker run."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import shutil
import time

from .data import digest
from .security import reject_secrets
from .sft_data import validate as validate_sft

OPTIONS={'device':'cpu','precision':'fp32','max_length':256,'max_steps':20,'learning_rate':0.0002,
         'rank':8,'alpha':16,'accumulation':1,'max_new_tokens':48,'seed':42,'system_prompt':'',
         'model_license':''}
DEPENDENCIES=('torch','transformers','peft','safetensors')
SUPPORTED={'qwen2','qwen3'}


def python_executable():
    """Use only the fixed, user-provisioned repository environment, never imported executable paths."""
    import sys
    local=Path(__file__).resolve().parent.parent/'.venv-llm'/'bin'/'python'
    return str(local) if local.is_file() else sys.executable


def checked(options):
    if not isinstance(options,dict) or set(options)-set(OPTIONS):raise ValueError('Unknown LoRA options.')
    reject_secrets(options);c={**OPTIONS,**options}
    for key,lo,hi in (('max_length',32,2048),('max_steps',1,1000),('rank',1,64),('alpha',1,128),('accumulation',1,32),('max_new_tokens',1,256),('seed',0,2**31-1)):
        if type(c[key]) is not int or not lo<=c[key]<=hi:raise ValueError(f'{key} must be an integer in {lo}–{hi}.')
    if c['device'] not in ('cpu','cuda') or c['precision'] not in ('fp32','fp16'):raise ValueError('Choose CPU/CUDA and FP32/FP16; BF16 and quantization are not enabled.')
    if c['device']=='cpu' and c['precision']!='fp32':raise ValueError('CPU LoRA uses FP32.')
    if type(c['learning_rate']) not in (int,float) or not math.isfinite(c['learning_rate']) or not 1e-7<=c['learning_rate']<=.01:raise ValueError('Learning rate must be between 1e-7 and 0.01.')
    if not isinstance(c['system_prompt'],str) or len(c['system_prompt'])>2000:raise ValueError('Style/system prompt must be at most 2,000 characters.')
    if not isinstance(c['model_license'],str) or not 0<len(c['model_license'])<=500:raise ValueError('Review and declare the local base model license/permission.')
    return c


def _json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>1_000_000:raise ValueError('Checkpoint metadata must be a bounded regular local file.')
    data=json.loads(path.read_text())
    if not isinstance(data,dict):raise ValueError('Checkpoint metadata must be a JSON object.')
    return data


def checkpoint_files(model_path):
    root=Path(model_path).absolute()
    if not root.is_dir() or any(p.is_symlink() for p in (root,*root.parents)):raise ValueError('Choose a local checkpoint directory without symlink traversal (copy HF cache snapshots to regular files).')
    config=_json(root/'config.json')
    if config.get('model_type') not in SUPPORTED:raise ValueError('This initial backend supports standard Qwen2/Qwen2.5 and Qwen3 causal-LM checkpoints only.')
    if config.get('auto_map') or config.get('quantization_config'):raise ValueError('Custom model code and prequantized checkpoints are not supported. Select standard nonquantized HF weights, not Ollama/GGUF.')
    files=[]
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('Checkpoint contains a symlink; use a regular-file snapshot.')
        if not p.is_file():continue
        if p.suffix in ('.bin','.pt','.pth','.pkl','.py'):
            raise ValueError('Pickle/custom-code checkpoint files are not accepted; supply a clean safetensors snapshot.')
        if p.suffix=='.safetensors' or p.suffix=='.json' or p.name in ('merges.txt','vocab.txt','tokenizer.model'):
            files.append(p)
        if len(files)>256:raise ValueError('Checkpoint contains too many files.')
    weights=[p for p in files if p.suffix=='.safetensors']
    if not weights or not (root/'tokenizer.json').is_file():raise ValueError('Need local safetensors base weights and tokenizer.json. Inference endpoints/GGUF files are not trainable HF checkpoints.')
    # Shard indexes must reference in-directory regular safetensors files only.
    index=root/'model.safetensors.index.json'
    if index.exists():
        for name in set(_json(index).get('weight_map',{}).values()):
            if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.safetensors') or not (root/name).is_file():raise ValueError('Unsafe or missing model shard reference.')
    return root,config,files


def preflight(model_path,options,memory_mb=8192,storage_path=None,runtime=False):
    c=checked(options);root,config,files=checkpoint_files(model_path)
    weights=sum(p.stat().st_size for p in files if p.suffix=='.safetensors')
    # Conservative planning heuristic, not a measured fit guarantee: activations vary by architecture.
    estimated_mb=math.ceil(weights*(4 if c['precision']=='fp32' else 2)/2**20)+1024+c['max_length']*2
    deps={name:importlib.util.find_spec(name) is not None for name in DEPENDENCIES}
    blockers=[];warnings=[];device_info=None
    if not all(deps.values()):blockers.append('Missing optional ML dependencies. Provision .venv-llm as documented; normal GTK/classifier use needs none of them.')
    if memory_mb<estimated_mb and c['device']=='cpu':blockers.append(f'Conservative RAM estimate {estimated_mb} MB exceeds configured worker limit {memory_mb} MB.')
    free_disk=shutil.disk_usage(storage_path or root).free//2**20
    if free_disk<256:blockers.append('Less than 256 MB free artifact storage.')
    if c['device']=='cuda' and not runtime:blockers.append('CUDA must be checked in the selected training interpreter; run runtime preflight.')
    if runtime and deps['torch']:
        import torch
        if c['device']=='cuda':
            if not torch.cuda.is_available():blockers.append('PyTorch cannot initialize CUDA on this machine.')
            else:
                capability=torch.cuda.get_device_capability(0);free,total=torch.cuda.mem_get_info(0)
                device_info={'name':torch.cuda.get_device_name(0),'capability':list(capability),'free_vram_mb':free//2**20,'total_vram_mb':total//2**20,'runtime':torch.version.cuda}
                arches=torch.cuda.get_arch_list()
                if f'sm_{capability[0]}{capability[1]}' not in arches and f'compute_{capability[0]}{capability[1]}' not in arches:
                    warnings.append('Exact GPU architecture not listed in this PyTorch build; compatibility depends on the actual kernel smoke below. Older Pascal cards may need a compatible CUDA/PyTorch build.')
                if free//2**20<estimated_mb:blockers.append('Conservative training estimate exceeds currently free VRAM; reduce model/sequence length or use CPU.')
                try:
                    dtype=torch.float16 if c['precision']=='fp16' else torch.float32
                    x=torch.ones((8,8),device='cuda',dtype=dtype,requires_grad=True)
                    (x@x).sum().backward();torch.cuda.synchronize();del x
                except Exception as error:blockers.append('Actual CUDA precision/kernel smoke failed: '+type(error).__name__)
                if capability[0]<7:warnings.append('Pascal/older: no BF16, no FlashAttention or 4-bit kernels enabled; FP16 throughput may be poor.')
    if runtime and all(deps.values()):
        try:
            os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
            from transformers import AutoConfig,AutoTokenizer
            from peft import LoraConfig
            AutoConfig.from_pretrained(str(root),local_files_only=True,trust_remote_code=False)
            tokenizer=AutoTokenizer.from_pretrained(str(root),local_files_only=True,trust_remote_code=False)
            if not tokenizer.chat_template or tokenizer.eos_token_id is None:blockers.append('Tokenizer needs a local chat template and EOS token.')
        except Exception as error:blockers.append('Optional Transformers/PEFT/tokenizer runtime failed: '+type(error).__name__+': '+str(error)[:300])
    if c['device']=='cpu':warnings.append('CPU FP32 is a safe fallback, often slow for 0.5B+ models. No duration estimate is invented; measured throughput appears after training starts.')
    return {'ready':not blockers,'blockers':blockers,'warnings':warnings,'dependencies':deps,'device':c['device'],'precision':c['precision'],
            'runtime_device':device_info,'model_type':config['model_type'],'weight_bytes':weights,'estimated_working_mb':estimated_mb,
            'estimate_notice':'Conservative heuristic, not an allocation guarantee; no automatic offload, quantization, BF16 or FlashAttention.',
            'free_disk_mb':free_disk,'model_license':c['model_license'],'options':c}


def _fingerprint(files,guard,root=None):
    result={}
    for path in files:
        h=hashlib.sha256()
        with path.open('rb') as stream:
            while block:=stream.read(1024*1024):h.update(block);guard()
        result[path.relative_to(root).as_posix() if root else path.name]=h.hexdigest()
    return result


def run(experiment):
    """One bounded Torch/Transformers/PEFT experiment in the existing isolated worker."""
    exp=experiment;c=checked(exp.c['lora']);data=validate_sft(exp.dataset)
    if exp.s['phase']!='inspect':raise ValueError('Interrupted LoRA runs preserve completed adapter checkpoints but cannot resume optimizer state yet. Create a fresh run; the old run stays intact.')
    report=preflight(exp.c['student']['model'],c,exp.c['memory_mb'],exp.store.root,runtime=True)
    exp.store.artifact(exp.rid,'preflight.json',report)
    if not report['ready']:raise ValueError('LoRA preflight blocked: '+'; '.join(report['blockers']))
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from peft import LoraConfig,get_peft_model,PeftModel
    from .environment import snapshot
    torch.set_num_threads(min(4,os.cpu_count() or 1));torch.manual_seed(c['seed'])
    if c['device']=='cuda':torch.cuda.manual_seed_all(c['seed'])
    root,_,files=checkpoint_files(exp.c['student']['model'])
    exp.s['dataset_sha256']=digest(data);exp.s['phase']='load';exp.save()
    exp.store.artifact(exp.rid,'environment.json',snapshot())
    identities=_fingerprint(files,exp.guard,root)
    exp.store.artifact(exp.rid,'base-model.json',{'files_sha256':identities,'model_type':report['model_type'],'license':c['model_license']})
    tokenizer=AutoTokenizer.from_pretrained(str(root),local_files_only=True,trust_remote_code=False)
    if not tokenizer.chat_template:raise ValueError('A local tokenizer chat_template is required; no guessed prompt format is used.')
    if tokenizer.eos_token_id is None:raise ValueError('Tokenizer requires an EOS token.')
    dtype=torch.float16 if c['precision']=='fp16' else torch.float32
    load_kwargs={'local_files_only':True,'trust_remote_code':False,'use_safetensors':True,'torch_dtype':dtype,'attn_implementation':'eager'}
    def load_base():
        exp.guard();return AutoModelForCausalLM.from_pretrained(str(root),**load_kwargs).to(c['device'])
    base=load_base();base.config.use_cache=False
    if c['max_length']+c['max_new_tokens']>getattr(base.config,'max_position_embeddings',0):raise ValueError('Training context plus generation cap exceeds model position capacity.')

    def prompt_ids(text,style):
        messages=([{'role':'system','content':style}] if style else [])+[{'role':'user','content':text}]
        return tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False)

    def encode(row,style):
        prefix=prompt_ids(row['input'],style)
        response=tokenizer.encode(row['target'],add_special_tokens=False)+[tokenizer.eos_token_id]
        if len(prefix)+len(response)>c['max_length']:raise ValueError('An instruction/response exceeds max_length. Shorten the example or increase the explicit cap; no silent response truncation.')
        if not response:raise ValueError('No trainable response tokens.')
        return {'input_ids':torch.tensor([prefix+response],device=c['device']),
                'labels':torch.tensor([[-100]*len(prefix)+response],device=c['device'])},len(response)

    # Validate/tokenize all rows before taking a single optimizer step. Held-out rows are never used for updates.
    for split in ('train','validation','test'):
        for row in data[split]:
            batch,_=encode(row,c['system_prompt']);del batch
            exp.guard()

    def evaluate(model,rows,style):
        model.eval();results=[];loss_sum=0;token_count=0;start=time.monotonic()
        with torch.no_grad():
            for row in rows:
                exp.guard();batch,n=encode(row,style)
                loss=float(model(**batch).loss.item());loss_sum+=loss*n;token_count+=n
                ids=prompt_ids(row['input'],style)
                if len(ids)+c['max_new_tokens']>getattr(model.config,'max_position_embeddings',0):raise ValueError('Evaluation prompt exceeds context capacity.')
                inputs=torch.tensor([ids],device=c['device'])
                output=model.generate(input_ids=inputs,attention_mask=torch.ones_like(inputs),max_new_tokens=c['max_new_tokens'],do_sample=False,
                                      pad_token_id=tokenizer.eos_token_id,eos_token_id=tokenizer.eos_token_id,use_cache=True)
                answer=tokenizer.decode(output[0,len(ids):],skip_special_tokens=True).strip()
                results.append({'input':row['input'],'target':row['target'],'prediction':answer,'correct':answer==row['target'].strip(),'axis':row.get('axis','instruction')})
        return {'accuracy':sum(r['correct'] for r in results)/len(results),'count':len(results),'results':results,
                'response_nll':loss_sum/token_count,'response_tokens':token_count,'seconds':time.monotonic()-start}

    exp.s['phase']='baseline';exp.save();exp.event('evaluation','Measuring stock and prompted baselines locally. No held-out response is used for training.')
    baseline_validation=evaluate(base,data['validation'],c['system_prompt'])
    baseline_test=evaluate(base,data['test'],c['system_prompt'])
    exp.store.artifact(exp.rid,'baseline-validation.json',baseline_validation)
    exp.store.artifact(exp.rid,'baseline-test.json',baseline_test)
    stock=evaluate(base,data['test'],'') if c['system_prompt'] else baseline_test
    exp.store.artifact(exp.rid,'stock-test.json',stock)
    model=get_peft_model(base,LoraConfig(r=c['rank'],lora_alpha=c['alpha'],lora_dropout=0.,bias='none',task_type='CAUSAL_LM',target_modules=['q_proj','v_proj']))
    trainable={name:p for name,p in model.named_parameters() if p.requires_grad}
    if not trainable or any('lora_' not in name for name in trainable):raise ValueError('Expected LoRA-only trainable parameters.')
    before={name:p.detach().cpu().clone() for name,p in trainable.items()}
    def tensor_hash(parameters):
        h=hashlib.sha256()
        for name,p in sorted(parameters.items()):h.update(name.encode());h.update(p.detach().float().cpu().contiguous().numpy().tobytes())
        return h.hexdigest()
    before_hash=tensor_hash(before)
    optimizer=torch.optim.AdamW(trainable.values(),lr=c['learning_rate'],weight_decay=0.)
    scaler=torch.cuda.amp.GradScaler(enabled=c['device']=='cuda' and c['precision']=='fp16')
    metrics=[];steps=0;processed=0
    directory=exp.store.root/exp.rid

    def save_adapter(epoch):
        name=f'adapter-epoch-{epoch}'
        path=directory/name
        if path.exists():raise ValueError('Refusing to overwrite an adapter checkpoint.')
        model.save_pretrained(path,safe_serialization=True)
        exp.store.artifact(exp.rid,'checkpoint.json',{'adapter':name,'epoch':epoch,'optimizer_steps':steps,'optimizer_resume':False})
        return path

    exp.s['phase']='improve';exp.save()
    for epoch in range(exp.c['epochs']):
        model.train();optimizer.zero_grad(set_to_none=True);order=list(range(len(data['train'])))
        random.Random(c['seed']+epoch).shuffle(order)
        epoch_start=time.monotonic();losses=[];gradients=[];group_count=0
        for position,index in enumerate(order):
            exp.guard();batch,n=encode(data['train'][index],c['system_prompt']);loss=model(**batch).loss
            if not torch.isfinite(loss):raise ValueError('Nonfinite training loss; try FP32/lower learning rate.')
            # Divide by the actual accumulation group size, including the final partial group.
            group_size=min(c['accumulation'],len(order)-(position//c['accumulation'])*c['accumulation'])
            scaler.scale(loss/group_size).backward();losses.append(float(loss.detach().item()));processed+=1;group_count+=1
            if group_count==group_size:
                scaler.unscale_(optimizer)
                norm=torch.nn.utils.clip_grad_norm_(list(trainable.values()),1.0,error_if_nonfinite=True)
                gradients.append(float(norm));scale=scaler.get_scale();scaler.step(optimizer);scaler.update()
                if scaler.get_scale()<scale:raise ValueError('FP16 optimizer step skipped on overflow; switch to FP32 rather than claiming an update.')
                optimizer.zero_grad(set_to_none=True);group_count=0;steps+=1
                exp.s['optimizer_steps']=steps;exp.save()
                if steps>=c['max_steps']:break
        exp.guard();validation=evaluate(model,data['validation'],c['system_prompt'])
        metrics.append({'epoch':epoch+1,'examples':len(losses),'epoch_complete':len(losses)==len(order),'loss':sum(losses)/len(losses),'validation_nll':validation['response_nll'],
                        'validation_accuracy':validation['accuracy'],'learning_rate':c['learning_rate'],'optimizer_steps':steps,
                        'mean_gradient_l2':sum(gradients)/len(gradients),'epoch_seconds':time.monotonic()-epoch_start,
                        'examples_per_second':len(losses)/(time.monotonic()-epoch_start),'timestamp':time.time()})
        exp.store.artifact(exp.rid,'training-metrics.json',metrics)
        exp.store.artifact(exp.rid,'latest-validation.json',validation)
        adapter_path=save_adapter(epoch+1)
        exp.s['epoch']=epoch+1;exp.save()
        exp.event('training',f'LoRA epoch {epoch+1}: response loss {metrics[-1]["loss"]:.4f}, validation NLL {validation["response_nll"]:.4f}, optimizer steps {steps}.')
        if steps>=c['max_steps']:break
    after_hash=tensor_hash(trainable)
    changed=sum(int(torch.count_nonzero(before[name]!=p.detach().cpu())) for name,p in trainable.items())
    integrity={'optimizer_steps':steps,'trainable_parameters':sum(p.numel() for p in trainable.values()),
               'total_parameters':sum(p.numel() for p in model.parameters()),'parameters_changed':changed,
               'before_sha256':before_hash,'after_sha256':after_hash,'verified':steps>0 and changed>0 and before_hash!=after_hash,
               'checkpoint_reload_verified':False}
    exp.store.artifact(exp.rid,'training-integrity.json',integrity)
    if not integrity['verified']:raise ValueError('LoRA integrity rejected: zero optimizer steps or unchanged adapter parameters.')
    candidate_validation=evaluate(model,data['validation'],c['system_prompt'])
    # Save probe outputs as data, then release ALL references to the training model/optimizer before reload.
    del optimizer,trainable,before,base,model,loss,batch,norm
    import gc
    gc.collect()
    if c['device']=='cuda':torch.cuda.empty_cache()
    exp.s['phase']='verify';exp.save()
    if _fingerprint(files,exp.guard,root)!=identities:raise ValueError('Base checkpoint files changed during training; comparison rejected.')
    reloaded=PeftModel.from_pretrained(load_base(),str(adapter_path),is_trainable=False,local_files_only=True)
    reload_validation=evaluate(reloaded,data['validation'],c['system_prompt'])
    reload_hash=tensor_hash({name:p for name,p in reloaded.named_parameters() if 'lora_' in name})
    matches=(reload_hash==after_hash and all(a['prediction']==b['prediction'] for a,b in zip(candidate_validation['results'],reload_validation['results']))
             and abs(candidate_validation['response_nll']-reload_validation['response_nll'])<=1e-4)
    integrity['checkpoint_reload_verified']=matches
    exp.store.artifact(exp.rid,'training-integrity.json',integrity)
    if not matches:raise ValueError('Reloaded adapter parameters or validation outputs do not match the saved candidate.')
    exp.store.artifact(exp.rid,'candidate-validation.json',reload_validation)
    candidate_test=evaluate(reloaded,data['test'],c['system_prompt'])
    exp.store.artifact(exp.rid,'candidate-test.json',candidate_test)
    hashes=_fingerprint(list(adapter_path.glob('*')),exp.guard)
    artifact={'format':'gafaw.lora.v1','base_model':str(root),'base_files_sha256':identities,
              'adapter_directory':adapter_path.name,'adapter_files_sha256':hashes,'system_prompt':c['system_prompt'],
              'max_length':c['max_length'],'max_new_tokens':c['max_new_tokens'],'notice':'Real LoRA adapter; base model weights unchanged. Requires the original compatible local base checkpoint.'}
    candidate_hash=exp.store.artifact(exp.rid,'candidate.json',artifact)
    report={'method':'sft_lora','promoted':False,'baseline_accuracy':baseline_test['accuracy'],'candidate_accuracy':candidate_test['accuracy'],
            'baseline_nll':baseline_test['response_nll'],'candidate_nll':candidate_test['response_nll'],
            'test_count':len(data['test']),'dataset_sha256':exp.s['dataset_sha256'],'candidate_sha256':candidate_hash,
            'training_integrity':integrity,'stock_accuracy':stock['accuracy'],'p_one_sided':None,
            'policy':'No automatic generative promotion: exact match and reference-response NLL do not certify style or factual correctness. Review each axis and regressions independently.',
            'scope':'Independent fixed held-out instruction prompts; repeated use is exploratory. Prompted and adapter evaluations share the same system prompt; stock is recorded separately.'}
    exp.store.artifact(exp.rid,'report.json',report);exp.s['report']=report;exp.s['phase']='done';exp.save()
    exp.store.update(exp.rid,status='completed');exp.event('verification','Actual LoRA parameters changed; checkpoint reloaded and matched validation. Held-out stock/prompted/adapter evidence saved. Human assessment remains required.')


def playground(store,rid,prompt):
    """Local manual inference; never changes the experiment's benchmark or model weights."""
    import fcntl
    import resource
    from .lab import config_checked
    run=store.get(rid);config=config_checked(run['config']);c=config['lora']
    if run['status']!='completed' or config['student']['kind']!='local_lora':raise ValueError('Playground requires a completed LoRA experiment.')
    if not isinstance(prompt,str) or not 0<len(prompt)<=4000:raise ValueError('Enter a bounded playground prompt.')
    start=time.monotonic()
    def guard():
        if time.monotonic()-start>config['minutes']*60:raise ValueError('Playground time budget exhausted.')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>config['memory_mb']*1024:raise ValueError('Playground measured RSS exceeded the experiment RAM limit.')
    with store.lock() as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Training or another checkpoint comparison is active.') from None
        root,_,files=checkpoint_files(config['student']['model']);artifact=store.read(rid,'candidate.json')
        if _fingerprint(files,guard,root)!=artifact['base_files_sha256']:raise ValueError('Original base checkpoint changed; comparison rejected.')
        name=artifact['adapter_directory']
        if not isinstance(name,str) or Path(name).name!=name or not name.startswith('adapter-epoch-'):raise ValueError('Invalid adapter path.')
        directory=store.root/rid/name
        if directory.is_symlink():raise ValueError('Adapter directory must not be a symlink.')
        for filename in artifact['adapter_files_sha256']:
            if Path(filename).name!=filename or (directory/filename).is_symlink():raise ValueError('Unsafe adapter artifact path.')
        if _fingerprint([directory/name for name in artifact['adapter_files_sha256']],guard)!=artifact['adapter_files_sha256']:raise ValueError('Adapter artifact hash changed; comparison rejected.')
        adapter_config=_json(directory/'adapter_config.json')
        if adapter_config.get('peft_type')!='LORA' or adapter_config.get('task_type')!='CAUSAL_LM' or adapter_config.get('auto_mapping'):raise ValueError('Only the saved standard causal-LM LoRA adapter is accepted.')
        report=preflight(root,c,config['memory_mb'],store.root,runtime=True)
        if not report['ready']:raise ValueError('; '.join(report['blockers']))
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
        import torch
        from transformers import AutoModelForCausalLM,AutoTokenizer
        from peft import PeftModel
        torch.set_num_threads(min(4,os.cpu_count() or 1));torch.manual_seed(c['seed'])
        tokenizer=AutoTokenizer.from_pretrained(str(root),local_files_only=True,trust_remote_code=False)
        dtype=torch.float16 if c['precision']=='fp16' else torch.float32
        model=AutoModelForCausalLM.from_pretrained(str(root),local_files_only=True,trust_remote_code=False,use_safetensors=True,
                                                 torch_dtype=dtype,attn_implementation='eager').to(c['device'])
        def generate(model,style):
            guard();model.eval()
            messages=([{'role':'system','content':style}] if style else [])+[{'role':'user','content':prompt}]
            ids=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False)
            if len(ids)>c['max_length'] or len(ids)+c['max_new_tokens']>model.config.max_position_embeddings:raise ValueError('Playground prompt exceeds the configured context cap.')
            inputs=torch.tensor([ids],device=c['device'])
            with torch.no_grad():output=model.generate(input_ids=inputs,attention_mask=torch.ones_like(inputs),max_new_tokens=c['max_new_tokens'],do_sample=False,
                                                       pad_token_id=tokenizer.eos_token_id,eos_token_id=tokenizer.eos_token_id)
            guard();return tokenizer.decode(output[0,len(ids):],skip_special_tokens=True).strip()
        stock=generate(model,'');prompted=generate(model,c['system_prompt'])
        adapted=PeftModel.from_pretrained(model,str(directory),local_files_only=True,is_trainable=False)
        trained=generate(adapted,c['system_prompt'])
        trial={'experiment':rid,'mode':'lora','prompt':prompt,'system_prompt':c['system_prompt'],'stock':stock,'prompted':prompted,'adapter':trained,
               'timestamp':time.time(),'notice':'Manual deterministic matched-prompt generations. Human ratings are not part of the independent held-out evaluation.'}
        name=f'playground-{time.time_ns()}.json';store.artifact(rid,name,trial)
        return {**trial,'artifact':name}
