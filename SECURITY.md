# Security Policy

AutoWebDelivery is a **proof-of-concept** and is not production-hardened. It has not been
security-reviewed, load-tested, or operated long-term. Automated CI runs a secrets scan
(gitleaks) and a dependency audit (pip-audit) on every push.

## What is intentionally kept OUT of this public repository

This repository is public and curates only implementation source, tests, and public
documentation. The following are **never committed** and are excluded via `.gitignore`:

- `autowebdelivery-orchestrator-pack/` — internal AI-agent operating protocols, audit
  reports, findings registries and sprint plans. Kept private on purpose.
- `.kilo/` and any other local agent/tool state.
- `config/run_config.json` — run-specific configuration (the committed template is
  `config/run_config.example.json`).
- Secrets of any kind: `.env`, API keys, tokens, `*.pem`/`*.key`/`*.crt`/`*.p12`/`*.pfx`,
  service-account and Google credential files.
- Local artifacts: `__pycache__/`, screenshots, generated preview sites, databases,
  `*.log`, OS/editor noise (`.DS_Store`, `.vscode/`, `.idea/`).

If you are working in this repository, verify **before every commit**:

```bash
git status --short                 # no unexpected files (local state, run config, logs)
git diff --staged --stat           # only intended files staged
git diff --staged                  # review the actual diff
git grep -l "/Users/" -- '*.md' '*.py' '*.json'   # no local absolute paths
git grep -iE 'api[_-]?key|secret|password'        # no stray secrets in tracked files
```

Never stage with `git add -A`/`git add .`; use explicit paths.

## Reporting a vulnerability

If you find a security issue in this codebase:

1. **Do not open a public issue.** Email the maintainer (see `CONTRIBUTING.md` -> Author)
   with the details, or open a private advisory via GitHub's **Security → Report a
   vulnerability** for this repository.
2. Include: affected file(s)/function(s), a minimal reproducer, and impact.
3. Do not disclose the issue publicly until the maintainer has had a chance to respond.

The maintainer will acknowledge within a reasonable timeframe and work toward a fix.

## Disclosure

This is a proof-of-concept, and the maintainer cannot commit to SLAs or security
guarantees. Please still report issues — they are taken seriously and addressed in order
of impact.

## Dependency and secret scanning

CI enforces, per push:

| Job | Tool | Purpose |
|---|---|---|
| Ruff | `ruff check packages/ tests/ templates/` | lint |
| Pytest (3.10 / 3.12) | `uv run --no-sync python -m pytest tests/ -q` | full test suite |
| Gitleaks | `gitleaks detect` | secrets scan |
| Dependency audit | `pip-audit` | known-vulnerability check |