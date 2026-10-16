# Contributing

Report bugs through the repository host's **Issues** page. Include Linux distribution, Python version, OVERMIND revision, steps to reproduce, expected/actual behavior and a minimal sanitized error. For provider issues, name the provider/model and describe the request outcome. Never include API keys, authorization headers, private datasets, raw laboratory databases or unsanitized artifacts. Report suspected secret exposure privately to the repository maintainer through the host's private security-reporting channel if available; do not post the secret in a public issue.

For a pull request, fork the repository, create a focused branch, and explain the problem, change and verification. Preserve existing experiments, spending protections and third-party notices. Use fake credentials and mocked responses in tests; do not require paid calls or model downloads. Do not describe prompt/retrieval changes as weight training or fixture outputs as model gains.

From a source checkout with Python 3.12+:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B -m overmind.secret_scan --tracked
# Optional, after reviewing the hook:
git config --local core.hooksPath .githooks
# Before each commit, including new files after staging:
python3 -B -m overmind.secret_scan --staged
```

See [setup](README.md#run) and [scanner limitations](docs/security-hardening.md). Review the actual diff as well: pattern scanning cannot detect every secret or personal detail. Include the test result in the PR and identify any live integration or desktop checks that were not performed. Contributions are offered under the project's MIT license; the benchmark's CC0 and external dependency/model/data licenses remain separate.
