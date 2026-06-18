# maximethomas16-cell.github.io

Site public de Widget CDM 2026, heberge avec GitHub Pages.

- Politique de confidentialite : `/privacy-policy.html`
- Contact et support : `/contact.html`
- Horaires et resultats publics : `/data/live-data.json`

## Automatisation des resultats

Le fichier `data/live-data.json` peut etre regenere automatiquement via le workflow GitHub Actions `.github/workflows/update-live-data.yml`.

Pre-requis :

- ajouter le secret GitHub `FOOTBALL_DATA_API_KEY`
- verifier que GitHub Actions est active sur le depot

Le generateur Python s'appuie sur :

- `scripts/reference/teams_2026.json`
- `scripts/reference/official_schedule_2026.json`

Commande locale :

```bash
python scripts/update_live_data.py
```
