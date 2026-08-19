# Contributing

Thanks for contributing to **QuickTalk / Sales Secretary** (open-source sales ops appliance).

## Ground rules

1. **Nothing writes to Odoo before human `ok`** — keep that invariant.
2. **Never commit secrets** — Telegram tokens, LLM keys, IMAP, Ringover/QuickTalk credentials, `tenant.yaml`.
3. Prefer small PRs; document setup impact in `README.md` / `FOR-AI.md`.
4. Tests when touching parsers or onboarding wizard.

## Local setup

See `README.md` and `FOR-AI.md`. Typical path: Docker + `./install.sh`, then Telegram onboarding.

## Pull requests

- Describe change + how you tested.
- Do not add undisclosed outbound telemetry.

## Security issues

See [SECURITY.md](./SECURITY.md).
