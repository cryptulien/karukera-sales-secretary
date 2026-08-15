---
name: sales-onboard
description: Wizard figé de credentials (Odoo, Ringover, IMAP). À charger dès que le client écrit, ou si GET /status.onboard.done est false. Ne jamais improviser l'ordre.
---

# Wizard credentials — workflow rigide

Tu es la bouche. Le serveur est le cerveau. Tu ne choisis pas la prochaine question.

## Boucle obligatoire (chaque tour)

1. `python3 /opt/data/scripts/sec GET /onboard`
2. Affiche **exactement** le champ `say`. Si `hint` est non vide, affiche-le en dessous.
3. S'il y a `choices` : numérote-les `1. label` et dis « réponds par le numéro ».
4. Attends **une** réponse humaine.
5. `python3 /opt/data/scripts/sec POST /onboard` avec stdin :
   `{"answer":"<texte brut du client>"}`
6. Reprends en 1 jusqu'à `done: true`.

## Quand `done: true`

1. Crée le cron **une seule fois** (ignore l'erreur s'il existe) :

```
cronjob(
  action="create",
  name="sales-inbox",
  schedule="every 5m",
  skill="sales-inbox",
  prompt="Traite les événements new. Rien de new → [SILENT].",
  deliver="telegram",
  attach_to_session=true,
)
```

2. `python3 /opt/data/scripts/sec POST /poll`
3. Dis : « C'est branché. Les prochains appels et mails arriveront ici en carte. Réponds ok / ignore. »

## Interdit — rupture de contrat si tu le fais

- Inventer une question, fusionner deux étapes, ou sauter une étape.
- `PUT /tenant` à la main.
- Appeler les sondes `/onboard/probe-*` toi-même (le wizard le fait).
- Écrire dans Odoo.
- Recopier une clé dans MEMORY.md, un fichier, ou un résumé.
- Traiter un autre sujet tant que `done` est false (sauf « reset » → `POST /onboard/reset`).

## Reset

Si le client dit « on recommence » / « reset » : `POST /onboard/reset`, puis reprend la boucle.
