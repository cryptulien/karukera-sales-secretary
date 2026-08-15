---
name: sales-inbox
description: Transformer les événements new (appels Ringover, mails IMAP) en cartes Telegram. Cron toutes les 5 min, ou « y a-t-il du nouveau ».
---

# Inbox → cartes

CLI : `python3 /opt/data/scripts/sec METHOD /path`

## Procédure

1. `GET /status`. Si `configured: false` → une ligne « pas encore configuré », stop (ou `[SILENT]` en cron).
2. `GET /inbox?status=new&limit=10`. Vide → `[SILENT]` (cron) ou « Rien de nouveau ».
3. Pour **chaque** événement, une carte :
   - `POST /odoo/match` `{phone, email}` extraits du payload.
   - Rédige résumé + propositions (lead, activité, tâche, brouillon mail).
   - Dates d'activité : jour ouvré suivant, 09:00, timezone du tenant.
   - Si match partner/lead : `is_new=false`, reprends les ids.
   - `POST /inbox/{id}/card` avec le JSON `ApprovalCard` (schéma ci-dessous).
4. Envoie **une carte par message Telegram**, format humain + l'id technique en dernière ligne (`id: ringover:call:42`).

## Format Telegram

```
📞 Appel · {nom} · {téléphone}
{quand} · {durée} · {direction}

Résumé
{3 lignes max}

Proposition
• Lead « … » ({nouveau|existant})
• Activité {type} {date} → {user}
• Tâche « … » projet {nom}
• Brouillon mail « objet »

Réponds ok / ignore / ou précise la modif.
id: {event_id}
```

Mails : préfixe `✉️ Mail ·`.

## JSON carte (`POST /inbox/{id}/card`)

```json
{
  "card": {
    "event_id": "…",
    "kind": "call",
    "contact": {"name": "", "phone": "+33…", "email": "", "partner_id": null, "is_new": true},
    "lead": {"name": "", "lead_id": null, "team_id": null, "stage_id": null, "user_id": null},
    "activity": {"summary": "", "activity_type_id": null, "date_deadline": "YYYY-MM-DD", "user_id": null},
    "task": {"name": "", "project_id": null, "user_id": null, "description": ""},
    "mail_draft": {"subject": "", "body": "", "email_to": ""},
    "skip": {"activity": false, "task": false, "mail_draft": false},
    "chatter": "transcription ou corps",
    "summary": "résumé court"
  }
}
```

Les `*_id` nuls sont remplis par les défauts du tenant au moment du `ok`.

## Interdit

- `POST /inbox/{id}/apply` depuis ce skill.
- Inventer un numéro, un mail ou un engagement.
- Plus de 10 cartes par run.
