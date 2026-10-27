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

Deux façons de l'utiliser : **le robot Zoom** rejoint lui-même la réunion et l'enregistre, ou vous **fournissez la transcription** après la réunion.

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

### Robot Zoom : l'agent participe à la réunion

Le robot rejoint la réunion Zoom comme un participant (« Assistant compte rendu (enregistrement) »). Il coupe son micro et sa caméra et annonce l'enregistrement dans la discussion. Il enregistre ensuite le son jusqu'à la fin de la réunion, transcrit l'enregistrement sur votre ordinateur, rédige le compte rendu Word et peut l'envoyer par e-mail.

**Gratuit** : le robot utilise le client web de Zoom avec un simple compte gratuit, sans abonnement ni service payant. La transcription (Whisper) tourne sur votre machine. Seule la rédaction par Claude est facturée à l'usage, soit environ 0,10 à 0,30 $ pour une réunion d'une heure.

#### Lancer le robot avec Docker (Windows, Mac, Linux)

**Le plus simple :** installez Docker Desktop, copiez `config.env.exemple` en `config.env` et mettez-y votre clé API. Ensuite, double-cliquez sur `lancer_robot.bat` (Windows), ou lancez `./lancer_robot.sh` (Mac, Linux), puis collez le lien de la réunion. Le premier lancement installe le robot automatiquement.

Ou, en ligne de commande :


1. Installez [Docker Desktop](https://www.docker.com/products/docker-desktop/) (gratuit).
2. Dans ce dossier, construisez l'image une seule fois :

```bash
docker build -t robot-zoom .
```

3. Au début de la réunion (ou quelques minutes avant), lancez :

```bash
docker run --rm -e ANTHROPIC_API_KEY="votre-clé" \
  -v "$PWD/comptes_rendus:/app/comptes_rendus" -v "$PWD/modeles:/app/modeles" \
  robot-zoom "https://us02web.zoom.us/j/85512345678?pwd=AbC123" \
  --titre "Comité de pilotage" --participants "Awa (DG), Paul (DSI)"
```

4. **Si vous êtes l'hôte, admettez le robot depuis la salle d'attente.** Le robot quitte la réunion tout seul quand elle se termine. Le compte rendu arrive dans `comptes_rendus/`, avec l'enregistrement `.mp3` et la transcription `.txt`.

#### Recevoir le compte rendu par e-mail (gratuit avec Gmail)

Créez un [mot de passe d'application Gmail](https://myaccount.google.com/apppasswords), puis ajoutez à la commande `docker run` :

```bash
  -e SMTP_UTILISATEUR="vous@gmail.com" -e SMTP_MOT_DE_PASSE="mot-de-passe-d-application" \
  ... --envoyer-a "vous@gmail.com,collegue@exemple.com"
```

#### Options du robot

| Option | Rôle |
|---|---|
| `--code` | Code secret, s'il n'est pas dans le lien |
| `--nom` | Nom affiché du robot dans la réunion |
| `--attente-max` | Minutes d'attente en salle d'attente avant abandon (défaut : 15) |
| `--duree-max` | Durée maximale d'enregistrement en minutes (défaut : 180) |
| `--modele-whisper` | Qualité de transcription : `small` (défaut), `medium` ou `large-v3`, plus précis mais plus lent |
| `--sans-annonce` | Ne pas écrire le message d'annonce dans la discussion |
| `--envoyer-a` | Destinataires du compte rendu |

#### Lancer le robot sans Docker (Linux)

```bash
sudo apt install pulseaudio ffmpeg xvfb
pip install -r requirements.txt faster-whisper playwright && playwright install chromium
pulseaudio --start
xvfb-run -a python -m agent_compte_rendu.zoom "LIEN_ZOOM"
```

#### Bon à savoir

- **Consentement** : le robot porte un nom explicite et annonce l'enregistrement dans la discussion. Prévenez quand même les participants à l'oral : l'enregistrement sans consentement est interdit dans de nombreux pays.
- Si l'organisateur a activé la salle d'attente ou réservé la réunion aux utilisateurs connectés, le robot doit être admis, sinon il ne peut pas entrer.
- Le robot pilote l'interface web de Zoom. Si Zoom la modifie, il peut cesser de fonctionner. En cas d'échec, une capture d'écran `*.erreur.png` est enregistrée dans `comptes_rendus/` pour comprendre ce qui s'est passé.
- L'ordinateur qui lance le robot doit rester allumé pendant toute la réunion.

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
