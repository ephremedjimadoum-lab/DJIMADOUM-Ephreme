from pathlib import Path

from agent_compte_rendu.modeles import Action, CompteRendu, Decision, Participant, PointAborde
from agent_compte_rendu.rendu import en_docx, en_markdown
from agent_compte_rendu.transcription import lire_transcription, parser_sous_titres

EXEMPLE = Path(__file__).parent.parent / "exemples" / "reunion_exemple.vtt"


def test_vtt_teams_orateurs_et_fusion():
    texte = lire_transcription(EXEMPLE)
    lignes = texte.splitlines()
    assert lignes[0].startswith("[00:00:02] Awa Mahamat : Bonjour")
    # Les deux premières répliques d'Awa sont fusionnées.
    assert "trois sujets" in lignes[0]
    assert lignes[1].startswith("[00:00:22] Paul Ngarta :")
    assert "<v" not in texte


def test_srt_format_zoom():
    srt = "1\n00:00:01,000 --> 00:00:03,000\nJean : Bonjour\n\n2\n00:00:04,000 --> 00:00:06,000\nMarie : Salut\n"
    assert parser_sous_titres(srt) == "[00:00:01] Jean : Bonjour\n[00:00:04] Marie : Salut"


def _compte_rendu():
    return CompteRendu(
        titre="Lancement du site",
        date="24/10/2026",
        participants=[Participant(nom="Awa", role="DG"), Participant(nom="Paul")],
        objet="Faire le point sur le lancement.",
        resume="La mise en ligne est décalée.",
        points_abordes=[PointAborde(sujet="Planning", discussion="Retard de deux semaines.", conclusions=["Nouvelle date"])],
        decisions=[Decision(decision="Mise en ligne le 15 décembre", justification="Qualité")],
        actions=[Action(tache="Signer le contrat", responsable="Paul", echeance=None, priorite="haute")],
        questions_en_suspens=["Montant du budget marketing"],
        prochaine_reunion="Jeudi 10 h",
    )


def test_rendu_markdown():
    md = en_markdown(_compte_rendu())
    assert "# Compte rendu — Lancement du site" in md
    assert "Awa (DG), Paul" in md
    assert "| Signer le contrat | Paul | — | haute |" in md
    assert "## Questions en suspens" in md


def test_rendu_docx(tmp_path):
    chemin = tmp_path / "cr.docx"
    en_docx(_compte_rendu(), chemin)
    texte = lire_transcription(chemin)
    assert "Compte rendu — Lancement du site" in texte
    assert "Mise en ligne le 15 décembre" in texte
