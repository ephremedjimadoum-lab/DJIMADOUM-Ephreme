"""Robot qui rejoint une réunion Zoom depuis le client web, l'enregistre puis rédige le compte rendu.

Solution gratuite : navigateur Chromium piloté par Playwright, son capturé avec PulseAudio + ffmpeg,
transcription locale avec faster-whisper. Prévu pour Linux (voir le Dockerfile pour Windows et macOS).

    python -m agent_compte_rendu.zoom "https://zoom.us/j/123456789?pwd=abc" --envoyer-a moi@exemple.com
"""

import argparse
import base64
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, urljoin, urlparse

log = logging.getLogger("robot_zoom")

NOM_PAR_DEFAUT = "Assistant compte rendu (enregistrement)"
PUITS_AUDIO = "robot_zoom"
MICRO_MUET = "robot_zoom_micro"

# Libellés du client web Zoom, en anglais et en français.
_BOUTON_REJOINDRE = re.compile(r"^\s*(Join|Rejoindre)\s*$", re.I)
_BOUTON_AUDIO_ORDINATEUR = re.compile(r"(Join Audio by Computer|audio par ordinateur|audio de l.ordinateur)", re.I)
_BOUTON_QUITTER = re.compile(r"^(Leave|Quitter)", re.I)
_FIN_DE_REUNION = re.compile(
    r"(meeting has been ended|ended by (the )?host|been removed|réunion a été (terminée|clôturée)|"
    r"a mis fin à la réunion|avez été retiré)",
    re.I,
)
_SALLE_ATTENTE = re.compile(r"(waiting room|host will let you in|salle d.attente|l.hôte va vous admettre|has not started|waiting for the host to start|pas encore commencé)", re.I)
_BOUTON_COOKIES = re.compile(r"^(Accept|Accepter)( all| tout| tous)?( cookies| les cookies)?$", re.I)
_LIEN_NAVIGATEUR = re.compile(r"(Join from (your|this) browser|depuis (votre|ce) navigateur)", re.I)
_BLOCAGES = [
    (re.compile(r"(sign in to join|only (authenticated|signed.in) users|connectez-vous pour rejoindre|utilisateurs authentifiés)", re.I),
     "Cette réunion n'accepte que les utilisateurs connectés à un compte Zoom. Dans les paramètres de la réunion, "
     "désactivez « Seuls les utilisateurs authentifiés peuvent rejoindre »."),
    (re.compile(r"(captcha|i.m not a robot|je ne suis pas un robot|verify you are human)", re.I),
     "Zoom demande une vérification « Je ne suis pas un robot » : réessayez dans quelques minutes."),
    (re.compile(r"(invalid meeting id|meeting id is not valid|numéro de réunion (non valide|invalide)|does not exist)", re.I),
     "Numéro de réunion invalide : vérifiez le lien Zoom."),
    (re.compile(r"(wrong passcode|incorrect passcode|code secret (incorrect|erroné))", re.I),
     "Code secret incorrect : utilisez le lien d'invitation complet (avec ?pwd=…) ou l'option --code."),
]


@dataclass
class Reunion:
    numero: str
    code: Optional[str] = None

    def url_client_web(self, nom: str) -> str:
        """Adresse qui force le client web (/wc/join/) au lieu de l'application Zoom."""
        nom_b64 = base64.b64encode(nom.encode()).decode()
        url = f"https://app.zoom.us/wc/join/{self.numero}?prefer=1&un={quote(nom_b64)}"
        if self.code:
            url += f"&pwd={quote(self.code)}"
        return url


def analyser_lien(lien: str, code: Optional[str] = None) -> Reunion:
    """Accepte un lien d'invitation Zoom (…/j/123…?pwd=…) ou un simple numéro de réunion."""
    lien = lien.strip()
    if re.fullmatch(r"[\d\s-]{9,13}", lien):
        return Reunion(re.sub(r"\D", "", lien), code)
    adresse = urlparse(lien if "://" in lien else f"https://{lien}")
    numero = re.search(r"/(?:j|w|s|wc(?:/join)?|my)/(\d{9,12})", adresse.path) or re.search(r"/wc/(\d{9,12})", adresse.path)
    if not numero or not adresse.hostname or not adresse.hostname.endswith("zoom.us"):
        raise ValueError(f"Lien Zoom non reconnu : {lien}")
    pwd = parse_qs(adresse.query).get("pwd", [None])[0]
    return Reunion(numero.group(1), code or pwd)


class EnregistreurAudio:
    """Dirige le son du navigateur vers un périphérique PulseAudio virtuel et l'enregistre avec ffmpeg."""

    def __init__(self, fichier: Path):
        self.fichier = fichier
        self._ffmpeg: Optional[subprocess.Popen] = None

    def preparer(self) -> None:
        for outil in ("pactl", "ffmpeg"):
            if not shutil.which(outil):
                raise SystemExit(f"Outil manquant : {outil}. Installez pulseaudio et ffmpeg (ou utilisez le Dockerfile).")
        if subprocess.run(["pactl", "info"], capture_output=True).returncode != 0:
            subprocess.run(["pulseaudio", "--start", "--exit-idle-time=-1"], check=True)
        puits = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True).stdout
        for nom in (PUITS_AUDIO, MICRO_MUET):
            if nom not in puits.split():
                subprocess.run(
                    ["pactl", "load-module", "module-null-sink", f"sink_name={nom}",
                     f"sink_properties=device.description={nom}"],
                    check=True, capture_output=True,
                )
        subprocess.run(["pactl", "set-default-sink", PUITS_AUDIO], check=True)
        # Micro virtuel silencieux : le robot n'émet jamais de son dans la réunion.
        subprocess.run(["pactl", "set-default-source", f"{MICRO_MUET}.monitor"], check=True)

    def demarrer(self) -> None:
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        self._ffmpeg = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "pulse", "-i", f"{PUITS_AUDIO}.monitor",
             "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", str(self.fichier)],
            stdin=subprocess.PIPE,
        )

    def arreter(self) -> None:
        if self._ffmpeg and self._ffmpeg.poll() is None:
            self._ffmpeg.communicate(b"q", timeout=30)


def _cliquer(page, motif: re.Pattern, delai_ms: int = 2000) -> bool:
    """Clique sur le premier bouton visible dont le libellé correspond, dans la page ou ses cadres."""
    for cadre in page.frames:
        bouton = cadre.get_by_role("button", name=motif)
        try:
            if bouton.count():
                bouton.first.click(timeout=delai_ms)
                return True
        except Exception:
            continue
    return False


def _texte_visible(page) -> str:
    morceaux = []
    for cadre in page.frames:
        try:
            morceaux.append(cadre.locator("body").inner_text(timeout=2000))
        except Exception:
            pass
    return "\n".join(morceaux)


def _dans_la_reunion(page) -> bool:
    return any(cadre.get_by_role("button", name=_BOUTON_QUITTER).count() for cadre in page.frames)


def _photo(page, capture: Optional[Path]) -> None:
    """Enregistre ce que voit le robot, pour comprendre un éventuel blocage."""
    if capture:
        try:
            page.screenshot(path=str(capture))
        except Exception:
            pass


def _rejoindre(page, reunion: Reunion, nom: str, attente_max_s: int, capture: Optional[Path] = None) -> None:
    log.info("Étape 1/4 : ouverture de la réunion %s dans le navigateur…", reunion.numero)
    page.goto(reunion.url_client_web(nom), wait_until="domcontentloaded")
    _cliquer(page, _BOUTON_COOKIES, 3000)
    # Page d'accueil « Lancer la réunion » : on choisit le navigateur plutôt que l'application.
    if not _cliquer(page, _LIEN_NAVIGATEUR, 3000):
        lien = page.get_by_role("link", name=_LIEN_NAVIGATEUR)
        if lien.count():
            lien.first.click()
    # Le nouveau client web s'affiche dans un iframe plein écran : on l'ouvre directement.
    iframe = page.locator("iframe#webclient")
    try:
        iframe.wait_for(timeout=8000)
        source = iframe.get_attribute("src")
        if source:
            page.goto(urljoin(page.url, source), wait_until="domcontentloaded")
    except Exception:
        pass
    _photo(page, capture)

    log.info("Étape 2/4 : saisie du nom « %s »…", nom)
    champ_nom = page.locator("#input-for-name")
    try:
        champ_nom.wait_for(timeout=20000)
        champ_nom.fill(nom)
    except Exception:
        log.info("Champ du nom introuvable, le nom passé dans le lien sera utilisé.")
    _verifier_blocage(page, capture)
    if reunion.code:
        champ_code = page.locator("#input-for-pwd")
        if champ_code.count():
            champ_code.fill(reunion.code)

    # Micro et caméra coupés : le robot écoute seulement.
    for identifiant, coupe in (("#preview-audio-control-button", "Unmute"), ("#preview-video-control-button", "Start Video")):
        bouton = page.locator(identifiant)
        if bouton.count() and bouton.get_attribute("aria-label") != coupe:
            bouton.click()

    log.info("Étape 3/4 : clic sur « Rejoindre »…")
    bouton_rejoindre = page.locator(".preview-join-button")
    if bouton_rejoindre.count():
        bouton_rejoindre.first.click()
    elif not _cliquer(page, _BOUTON_REJOINDRE, 5000):
        _photo(page, capture)
        raise RuntimeError("Bouton « Rejoindre » introuvable : la page Zoom a peut-être changé.")

    log.info("Étape 4/4 : demande d'accès envoyée, en attente d'admission…")
    limite = time.monotonic() + attente_max_s
    signale_attente = False
    prochaine_photo = 0.0
    while not _dans_la_reunion(page):
        texte = _texte_visible(page)
        if _FIN_DE_REUNION.search(texte):
            raise RuntimeError("La réunion est terminée ou l'accès a été refusé.")
        _verifier_blocage(page, capture, texte)
        if _SALLE_ATTENTE.search(texte) and not signale_attente:
            log.info("Le robot est en salle d'attente : l'hôte doit l'admettre (Participants > Admettre).")
            signale_attente = True
        if time.monotonic() > limite:
            raise RuntimeError("Le robot n'a pas été admis dans la réunion à temps.")
        if time.monotonic() > prochaine_photo:
            _photo(page, capture)
            prochaine_photo = time.monotonic() + 10
        time.sleep(3)
    log.info("Robot entré dans la réunion.")
    _cliquer(page, _BOUTON_AUDIO_ORDINATEUR, 5000)
    _photo(page, capture)


def _verifier_blocage(page, capture: Optional[Path], texte: Optional[str] = None) -> None:
    """Arrête tout de suite, avec une explication, quand Zoom refuse l'accès au robot."""
    texte = texte if texte is not None else _texte_visible(page)
    for motif, explication in _BLOCAGES:
        if motif.search(texte):
            _photo(page, capture)
            raise RuntimeError(explication)


def _annoncer(page, message: str) -> None:
    """Prévient les participants dans la discussion que la réunion est enregistrée (au mieux)."""
    try:
        if not _cliquer(page, re.compile(r"^(open the chat|chat|converser|discussion)", re.I)):
            return
        zone = page.locator(".chat-rtf-box__editor-outer [contenteditable='true'], textarea.chat-box__chat-textarea").first
        zone.wait_for(timeout=5000)
        zone.click()
        zone.type(message)
        zone.press("Enter")
        _cliquer(page, re.compile(r"^(close|fermer)", re.I))
    except Exception:
        log.info("Message d'annonce non envoyé dans la discussion (interface différente).")


def _attendre_la_fin(page, duree_max_s: int) -> None:
    limite = time.monotonic() + duree_max_s
    absent_depuis = None
    while time.monotonic() < limite:
        time.sleep(5)
        if page.is_closed():
            return
        if _FIN_DE_REUNION.search(_texte_visible(page)):
            log.info("Fin de la réunion détectée.")
            return
        # Le bouton « Quitter » disparaît quand on n'est plus dans la réunion.
        if _dans_la_reunion(page):
            absent_depuis = None
        elif absent_depuis is None:
            absent_depuis = time.monotonic()
        elif time.monotonic() - absent_depuis > 60:
            log.info("Le robot n'est plus dans la réunion.")
            return
    log.info("Durée maximale atteinte, le robot quitte la réunion.")


def enregistrer_reunion(
    reunion: Reunion,
    fichier_audio: Path,
    nom: str = NOM_PAR_DEFAUT,
    attente_max_s: int = 15 * 60,
    duree_max_s: int = 3 * 3600,
    annonce: Optional[str] = None,
) -> Path:
    from playwright.sync_api import sync_playwright

    fichier_audio.parent.mkdir(parents=True, exist_ok=True)
    enregistreur = EnregistreurAudio(fichier_audio)
    enregistreur.preparer()
    environnement = {**os.environ, "PULSE_SINK": PUITS_AUDIO, "PULSE_SOURCE": f"{MICRO_MUET}.monitor"}
    with sync_playwright() as p:
        navigateur = p.chromium.launch(
            headless=False,
            env=environnement,
            args=["--autoplay-policy=no-user-gesture-required", "--use-fake-ui-for-media-stream"],
        )
        contexte = navigateur.new_context(permissions=["microphone", "camera"], locale="fr-FR",
                                          viewport={"width": 1280, "height": 800})
        page = contexte.new_page()
        try:
            _rejoindre(page, reunion, nom, attente_max_s, fichier_audio.with_suffix(".robot.png"))
            enregistreur.demarrer()
            log.info("Enregistrement en cours → %s", fichier_audio)
            if annonce:
                _annoncer(page, annonce)
            _attendre_la_fin(page, duree_max_s)
        except Exception:
            _photo(page, fichier_audio.with_suffix(".erreur.png"))
            log.info("Capture de ce que voyait le robot : %s", fichier_audio.with_suffix(".erreur.png"))
            raise
        finally:
            enregistreur.arreter()
            try:
                _cliquer(page, _BOUTON_QUITTER)
                _cliquer(page, re.compile(r"^(Leave Meeting|Quitter la réunion)", re.I))
            except Exception:
                pass
            navigateur.close()
    return fichier_audio


def envoyer_par_email(destinataires: list[str], sujet: str, corps: str, pieces: list[Path]) -> None:
    """Envoi via SMTP (gratuit avec Gmail et un mot de passe d'application)."""
    import smtplib
    from email.message import EmailMessage

    hote = os.environ.get("SMTP_HOTE", "smtp.gmail.com")
    utilisateur = os.environ.get("SMTP_UTILISATEUR")
    mot_de_passe = os.environ.get("SMTP_MOT_DE_PASSE")
    if not utilisateur or not mot_de_passe:
        raise RuntimeError("Définissez SMTP_UTILISATEUR et SMTP_MOT_DE_PASSE pour l'envoi par e-mail.")

    message = EmailMessage()
    message["From"] = utilisateur
    message["To"] = ", ".join(destinataires)
    message["Subject"] = sujet
    message.set_content(corps)
    for piece in pieces:
        sous_type = "vnd.openxmlformats-officedocument.wordprocessingml.document" if piece.suffix == ".docx" else "markdown"
        message.add_attachment(piece.read_bytes(), maintype="application" if piece.suffix == ".docx" else "text",
                               subtype=sous_type, filename=piece.name)
    with smtplib.SMTP(hote, int(os.environ.get("SMTP_PORT", "587"))) as serveur:
        serveur.starttls()
        serveur.login(utilisateur, mot_de_passe)
        serveur.send_message(message)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent_compte_rendu.zoom",
        description="Fait rejoindre une réunion Zoom par le robot, l'enregistre puis rédige le compte rendu.",
    )
    parser.add_argument("lien", help="Lien d'invitation Zoom ou numéro de réunion")
    parser.add_argument("--code", help="Code secret de la réunion, s'il n'est pas dans le lien")
    parser.add_argument("--nom", default=NOM_PAR_DEFAUT, help=f"Nom affiché du robot (défaut : « {NOM_PAR_DEFAUT} »)")
    parser.add_argument("--titre", help="Titre de la réunion")
    parser.add_argument("--participants", help="Participants attendus, ex. « Awa (DG), Paul (DAF) »")
    parser.add_argument("--contexte", help="Ordre du jour, sigles, projet…")
    parser.add_argument("--sortie", type=Path, default=Path("comptes_rendus"), help="Dossier de sortie")
    parser.add_argument("--envoyer-a", help="Adresses e-mail destinataires du compte rendu, séparées par des virgules")
    parser.add_argument("--attente-max", type=int, default=15, help="Minutes d'attente maximum en salle d'attente (défaut : 15)")
    parser.add_argument("--duree-max", type=int, default=180, help="Durée maximum d'enregistrement en minutes (défaut : 180)")
    parser.add_argument("--sans-annonce", action="store_true", help="Ne pas annoncer l'enregistrement dans la discussion")
    parser.add_argument("--modele-whisper", default="small", help="Modèle de transcription : tiny, base, small, medium, large-v3 (défaut : small)")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    from .agent import rediger_compte_rendu
    from .rendu import en_docx, en_markdown
    from .transcription import transcrire_audio

    try:
        reunion = analyser_lien(args.lien, args.code)
    except ValueError as erreur:
        sys.exit(str(erreur))
    debut = datetime.now()
    base = args.sortie / f"{debut:%Y-%m-%d_%Hh%M}_zoom-{reunion.numero}"
    annonce = None if args.sans_annonce else (
        "Bonjour, je suis l'assistant de prise de notes : cette réunion est enregistrée pour en rédiger le compte rendu."
    )

    try:
        audio = enregistrer_reunion(reunion, base.with_suffix(".mp3"), args.nom,
                                    args.attente_max * 60, args.duree_max * 60, annonce)
    except RuntimeError as erreur:
        sys.exit(f"Échec : {erreur}\nCe que voyait le robot : {base.with_suffix('.erreur.png')}")
    fin = datetime.now()

    log.info("Transcription de l'enregistrement…")
    transcription = transcrire_audio(audio, "fr", args.modele_whisper)
    base.with_suffix(".transcription.txt").write_text(transcription, encoding="utf-8")
    if not transcription.strip():
        sys.exit("Aucune parole détectée dans l'enregistrement : le compte rendu n'a pas été rédigé.")

    log.info("Rédaction du compte rendu…")
    duree = int((fin - debut).total_seconds() // 60)
    cr = rediger_compte_rendu(
        transcription,
        titre=args.titre,
        date=f"{debut:%d/%m/%Y}, de {debut:%H:%M} à {fin:%H:%M} (environ {duree} min)",
        participants=args.participants,
        contexte=args.contexte,
        effort=args.effort,
    )
    base.with_suffix(".md").write_text(en_markdown(cr), encoding="utf-8")
    en_docx(cr, base.with_suffix(".docx"))
    log.info("Compte rendu enregistré : %s", base.with_suffix(".docx"))

    if args.envoyer_a:
        destinataires = [a.strip() for a in args.envoyer_a.split(",") if a.strip()]
        envoyer_par_email(destinataires, f"Compte rendu — {cr.titre}", cr.resume, [base.with_suffix(".docx")])
        log.info("Compte rendu envoyé à %s", ", ".join(destinataires))


if __name__ == "__main__":
    main()
