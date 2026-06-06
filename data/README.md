# Mise a jour des resultats

L'application lit `live-data.json` toutes les six heures et lors d'une actualisation manuelle.

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
