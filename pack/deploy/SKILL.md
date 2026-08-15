---
name: sales-secretary-deploy
description: Déployer l'appliance sales-secretary sur un VPS, étape par étape, sans improviser. À charger dès qu'on ouvre ce dépôt ou qu'on dit « installe le secrétaire ».
---

# Déploiement VPS — workflow rigide

Tu guides un humain (ou tu exécutes sur le VPS si tu y es). **Une question à la fois.** Tu n'avances pas tant que l'étape n'est pas verte.

Ne configure pas Odoo / Ringover / IMAP ici. Ça se fait **après**, dans Telegram, par le wizard du bot.

## Étape 0 — Où tu es

Demande : « Je suis déjà en SSH sur le VPS (linux), ou on est encore sur ton ordi ? »

- Ordi → donne la commande SSH à lancer, **stop**, attends qu'il confirme être sur le VPS.
- VPS → étape 1.

## Étape 1 — Docker

```bash
command -v docker && docker compose version
```

Si ça manque :

```bash
curl -fsSL https://get.docker.com | sh
```

Vérifie à nouveau. Rouge → stop, colle l'erreur.

## Étape 2 — Paquet

Si le dépôt n'est pas là :

```bash
git clone <url-du-dépôt> /opt/sales-secretary
cd /opt/sales-secretary
```

Sinon `cd` dedans. Vérifie que `docker-compose.yml` et `install.sh` existent.

## Étape 3 — Bot Telegram

Dis, mot pour mot :

> Sur Telegram, ouvre @BotFather → /newbot → choisis un nom → copie le token (chiffres:lettres). Colle-le ici, rien d'autre.

Attends le token. Il doit matcher `^[0-9]+:[A-Za-z0-9_-]+$`. Sinon redemande.

## Étape 4 — Clé LLM

Demande **un seul** fournisseur :

> Quelle clé as-tu ? Réponds `openrouter` / `xai` / `anthropic` / `openai`, puis au message suivant colle la clé.

Une clé. Pas les quatre.

## Étape 5 — Écrire `.env` et lancer

```bash
cd /opt/sales-secretary
cp -n .env.example .env
TOKEN=$(openssl rand -hex 24)
# pose TELEGRAM_BOT_TOKEN, SECRETARY_TOKEN=$TOKEN, et LA clé LLM du fournisseur choisi
# laisse les autres clés vides
./install.sh
```

`install.sh` refuse de démarrer si token Telegram ou clé LLM manque.

## Étape 6 — Vérifier

Attends que ce soit vert :

```bash
docker compose ps
docker compose exec ingest python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/healthz').read())"
```

`{"ok": true}` obligatoire. Sinon `docker compose logs --tail=80 ingest hermes` et tu t'arrêtes sur l'erreur.

## Étape 7 — Passation Telegram

Dis :

> Ouvre Telegram, cherche le bot que tu as créé, envoie n'importe quoi. Il va te demander l'URL Odoo, puis une chose à la fois (Odoo, Ringover, IMAP). Réponds à chaque question, ne colle pas tout d'un coup.

Tu n'es plus responsable des credentials métier. STOP.

## Interdit

- Demander Odoo / Ringover / IMAP pendant ce skill.
- Éditer `tenant.yaml` à la main.
- Exposer le port 8080 sur Internet.
- Inventer un token BotFather ou une clé LLM.
- `docker compose down -v` (efface la config).
