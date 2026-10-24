"""Interface en ligne de commande : python -m agent_compte_rendu <transcription> [options]."""

import argparse
import re
import sys
import unicodedata
from datetime import date as date_du_jour
from pathlib import Path

import anthropic

from .agent import rediger_compte_rendu
from .rendu import en_docx, en_markdown
from .transcription import lire_transcription


def _nom_fichier(titre: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", sans_accents).strip("-").lower()[:60] or "reunion"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent_compte_rendu",
        description="Rédige le compte rendu d'une réunion en ligne à partir de sa transcription ou de son enregistrement.",
    )
    parser.add_argument("source", type=Path, help="Transcription (.vtt, .srt, .txt, .docx, .json) ou enregistrement audio/vidéo")
    parser.add_argument("--titre", help="Titre de la réunion (sinon déduit de la transcription)")
    parser.add_argument("--date", help="Date de la réunion, ex. 24/10/2026")
    parser.add_argument("--participants", help="Liste des participants attendus, ex. « Awa (DG), Paul (DAF) »")
    parser.add_argument("--contexte", help="Contexte utile : projet, ordre du jour, sigles…")
    parser.add_argument("--formats", default="md,docx", help="Formats de sortie séparés par des virgules : md, docx (défaut : md,docx)")
    parser.add_argument("--sortie", type=Path, default=Path("comptes_rendus"), help="Dossier de sortie (défaut : comptes_rendus)")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"], help="Niveau de réflexion de l'IA (défaut : high)")
    parser.add_argument("--langue", default="fr", help="Langue parlée, pour la transcription audio (défaut : fr)")
    args = parser.parse_args()

    if not args.source.exists():
        sys.exit(f"Fichier introuvable : {args.source}")

    print(f"Lecture de {args.source.name}…")
    transcription = lire_transcription(args.source, args.langue)
    print(f"Rédaction du compte rendu ({len(transcription.split())} mots de transcription)…")

    try:
        cr = rediger_compte_rendu(
            transcription,
            titre=args.titre,
            date=args.date,
            participants=args.participants,
            contexte=args.contexte,
            effort=args.effort,
        )
    except anthropic.AuthenticationError:
        sys.exit("Clé API invalide ou absente : définissez la variable d'environnement ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        sys.exit("Limite d'utilisation de l'API atteinte, réessayez dans quelques instants.")
    except anthropic.APIConnectionError:
        sys.exit("Impossible de joindre l'API Claude : vérifiez votre connexion internet.")
    except anthropic.APIStatusError as erreur:
        sys.exit(f"Erreur de l'API Claude ({erreur.status_code}) : {erreur.message}")
    except (RuntimeError, ValueError) as erreur:
        sys.exit(str(erreur))

    args.sortie.mkdir(parents=True, exist_ok=True)
    base = args.sortie / f"{date_du_jour.today():%Y-%m-%d}_{_nom_fichier(cr.titre)}"
    formats = {f.strip().lower() for f in args.formats.split(",")}
    if "md" in formats:
        base.with_suffix(".md").write_text(en_markdown(cr), encoding="utf-8")
        print(f"✔ {base.with_suffix('.md')}")
    if "docx" in formats:
        en_docx(cr, base.with_suffix(".docx"))
        print(f"✔ {base.with_suffix('.docx')}")
    if "json" in formats:
        base.with_suffix(".json").write_text(cr.model_dump_json(indent=2), encoding="utf-8")
        print(f"✔ {base.with_suffix('.json')}")

    print(f"\n{len(cr.decisions)} décision(s), {len(cr.actions)} action(s), {len(cr.questions_en_suspens)} question(s) en suspens.")


if __name__ == "__main__":
    main()
