# Phase Two: local Qwen SFT, Personality Forge, and verification

**Status:** an experimental local generative backend is implemented, integrated with the existing GTK workbench and CLI. This implementation environment has no PyTorch, Transformers, PEFT, or safetensors, no working CUDA driver, and no running Ollama endpoint. Consequently **no Qwen optimizer step, adapter reload, or live conversational improvement was measured here**. Missing-dependency diagnostics were exercised through the real GTK-to-worker path. Use the opt-in tiny-model check below before trusting this backend with a pretrained checkpoint. Classifier tests are not evidence that generative training works.

## Urgent Configure UX

Wheel events over spin buttons, combo boxes (including model/skin selectors), and range controls are forwarded to their containing scrollable page; they never change a parameter. Keyboard bindings, explicit +/- actions, text entry and dropdown selection retain GTK behavior. This applies to all tabs and dynamically added controls.

**Reset to Defaults** resets only the next experiment: mentor/controller and CPU classifier, model IDs/URLs, objective, built-in dataset, fresh classifier, epochs **18**, wall minutes **15**, calls **240**, worker memory **512 MB**, candidate count **3**, cloud rates/budget **0**, cloud output cap **2048**, and all dispatch/paid-use permissions off. It also restores the optional LoRA form to CPU FP32, rank 8/alpha 16, context 256, step cap 20, accumulation 1, generation cap 48, learning rate 0.0002, and an empty style/license. Credentials, skins, dataset-editor drafts, saved notes and experiments are retained. Configure settings are not persisted across sessions, so there is no hidden saved configuration to reset. Reset is reversible editing of the next run, not a data-deletion action.

## Isolated optional dependencies

Normal `./run.sh`, GTK, classifier training, skins and saved evidence need no ML stack. The generative worker uses `.venv-llm/bin/python` if that fixed local environment exists; otherwise it uses the current interpreter. Imported configurations cannot nominate executable paths.

Creating/installing this environment is an **explicit user action**. No installation or weight download was performed during development:

```bash
python3 -m venv .venv-llm
# Choose ONE hardware-compatible PyTorch build using the official installation guide.
# Example for CPU-only use (this downloads a substantial optional dependency):
.venv-llm/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv-llm/bin/python -m pip install -r requirements-training.txt
```

For CUDA, select an appropriate PyTorch/CUDA build from [PyTorch's official installation guide](https://pytorch.org/get-started/locally/), not the CPU command above. Driver presence does not guarantee the selected wheel supports Pascal. The requirements file bounds the initial Transformers 4.x/PEFT API range; it is not a tested dependency lock. Qwen3 needs a sufficiently recent Transformers release in that range. Runtime preflight verifies actual imports, tokenizer/config loading and, for CUDA, a precision-specific forward/backward kernel. No BF16, FlashAttention, bitsandbytes/QLoRA, device-map offloading, multi-GPU or remote worker is enabled by this backend. CPU uses FP32; CUDA offers FP32 or FP16. FP16 adapter parameters are kept in PEFT's standard trainable precision, with loss scaling and overflow rejection.

The implementation follows the existing [Transformers Qwen2 model API](https://huggingface.co/docs/transformers/model_doc/qwen2), [PEFT LoRA configuration](https://huggingface.co/docs/peft/package_reference/lora), and [PEFT checkpoint loading](https://huggingface.co/docs/peft/package_reference/peft_model). It uses PyTorch AdamW and gradient accumulation/clipping directly for this narrow single-device loop; TRL and a second scheduler/framework are not required.

## First opt-in real CPU smoke

After installing compatible dependencies:

```bash
.venv-llm/bin/python tools/lora_smoke.py
```

The script creates a tiny, random **actual Qwen2 causal architecture**, tokenizer and reviewed seed data in a temporary directory. It starts the normal worker, takes two real optimizer steps, requires adapter parameter changes, saves/reloads, compares validation, runs stock/prompted/adapter generation, exports/checks an adapter bundle, and runs an intentionally sabotaged zero-update negative control. It downloads no pretrained model. Random tiny Qwen is an integration fixture, **not** evidence of pretrained Qwen quality. The script exits with `UNAVAILABLE` and code 2 when dependencies are missing; that outcome is not a passed training test.

## Select the right model

Select a standard **Qwen2/Qwen2.5 or Qwen3 causal-LM** HF checkpoint folder with:

- `config.json`, local `tokenizer.json`, tokenizer metadata with a chat template and EOS token;
- unquantized `model.safetensors` or local safetensors shards with a safe index;
- a model license you have reviewed and permission to train/use the weights.

The initial backend rejects GGUF/Ollama blobs, pickle/PyTorch `.bin`/`.pt`/`.pth`, custom `.py` code, `auto_map`, prequantized configurations, and symlinks. If using a linked HF cache snapshot, copy the needed checkpoint/tokenizer files to a clean regular-file folder first. Other model families and checkpoint layouts remain unsupported. There is no automatic model download. A served Ollama model supplies inference, not trainable HF tensors.

```bash
./run.sh lora-preflight --model /path/to/local/qwen-checkpoint \
  --model-license 'Your reviewed license identifier' --device cpu --precision fp32 \
  --memory-mb 8192 --max-length 256
```

Preflight uses the isolated worker interpreter. It reports dependency/runtime failures, actual CUDA capability/free VRAM when available, storage, and a conservative model-size/context heuristic. The estimate is **not a fit guarantee or invented duration**. GTX 1080 Ti has no BF16; CUDA/FP16 is permitted only after the actual kernel smoke. Old cards may require a compatible older PyTorch/CUDA build. Start with a small model, short context, microbatch one, low step cap. CPU training of a 0.5B+ model can be slow; throughput is measured only once work occurs.

## Dataset Workshop: reviewed instructions

Use **Load instruction seed** in Dataset Workshop, or **Use editable collaborator example seed** in the Configure LoRA card. The included text is original CC0 material for review, not an automatically generated curriculum or evidence of improvement. Edit/replace the JSONL editor contents and choose **Validate & use reviewed data**. Each row must explicitly declare its split:

```json
{"split":"train","input":"Explain a voltage drop.","target":"Voltage drop is the potential difference across a connection or component while current flows.","axis":"technical"}
```

Supported axes are `instruction`, `technical`, `style`, `consistency`. They annotate examples; they do not provide automatic factual/style grading. Each split needs 2–2,000 examples, at most 5,000 total, with 1–8,000 characters per instruction/response. Exact normalized instruction overlap within/across splits is rejected. Authors must still review paraphrases, answer contamination and provenance. Explicit splits are never inferred from generated lessons. The classification CSV/TSV importer retains its existing label schema; instruction JSONL is reviewed by loading the instruction seed mode and pasting/replacing rows in its editor. Full versioned instruction JSON can be imported using the existing JSON file chooser.

The exported instruction dataset schema is:

```json
{
  "format":"gafaw.sft.v1", "name":"My reviewed instruction data", "license":"Your permission statement",
  "train":["instruction/response row objects"],
  "validation":["independently reviewed row objects"],
  "test":["fixed held-out row objects"]
}
```

The string arrays above illustrate structure, not valid row content. To get a complete valid seed:

```bash
./run.sh example-instructions > instructions-review.json
```

The actual export uses row objects, fingerprints and review lineage. Export creates a private new file; existing versions are never overwritten. Dataset snapshots go into the existing experiment directory. Instruction datasets cannot accidentally run through the classifier/prompt-label backend, or vice versa.

## Run from GTK or CLI

In Configure:

1. Keep **Curriculum controller** as mentor; choose **Local HF Qwen · real SFT + LoRA** as student.
2. Use Discover models to select a local checkpoint folder, enter its license, and inspect compatibility. This first LoRA path uses a fixed reviewed plan; it does not call a mentor or cloud service.
3. Enter an optional Personality Forge style/system prompt. It is distinct from adapter weights.
4. Review/select the instruction data in Dataset Workshop. Set a short context/step cap, epochs and worker RAM/time limits. Switching from untouched classifier defaults suggests one epoch and 8192 MB; review those limits yourself.
5. Run Experiment and inspect the existing Laboratory, Evidence & artifacts, Notebook & Compare. Pause is cooperative between operations; Emergency stop terminates the worker. No separate training mini-app is created.

CLI example configuration:

```json
{
  "objective":"Measure a warmer collaborator style without claiming a factual capability gain",
  "mentor":{"kind":"controller"},
  "student":{"kind":"local_lora","model":"/path/to/local/qwen-checkpoint"},
  "epochs":1, "minutes":15, "memory_mb":8192,
  "lora":{
    "model_license":"Your reviewed license identifier",
    "device":"cpu", "precision":"fp32", "max_length":256, "max_steps":20,
    "rank":8, "alpha":16, "accumulation":1, "learning_rate":0.0002,
    "max_new_tokens":48, "seed":42,
    "system_prompt":"Be warm, direct, technically careful and lightly funny. Label uncertainty."
  }
}
```

```bash
./run.sh run --config lora-config.json --dataset instructions-reviewed-v1.json
```

The worker is offline, uses `trust_remote_code=False` and safetensors, masks prompt tokens from the response loss, and refuses silent example truncation. Rank targets Qwen query/value projections. Optimizer steps are capped, accumulation handles final partial groups, gradients are clipped, nonfinite/overflowed updates are rejected, and only LoRA parameters can be trainable. Epoch loss, validation NLL/exact match, learning rate, gradient norm, step count, duration and throughput are recorded with timestamps. The existing loss plot reads these metrics. No unmeasured attention/activation/VRAM chart is presented.

### Verification and resource boundaries

Stock and prompted held-out responses are measured before training. The same style prompt is used for prompted-base versus adapter evaluation, so that comparison isolates the adapter intervention; stock-without-style is saved separately. Holdout responses are never used in optimizer updates or plan selection. Base/tokenizer files are fingerprinted before training and rechecked before reload. Adapter step counts, trainable/total parameter counts, changed-parameter counts and before/after hashes are recorded. Final verification destroys training references, loads a fresh base and saved adapter, requires adapter hashes and validation outputs/NLL to agree, and evaluates the reloaded model on fixed held-out prompts.

A lower reference-response NLL or higher exact-string match is **not** proof of better factual reasoning or style. Generative runs never automatically promote a model. Human assessment and regressions must be reviewed separately; repeated holdout use remains exploratory. Errors/unsupported runtimes remain failed/limited records with diagnostics, not successful runs.

Classifier workers retain their existing hard virtual-address-space limit. ML runtimes reserve large driver/library mappings, so LoRA uses measured RSS checks at operation boundaries plus a parent RSS/wall-time watchdog. This is a polling limit, not a cgroup or instantaneous hard allocation cap; brief overruns and loading spikes remain possible. The Linux-only implementation is intended for trusted local workers. CPU budget estimates are conservative; CUDA VRAM preflight is not a hard reservation. The CLI and GTK poll the parent watchdog; direct internal worker invocation is not the supported public entry point.

Each epoch boundary (including a stop at the optimizer-step cap) saves a new safetensors adapter directory and then an atomic checkpoint pointer. Metrics record the actual example count and whether the epoch traversed every training example; a step cap can end a partial epoch. Earlier completed checkpoints survive interruption. A partially written directory is not a verified candidate. **Optimizer-state resume is not implemented**: interrupted LoRA runs do not silently restart/replay or overwrite checkpoints. Create a fresh run, preserve the old one, and use only verified completed candidates for comparison. There is no claim of bitwise reproducibility across hardware/library versions.

## Personality Playground

Evidence & artifacts now has three native side-by-side response panes: **stock**, **prompted** (weights unchanged), and **adapter** (when a completed verified LoRA run exists). Use identical prompts and save separate 1–5 human ratings for style, instruction following, technical correctness and consistency; 0 means unrated, saved as null. Ratings identify the saved trial and rated variant. They are not automatically aggregated into a single “intelligence” score. Local memory/tool permissions are not model weights and are not implemented by this slice.

For a fast **prompt-only baseline**, choose an existing local Ollama/compatible endpoint in Configure, enter a style/system prompt, select an experiment to hold the manual trial, and choose the prompt-only comparison action. That explicit action sends two bounded local inference requests using the entered prompt/style, not a dataset upload. It never trains an adapter. The adapter pane says unavailable. If cancelled, an accepted endpoint request may finish, but no second request/result is saved after cancellation. This path was not live-tested here because the local Ollama endpoint is offline.

For a completed LoRA experiment, choose **Compare selected LoRA checkpoint**. It verifies base/adapter fingerprints, loads locally, generates stock/prompted/adapter responses, and saves a manual trial separately from benchmark evaluation. Cancel terminates that comparison process. The worker lock prevents concurrent local training/checkpoint inference in the same laboratory. CLI:

```bash
./run.sh playground RUN_ID 'How should we debug a stubborn fault?'
```

The manual trial and axis-specific feedback stay with the selected experiment and do not alter its held-out report. Existing notes, recorded comparisons and failure grouping are reused. For generative runs, “failures” currently mean exact-reference mismatch; they are not a factual/style classifier. The report and human review retain that distinction.

## Evidence export and remaining work

Existing bundle export includes preflight, model identity, metrics, integrity and checkpoint metadata. Minimized generative evaluation hashes **instructions, reference responses and generated responses**; explicit `--include-dataset` includes them. `--include-weights` includes the adapter's validated safetensors/config/static card, never base weights. Bundles remain bounded/checksummed data, with no extraction or code execution on validation. Configuration and notes can contain private text/paths: inspect before sharing. Base model identifiers/hashes/license are recorded, not bundled license grants.

The foundation is intentionally narrow. Still incomplete: executed pretrained-Qwen evidence in this environment, physical Pascal/CUDA validation, optimizer-state resume, broad model families, QLoRA, long-form automatic factual/style assessment, a bounded autonomous experiment planner, remote/distributed compute, memory/tools, and simulation. The next valuable step is to provision an approved compatible isolated runtime, pass the tiny real Qwen smoke, then run a small licensed pretrained Qwen checkpoint on independently reviewed examples.

## Verification commands

```bash
python3 -m unittest discover -s tests -q
python3 tools/parameter_smoke.py
python3 tools/desktop_smoke.py --skins --experiment
python3 tools/lora_blocked_smoke.py  # missing-dependency environment only
.venv-llm/bin/python tools/lora_smoke.py  # actual opt-in training, requires optional dependencies
```

The normal unit fixtures validate metadata/path/dependency handling; fake safetensors bytes are never trained or described as real model weights. The blocked GTK smoke uses the real process launch and verifies an honest failure with no training-integrity artifact. The full classifier/skin smoke uses actual CPU classifier updates. Those are separate from the opt-in generative test.

### Session verification record

- Complete unit/integration suite: **124 passed in 176.770 seconds**, no failures or skips. ML parameter execution is not part of that suite in this environment.
- Injected GTK wheel events: **26 controls**, **20 scrolling contexts**, deliberate keyboard/step/text edits and complete Reset to Defaults verified. The check includes the visible optional LoRA form and feedback controls.
- Actual GTK classifier/skin workflow: dataset review, isolated CPU classifier worker, checkpoint integrity, plot, failure inspection, notes, skin import/export/live switching passed.
- Actual GTK instruction review → isolated LoRA worker: missing-dependency preflight saved and run failed honestly; no optimizer/reload evidence was created.
- `tools/lora_smoke.py`: exited **UNAVAILABLE (2)** because torch/transformers/peft/safetensors/tokenizers are absent. No pretrained weights, ML stack or paid service was downloaded/used.
- Metadata/path/privacy fixtures cover reviewed instruction isolation, schema separation, unsafe shard/custom-code/pickle/quantization rejection, absent runtime diagnostics, and generative bundle text minimization. These fixtures do not validate real tensor updates or physical GPU support.
- Full generative execution, physical GTX 1080 Ti, live prompt-only endpoint comparisons and manual accessibility/HiDPI acceptance remain unverified.
