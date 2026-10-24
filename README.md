# DataWise
A data analysis project for extracting insights and supporting data-driven decisions.

## Agent IA de comptes rendus de réunions

`agent_compte_rendu` prend les notes de vos réunions en ligne (Teams, Zoom, Google Meet…) et rédige automatiquement un compte rendu professionnel en français, en s'appuyant sur Claude.

### Ce que produit l'agent

- **En-tête** : date, durée, participants et leur rôle, objet de la réunion
- **Résumé exécutif** pour les absents
- **Points abordés**, dans l'ordre chronologique, avec les positions de chacun
- **Décisions** prises (séparées des simples propositions)
- **Plan d'action** : tâche, responsable, échéance, priorité
- **Questions en suspens** et **prochaine réunion**

Sorties : Word (`.docx`), Markdown (`.md`) et, si besoin, JSON (`.json`) pour l'intégrer à d'autres outils.

### Installation

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="votre-clé"        # clé à créer sur https://console.anthropic.com
```

Sous Windows (PowerShell) : `$env:ANTHROPIC_API_KEY="votre-clé"`.

### Utilisation

1. Pendant la réunion, activez la **transcription** de votre outil :
   - **Teams** : *Plus › Enregistrer et transcrire › Démarrer la transcription*, puis téléchargez le `.vtt` ou le `.docx`
   - **Zoom** : activez l'*enregistrement cloud avec transcription audio* et téléchargez le `.vtt`
   - **Google Meet** : *Activités › Transcriptions* ; le document arrive dans Google Drive (à exporter en `.docx` ou `.txt`)
   - À défaut, un simple **enregistrement audio/vidéo** suffit (voir plus bas).
2. Lancez l'agent :

```bash
python -m agent_compte_rendu exemples/reunion_exemple.vtt
```

Avec plus de contexte, pour un compte rendu plus précis :

```bash
python -m agent_compte_rendu transcription.vtt \
  --titre "Comité de pilotage e-commerce" \
  --date "24/10/2026" \
  --participants "Awa Mahamat (DG), Paul Ngarta (DSI), Fatimé Abakar (Marketing)" \
  --contexte "Lancement du site prévu en décembre ; CFA = francs CFA" \
  --formats docx,md,json \
  --sortie comptes_rendus
```

Les fichiers sont enregistrés dans `comptes_rendus/` sous la forme `AAAA-MM-JJ_titre-de-la-reunion.docx`.

| Option | Rôle |
|---|---|
| `--titre`, `--date`, `--participants` | Complètent ce qui n'est pas dit dans la transcription |
| `--contexte` | Ordre du jour, sigles, noms de projets : aide l'IA à bien comprendre |
| `--formats` | `md`, `docx`, `json` (défaut : `md,docx`) |
| `--effort` | Profondeur d'analyse : `low` (rapide) à `max` (le plus soigné). Défaut : `high` |
| `--langue` | Langue parlée, pour la transcription audio (défaut : `fr`) |

### Formats acceptés

| Source | Extensions |
|---|---|
| Transcriptions Teams / Zoom / sous-titres | `.vtt`, `.srt` |
| Transcriptions Meet / Teams en document | `.docx`, `.txt` |
| Segments issus d'un autre outil | `.json` (`speaker`/`text`/`start`) |
| Enregistrements | `.mp3`, `.mp4`, `.m4a`, `.wav`, `.webm`, `.ogg`, `.mkv`, `.mov` |

Pour les enregistrements, installez en plus `pip install faster-whisper` : la transcription se fait alors sur votre ordinateur avant l'envoi du texte à Claude. Les orateurs ne sont pas identifiés dans ce cas ; utilisez `--participants` pour aider l'agent.

### Utilisation depuis Python

```python
from pathlib import Path
from agent_compte_rendu.agent import rediger_compte_rendu
from agent_compte_rendu.rendu import en_docx, en_markdown
from agent_compte_rendu.transcription import lire_transcription

cr = rediger_compte_rendu(lire_transcription(Path("reunion.vtt")), date="24/10/2026")
print(cr.resume)
for action in cr.actions:
    print(action.responsable, "→", action.tache)
en_docx(cr, Path("compte_rendu.docx"))
```

### Fonctionnement

1. `transcription.py` lit le fichier, nettoie les balises et regroupe les répliques par orateur.
2. `agent.py` envoie la transcription à Claude (`claude-opus-5-5`) avec des consignes de rédaction : fidélité stricte (rien d'inventé), distinction décision / proposition, suppression des apartés techniques. La réponse est contrainte au format défini dans `modeles.py`, ce qui garantit un compte rendu toujours complet et bien structuré.
3. `rendu.py` met en page le résultat en Word et en Markdown.

Les consignes de rédaction se modifient dans `agent_compte_rendu/agent.py` (variable `CONSIGNES`), par exemple pour imposer le modèle de compte rendu de votre organisation.

### Confidentialité

La transcription est envoyée à l'API d'Anthropic pour être analysée. Prévenez les participants que la réunion est transcrite et vérifiez que cela respecte les règles de votre organisation.

### Tests

```bash
pip install pytest
python -m pytest tests
```
