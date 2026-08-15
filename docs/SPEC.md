# Secrétaire commercial — spec v0.1

Appliance autonome (pas SuperPagr) : un VPS, `docker compose up`, un bot Telegram.

## Décisions

| Sujet | Choix |
|---|---|
| Produit | Packagé, N déploiements indépendants |
| Canal | Telegram |
| Appels | API Ringover (clé collée au chat) |
| Mails | IMAP (mot de passe d'application) |
| CRM | Odoo : partner, lead, chatter, activité, tâche projet |
| Brouillon mail | Note chatter « BROUILLON MAIL — non envoyé ». Jamais `mail.mail` outgoing (le cron Odoo l'enverrait). |
| Autonomie | Carte puis `ok` / `ignore` / modification |
| Config | Deux wizards figés : `pack/deploy/SKILL.md` (VPS) puis `GET/POST /onboard` (credentials métier). L'IA ne choisit pas l'ordre. |
| Archi | Ingest déterministe + Hermes seulement pour juger |

## Composants

```
ingest   FastAPI + poller (0 token)
         Ringover GET /v2/calls + Empower /public/empower/call/:uuid
         IMAP UID
         SQLite ledger
         writer JSON-RPC Odoo
hermes   image officielle, gateway Telegram
         skills sales-onboard / sales-inbox / sales-apply
         helper /opt/data/scripts/sec
```

Hermes n'a pas les secrets métier. Ils vivent dans `/data/tenant.yaml` (volume ingest).

## Flux

1. IA locale suit `pack/deploy/SKILL.md` jusqu'à ingest healthy.
2. Client → Telegram : wizard `/onboard` (une réponse = une étape, sonde incluse). `done` → cron `every 5m` + premier `POST /poll`.
3. Ingest poll 3 min → événements `new` (id `ringover:call:{id}` / `imap:{folder}:{uidvalidity}:{uid}`).
4. Cron Hermes : cartes `carded`, message Telegram.
5. `ok` → `POST /apply` → writer. `ignore` → plus jamais représenté.

## Idempotence

Contrainte unique `(source, external_id)`. Un second apply reprend `odoo_ids` et ne recrée pas partner/lead/activité/tâche.

## Hors v1

Envoyer le mail, webhook Ringover, WhatsApp, changer le stage tout seul, devis Odoo, calendrier.
