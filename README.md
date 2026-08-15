# Secrétaire commercial

Appliance **plug-and-play** : Hermes lit les **mails** et les **appels Quicktalk / Ringover**, propose une carte dans **Telegram**, et au `ok` met à jour **Odoo** (contact, opportunité, activité, tâche, brouillon de mail).

Rien n'écrit dans Odoo avant ton `ok`. Le brouillon de mail est une **note** sur le lead — Odoo n'envoie rien.

Hors stack SuperPagr.

## Setup de A à Z (deux phases, figées)

**Phase 1 — VPS.** Donne ce dépôt à une IA (elle lit `FOR-AI.md` puis `pack/deploy/SKILL.md`) : Docker, clone, token BotFather, **une** clé LLM, `./install.sh`. Pas d'Odoo / Ringover / IMAP ici.

**Phase 2 — Telegram.** Tu écris au bot. Le wizard (`GET/POST /onboard`) pose une question à la fois, sonde, n'écrit `tenant.yaml` qu'à la fin. Le bot n'a pas le droit d'inventer l'ordre.

```bash
curl -fsSL https://get.docker.com | sh
git clone <ce-dépôt> /opt/sales-secretary
cd /opt/sales-secretary
./install.sh    # interactif : token Telegram, puis une clé LLM
```

## Ce que le client voit

```
📞 Appel · Marie Dupont · +33612345678
Hier 16:42 · 0:00 · entrant

Résumé
A rappelé pour le devis cuisine, dispo jeudi matin.

Proposition
• Lead « Devis cuisine — Dupont » (nouveau)
• Activité Appel 2026-08-14 → toi
• Tâche « Relancer devis »
• Brouillon mail « Suite à votre appel »

Réponds ok / ignore / ou précise la modif.
id: ringover:call:42
```

`ok` · `ignore` · `activité vendredi` · `pas de mail`.

## Secrets

| Où | Quoi |
|---|---|
| `.env` | token Telegram, clé LLM, `SECRETARY_TOKEN` |
| volume ingest `/data/tenant.yaml` | Odoo, Ringover, IMAP — écrits par le bot |

La clé Ringover : dashboard → Developer → API key. Coche **Empower** si tu veux les transcriptions.

IMAP Gmail : mot de passe d'application, pas le mot de passe du compte.

## Exploitation

```bash
docker compose logs -f ingest hermes
docker compose exec ingest sales-secretary status
docker compose exec ingest sales-secretary poll
curl -s http://127.0.0.1:8080/healthz   # seulement si tu publies le port
```

L'API ingest n'est **pas** publiée par défaut. Hermes la joint sur le réseau Docker (`http://ingest:8080`).

## Dev

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
docker compose config -q
```

Spec : [`docs/SPEC.md`](docs/SPEC.md).
