# Security and public-demo boundaries

This repository contains synthetic data only. Do not place real agreements,
transactions, customer data, credentials, or API responses in these workbooks or
commit them to Git.

## API keys

The free demo and unit tests need no OpenAI key. A live agent run needs the
visitor's own `OPENAI_API_KEY`, supplied through their local environment. The
project does not contain or distribute the author's key. `.env` files are
ignored, but an ignored file can still be exposed by screenshots, copy/paste,
or a force-add, so keep credentials out of the repository entirely. Official
[OpenAI Docs](https://developers.openai.com/api/docs/quickstart) describe the
environment-variable setup.

Before any first push, run `python scripts/check_public_safety.py` and inspect
`git status --short` plus `git diff --cached --stat`. If a real key was ever
committed or published, removing it from the latest commit is insufficient:
revoke or rotate it and review the complete Git history.

## What the local controls do and do not do

The deterministic service has demo authorization rules, tenant/customer
filtering, exception states, decimal calculations, and a hash-linked local
audit log. These are learning and portfolio controls, not enterprise security.
The CLI uses a simulated local actor rather than real authentication. The
original read-only evidence tools in `agent.py` are not independently protected
by the service's permission check. The model is prompted to use the calculator
but that call is not yet enforced by the application. Final agent money fields
are floats, although the calculation engine uses Decimal. The local audit file
is tamper-evident, not an independently controlled immutable store.

Do not use this project to process confidential information or make financial
decisions without human verification and substantial additional controls.
