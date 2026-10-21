# GAFAW laboratory workflows

GAFAW means **Great, Another Fucking AI Workbench**. The application remains a local-first GTK 3 laboratory with no telemetry, mandatory account, cloud service, or automatic downloads. It preserves the MIT license, `overmind` Python module, `./run.sh`, private `lab-data/` storage, `.overmind-lab` marker, SQLite schema, existing configuration, and `overmind.softmax.v1` checkpoint compatibility. The remote and development branch are unchanged.

## Start with actual weight training

```bash
./run.sh
# Or run a complete bounded experiment without GTK:
./run.sh run --epochs 8
./run.sh list
```

In Configure, leave Curriculum controller and CPU text classifier selected. Use the built-in CC0 benchmark, run the experiment, and inspect Laboratory and Evidence & artifacts. Eight epochs are a small demonstration, not a universal training prescription. A promotion still requires held-out improvement, the existing exact paired test, no per-label regression, and complete training-integrity evidence. A failed promotion preserves its evidence.

The selected frozen checkpoint is reloaded before the held-out evaluation. `training-integrity.json` records the base/candidate parameter fingerprints, changed-parameter count, SGD example steps through the selected checkpoint, and prediction equivalence with its saved validation result. Report hashes still refer to the original disk artifacts. An unchanged candidate is rejected even if a backend claims to have taken optimizer steps. Legacy checkpoints without counters remain readable; recovery without complete integrity/reload evidence blocks fresh promotion.

`training-metrics.json` records actual per-epoch mean cross entropy, validation accuracy, learning rate, mean per-example gradient L2 norm, cumulative optimizer steps, duration, and examples/second. Extra practice examples count as SGD steps. Metrics describe the working model at that epoch, while the final candidate is selected by validation accuracy and can come from an earlier epoch. The chart displays persisted epoch losses, not generated neural activity. Abrupt interruption can leave missing metric rows; missing measurements are not reconstructed.

`environment.json` records Python/platform/library versions and application source-file SHA-256 hashes. Classifier training uses shuffle seed `42 + epoch`, independently of the dataset split seed. Worker resource limits, pause/recovery, external-model call limits, and explicit cloud/data-sharing consent remain in force.

## Dataset Workshop

CSV requires a header:

```csv
input,target
Please refund this payment,billing
Help me change my profile,account
```

TSV and TXT use the same header with tabs. JSONL uses one object per line:

```json
{"input":"Please refund this payment","target":"billing"}
```

An optional `split` column/field must be supplied for **all** rows, using `train`, `validation`, or `test`. Existing dataset JSON retains its authored splits and license. Newly imported files require a license or permission statement. Supported limits remain 2–32 labels, 8–5,000 rows per split, at most 10,000 rows total, 4,000 characters per input, and 8 MB per source.

For unassigned rows, the Workshop normalizes Unicode/case/whitespace to deduplicate before seeded stratified splitting (approximately 70/15/15, rounded per label). Conflicting labels are rejected. Duplicate inputs across explicit splits are rejected. Every label must occur in each split. Small datasets can fail the minimum row requirements even when each label has three examples; add more independently authored examples. Semantic/paraphrase duplicates require human review. This is exact-overlap protection, not a claim to detect all leakage.

Import a file, review/edit JSONL in the editor, then choose **Validate & use reviewed data**. The selected reviewed dataset is copied into the next experiment snapshot. Editing the buffer later does not silently alter that selected snapshot: validate/use again. **Export new dataset version** creates a mode-0600 JSON file and refuses to overwrite any existing file. Choose a dedicated dataset directory outside the managed laboratory root; the existing Store intentionally rejects unrelated files at its top level. Exported versions record content/source fingerprints and review parent lineage. The displayed token count is an explicitly labeled character estimate, not tokenizer output.

```bash
./run.sh prepare-dataset tickets.csv tickets-v1.json --license CC0-1.0 --seed 42
./run.sh run --dataset tickets-v1.json --epochs 8
```

No synthetic-example generation is added in this version. Imported examples remain human-reviewed classification data; mentors do not receive held-out examples through the normal experiment path.

## Hardware and model inspection

```bash
./run.sh hardware
./run.sh inspect-model /path/to/local/hf-checkpoint
./run.sh models ollama
```

Hardware & Models reports actual CPU/RAM/disk and available NVIDIA driver metadata, plus AMD PCI presence where exposed by sysfs. It does not load PyTorch on the GTK thread. CUDA/ROCm runtime and kernel compatibility stay **unverified**. A working driver or installed library is not proof of working GPU training. GTX 1080 Ti/Pascal guidance explicitly excludes BF16. No QLoRA or GPU model-fit guarantee is made. NVIDIA driver query support varies; missing detail is reported as unavailable rather than inferred.

Local model inspection reads bounded `config.json` metadata, safe weight filenames, tokenizer-file presence, top-level storage, adapter-config presence, custom-code declarations, and license-file evidence. It neither validates tensor contents nor executes remote/custom code, loads pickle, downloads files, grants licenses, or establishes training compatibility. Ollama/API discovery remains separate inference-only access. No Model Manager installation or download workflow is claimed.

## Notebook, comparisons, and bundles

Select an experiment in the sidebar, open Notebook & Compare, write Markdown, and save. Unsaved notes survive experiment switching within the current session, but require Save for persistence across application restarts. Notes are stored through the same private/redacting artifact writer.

Failure inspection aligns baseline/candidate held-out predictions and groups regressions, improvements, and persistent failures. Comparing two completed runs reads recorded results, reports dataset fingerprints and methods, and adds 95% Wilson accuracy intervals. Different dataset/method combinations suppress the score difference. Differences in configuration, baseline, or hardware still need human interpretation. Repeated holdout use is exploratory, not a fresh independent test or proof of statistical superiority.

```bash
./run.sh compare LEFT_ID RIGHT_ID
./run.sh export-bundle RUN_ID evidence.zip
./run.sh check-bundle evidence.zip
# Explicit local opt-in to include dataset text and CPU classifier artifacts:
./run.sh export-bundle RUN_ID full-evidence.zip --include-dataset --include-weights
```

The desktop exports minimized evidence: configuration, available reports/metrics/environment/notes, and evaluation rows with input hashes instead of dataset text. Dataset text and classifier weights require explicit CLI flags. Configuration, labels, and notes can still contain private information; inspect before sharing. Known credential patterns/session keys are redacted, not proof of universal secret detection. Bundles are private mode-0600 ZIP files with a JSON SHA-256 manifest. Checksums detect accidental/content changes relative to the manifest; they do not authenticate a publisher. Validation has bounded entry/expanded sizes, rejects unsafe paths/duplicates/checksum mismatches, and parses JSON without extracting or executing code. Bundle import into the experiment Store and experiment replay are not implemented.

## Theme and terminal

The reusable [Skin Library](skins.md) supports multiple local skins, live switching with saved preference, and validated `.gafawskin` import/export. Black Titanium remains the default; Phosphor Night is a second built-in. Skin textures and manifests are separate from application logic.

The dependency-free `tools/generate_skin.py` generates original brushed titanium, phosphor LCD, and flask-emblem SVGs. GTK CSS supplies beveled normal/hover/pressed/disabled controls, inset surfaces, visible focus, and real progress widgets. These are native keyboard-operable GTK controls, not a background screenshot. No Winamp assets are used. Manual HiDPI/accessibility/resizing acceptance remains pending.

Open Terminal Here / Ctrl+Shift+T opens the selected experiment directory, or laboratory root when none is selected. It uses a subprocess argument list, a working directory, and an allowlisted environment which retains desktop transport variables but strips API credentials. If no supported terminal is installed, a permanent sidebar status displays the directory for manual use. Opening a terminal depends on the user's desktop/session and terminal installation; terminal subprocess invocation has fixture coverage, not a claim of testing every terminal emulator.

## Implementation status

| Area | Working now | Remaining |
| --- | --- | --- |
| Desktop | GAFAW branding, original Black Titanium assets, native controls, terminal action | Manual accessibility/HiDPI/resizing acceptance; additional artwork |
| Data | Bounded imports, editable review, fingerprints, exact dedupe, reproducible/preserved splits, immutable export | True tokenizer counts, general task schemas, synthetic lesson review |
| Models/hardware | Local metadata inspection, existing provider discovery, bounded hardware reality checks | Full inventory lifecycle, downloads, verified CUDA/ROCm training |
| Training | Existing CPU SGD classifier; counters, parameter/reload verification, independent evaluation, actual epoch chart | Generative SFT/LoRA/QLoRA, adapter training and apprenticeship |
| Science | Existing budgets/evidence, notes, recorded comparisons/intervals, paired failure inspection, source/environment snapshots | Ablations, bounded hyperparameter searches, educational curricula |
| Portability | Minimized/opt-in evidence export, checksum-only inspection | Import/replay and licensed external model packaging |
| Compute | Existing isolated local worker and recovery | Multi-job scheduler, registered remote workers, distributed training, automation API |

No fake controls for absent backends are added. PyTorch/Transformers/PEFT/Accelerate are absent in the implementation environment; no dependency/model downloads or system-wide installs were performed. Real generative LoRA and mentor-to-LoRA apprenticeship are deferred, not simulated with prompt changes. Existing prompt optimization, cloud mentors, lexical RAG, classifier training, security protections, and persistence remain separate workflows.

## Verification

```bash
python3 -B -m unittest discover -s tests -q
python3 tools/desktop_smoke.py --experiment  # requires a logged-in display with GTK 3
python3 -m overmind.secret_scan
```

The GTK smoke uses a temporary laboratory and an actual bounded CPU worker, reviews the benchmark through the Workshop, verifies checkpoint integrity and the rendered loss graph, inspects failures, and saves notes. Its PNG is written to `/tmp/gafaw-desktop.png`; offscreen capture omits window-manager decorations/header. Tests use fixtures for GPU metadata, terminal subprocess invocation, malicious model metadata, and malformed bundles. They do not validate physical GPUs, terminal installations, hosted inference, LoRA, remote machines, or clusters.

### Verification record · 2026-10-20

- Unmodified baseline: 96 unit/integration tests passed.
- Final complete suite: 113 tests passed in 117.246 seconds; no skips or failures.
- Real GTK smoke: dataset review → actual isolated CPU worker → selected checkpoint reload/parameter checks → held-out evaluation → persisted loss graph → failure inspection → saved notes. Temporary two-epoch result: 10/40 baseline, 21/40 candidate. This is a workflow fixture, not a general capability claim.
- Focused checks covered deterministic/deduplicated splits, conflicting labels and explicit-split leakage, private immutable exports, nonexecuting model metadata inspection, zero-update rejection despite claimed steps, legacy checkpoint reload, paired failure alignment, uncertainty intervals, terminal argument/environment handling, unsafe/tampered bundles, and conservative mocked Pascal guidance.
- Tracked-file secret scan and whitespace check passed. No optional ML dependencies/models were downloaded or installed. No physical GPU, live provider/cloud generation, remote worker, or distributed cluster was tested in this run.
- Manual HiDPI, keyboard/accessibility, resize acceptance, and launching every supported terminal emulator remain unverified. Runtime hardware and metadata presence remain diagnostics, not backend qualification.
