# Mise a jour des resultats

`live-data.json` est maintenant destine a etre regenere automatiquement par GitHub Actions toutes les 15 minutes via `scripts/update_live_data.py`.

Le workflow attend un secret GitHub nomme `FOOTBALL_DATA_API_KEY`, avec une cle API `football-data.org` stockee cote serveur.

Exemple pour le match 17 :

```json
{
  "matchNumber": 17,
  "status": "FINISHED",
  "homeScore": 2,
  "awayScore": 1
}
```

Valeurs de `status` : `SCHEDULED`, `LIVE`, `FINISHED`.

Pour corriger un horaire ou un stade, ajouter facultativement :

```json
{
  "date": "2026-06-16T21:00:00+02:00",
  "stadium": "New York New Jersey Stadium"
}
```

Chaque modification doit aussi actualiser `updatedAt`. Un match termine doit toujours avoir les deux scores.
