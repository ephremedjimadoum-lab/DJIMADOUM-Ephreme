"""Lecture des transcriptions exportées par Teams, Zoom, Google Meet, ou d'un enregistrement audio/vidéo."""

import json
import re
from pathlib import Path

EXTENSIONS_AUDIO = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".mkv", ".mov"}

_HORODATAGE = re.compile(
    r"^(\d{1,2}:)?\d{1,2}:\d{2}([.,]\d{1,3})?\s*-->\s*(\d{1,2}:)?\d{1,2}:\d{2}([.,]\d{1,3})?"
)
_VOIX_VTT = re.compile(r"<v\s+([^>]+)>(.*?)(</v>|$)", re.DOTALL)
_BALISES = re.compile(r"<[^>]+>")


def lire_transcription(chemin: Path, langue: str = "fr") -> str:
    """Renvoie la transcription sous forme de texte « [hh:mm:ss] Orateur : propos »."""
    extension = chemin.suffix.lower()
    if extension in EXTENSIONS_AUDIO:
        return transcrire_audio(chemin, langue)
    if extension == ".docx":
        return _lire_docx(chemin)
    texte = chemin.read_text(encoding="utf-8-sig", errors="replace")
    if extension in (".vtt", ".srt"):
        return parser_sous_titres(texte)
    if extension == ".json":
        return _lire_json(texte)
    return texte.strip()


def parser_sous_titres(texte: str) -> str:
    """Convertit un fichier WebVTT ou SRT en lignes lisibles et fusionne les répliques consécutives d'un même orateur."""
    repliques: list[tuple[str, str, str]] = []
    debut = ""
    for bloc in re.split(r"\n\s*\n", texte.replace("\r\n", "\n")):
        lignes = [l.strip() for l in bloc.strip().split("\n") if l.strip()]
        contenu = []
        for ligne in lignes:
            if ligne.startswith("WEBVTT") or ligne.startswith("NOTE") or ligne.isdigit():
                continue
            if _HORODATAGE.match(ligne):
                debut = ligne.split("-->")[0].strip().split(".")[0].split(",")[0]
                continue
            # Les identifiants de cue Teams (ex. « 8f2c.../12-0 ») précèdent l'horodatage.
            if not contenu and "-->" not in ligne and re.fullmatch(r"[\w-]+/[\w-]+", ligne):
                continue
            contenu.append(ligne)
        if not contenu:
            continue
        brut = " ".join(contenu)
        voix = _VOIX_VTT.search(brut)
        if voix:
            orateur, propos = voix.group(1).strip(), voix.group(2)
        elif re.match(r"^[^:]{1,60}:\s", brut):
            orateur, propos = brut.split(":", 1)
        else:
            orateur, propos = "", brut
        propos = _BALISES.sub("", propos).strip()
        if not propos:
            continue
        orateur = orateur.strip()
        if repliques and repliques[-1][1] == orateur:
            precedent = repliques[-1]
            repliques[-1] = (precedent[0], orateur, f"{precedent[2]} {propos}")
        else:
            repliques.append((debut, orateur, propos))
    return "\n".join(
        f"[{h}] {o} : {p}" if o else f"[{h}] {p}" for h, o, p in repliques
    )


def _lire_docx(chemin: Path) -> str:
    from docx import Document

    return "\n".join(p.text for p in Document(str(chemin)).paragraphs if p.text.strip())


def _lire_json(texte: str) -> str:
    """Accepte une liste de segments {speaker|orateur, text|texte, start|debut}."""
    donnees = json.loads(texte)
    segments = donnees.get("segments", donnees) if isinstance(donnees, dict) else donnees
    lignes = []
    for s in segments:
        orateur = s.get("speaker") or s.get("orateur") or ""
        propos = s.get("text") or s.get("texte") or ""
        debut = s.get("start") or s.get("debut") or ""
        prefixe = f"[{debut}] " if debut != "" else ""
        lignes.append(f"{prefixe}{orateur} : {propos}" if orateur else f"{prefixe}{propos}")
    return "\n".join(lignes)


def transcrire_audio(chemin: Path, langue: str = "fr", modele: str = "medium") -> str:
    """Transcrit un enregistrement en local avec faster-whisper (dépendance optionnelle)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as erreur:
        raise SystemExit(
            "Pour transcrire un fichier audio/vidéo, installez faster-whisper :\n"
            "    pip install faster-whisper\n"
            "ou fournissez directement la transcription exportée par Teams, Zoom ou Meet (.vtt, .docx, .txt)."
        ) from erreur

    segments, _ = WhisperModel(modele, device="auto", compute_type="auto").transcribe(str(chemin), language=langue, vad_filter=True)
    lignes = []
    for segment in segments:
        secondes = int(segment.start)
        horodatage = f"{secondes // 3600:02d}:{secondes % 3600 // 60:02d}:{secondes % 60:02d}"
        lignes.append(f"[{horodatage}] {segment.text.strip()}")
    return "\n".join(lignes)
