# Verification record

Verified in the supplied Linux workspace on 2026-10-15. These are measured results from the actual CPU implementation, not a simulated training service.

## Weight-training experiment

Command: `./run.sh run`

Saved run: [`828cbca0f90a`](../lab-data/828cbca0f90a/report.json)

| Measurement | Result |
| --- | --- |
| Method | Actual CPU softmax SGD weight training |
| Starting student | Zero-initialized, untrained text classifier |
| Train / validation / test | 80 / 24 / 40 original project-authored synthetic examples |
| Epochs | 18 |
| Selected validation accuracy | 95.83% |
| Held-out baseline accuracy | 25% (10/40) |
| Held-out candidate accuracy | 92.5% (37/40) |
| Paired wins / losses | 27 / 0 |
| Exact one-sided paired p | 7.450580596923828e-09 |
| Per-label regressions | None |
| Promotion | Passed the implemented evidence policy |

The baseline is deliberately weak and the benchmark is small. This is evidence that this specific classifier learned this specific task, not evidence of general language-model improvement. The earlier development run used the same benchmark and obtained the same deterministic weights. This repeat is a reproducibility check, not fresh statistical confirmation.

Artifacts: [trained weights](../lab-data/828cbca0f90a/candidate.json), [baseline predictions](../lab-data/828cbca0f90a/baseline-test.json), [candidate predictions](../lab-data/828cbca0f90a/candidate-test.json), [dataset snapshot](../lab-data/828cbca0f90a/dataset.json), [report](../lab-data/828cbca0f90a/report.json). The artifacts remain in the workspace's ignored `lab-data/` directory. Preserve that directory when moving this verification record.

Dataset SHA-256: `f12cd7d7199688c6e359c6830029b4283769c8bd841a4fcd2eda845d75464805`

Candidate SHA-256: `f1278fcd02217b7ee4b0a278364c0da44886ccb1ebdbeb56ba3eb9b69f45a6f9`

Raw [CLI output](evidence/weight-training-run.txt) and [hardware detection](evidence/hardware.json) are retained. Hardware detection reported approximately 15.5 GiB system RAM, 16 logical CPUs, and no working NVIDIA driver. No GPU job was attempted.

## Automated checks

`python3 -m unittest discover -s tests -v` passed **17 tests**. See the [test log](evidence/tests.txt).

Coverage includes actual weight changes and reloadable predictions, reproducible independent final scoring, starting from preserved prior student weights, epoch-cursor recovery, frozen-candidate verification recovery, strict split validation, non-promotion of ties and weak evidence, local-only provider and redirect restrictions, validated mentor command schemas, pre-dispatch call reservations, time/stop guards, and subprocess pause/resume/emergency termination. The subprocess training test also executes the real Linux worker with its memory limit and wall-time alarm installed.

Provider wire tests and both mentor pipelines use explicitly marked fixtures. They verify integration logic; fixture outcomes are not reported as model improvements. No live Ollama or compatible LLM server was available, so real LLM inference and mentor quality remain unverified.

## Desktop checks and limitation

Python module compilation and GTK 3 stylesheet parsing passed. A native GTK launch was attempted, but this restricted execution environment could not connect to its display. A Broadway headless launch was also attempted, but socket creation was denied. No online remote desktop device was available. Consequently **the desktop has not been visually or interactively verified**. Launch `./run.sh` in the normal logged-in Linux session to perform that check; no screenshot or successful graphical launch is claimed.
