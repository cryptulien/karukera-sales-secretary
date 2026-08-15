---
name: sales-apply
description: Appliquer, modifier ou ignorer une carte après le ok du client dans Telegram.
---

# Appliquer une carte

CLI : `python3 /opt/data/scripts/sec METHOD /path`

## Résoudre la cible

- Si le message cite `id: …` → cet événement.
- Sinon `GET /inbox?status=carded&limit=5`.
  - 0 → « aucune carte en attente ».
  - 1 → celle-là.
  - plusieurs → demande laquelle (nom + id).

## Trois verbes

**ignore** — `POST /inbox/{id}/ignore`. Confirme.

**modifie** — réécris le JSON (skip.mail_draft=true, date_deadline, lead.name…).  
`POST /inbox/{id}/card` avec la carte complète. **Renvoie la carte**. Pas d'apply.

**ok** — `POST /inbox/{id}/apply` (le body peut omettre `card` : la dernière carte stockée est utilisée).  
Confirme avec les ids Odoo renvoyés (`partner_id`, `lead_id`, `activity_id`, `task_id`).

## Si apply échoue (502)

Affiche `detail`. Ne réessaie pas en boucle. Propose de corriger la carte.

## Interdit

- Apply sans `ok` explicite (oui, ouais, go, valide = ok).
- Envoyer le mail. Rappeler que c'est un brouillon chatter.
- Créer un deuxième lead si `odoo/match` avait déjà un lead ouvert — mets `lead.lead_id`.
