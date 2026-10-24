"""Appel à Claude pour transformer une transcription en compte rendu structuré."""

from typing import Optional

import anthropic

from .modeles import CompteRendu

MODELE = "claude-opus-5-5"

CONSIGNES = """Tu es l'assistant de prise de notes et de rédaction de comptes rendus de réunions en ligne.
On te fournit la transcription brute d'une réunion (Teams, Zoom, Google Meet ou enregistrement audio).
Ta mission : produire un compte rendu professionnel, fidèle et exploitable, rédigé en français soutenu.

Règles de rédaction :
- Fidélité absolue : n'invente aucun fait, nom, chiffre, date ou décision absent de la transcription.
  Si une information manque (responsable, échéance, date de la réunion), laisse le champ vide (null).
- Distingue clairement ce qui a été décidé, ce qui a seulement été proposé ou discuté,
  et ce qui reste en suspens. Une proposition sans accord explicite n'est pas une décision.
- Une action est une tâche concrète qu'une personne s'est engagée ou a été chargée de réaliser.
  Formule-la avec un verbe à l'infinitif (« Envoyer le budget révisé… »).
  Priorité « haute » si elle est urgente ou bloquante, « basse » si elle est accessoire, sinon « moyenne ».
- Les transcriptions automatiques contiennent des erreurs : corrige les fautes évidentes,
  ignore les hésitations, les apartés techniques (« tu m'entends ? », « je partage mon écran »)
  et les répétitions. Garde les noms propres tels qu'ils apparaissent le plus souvent.
- Les points abordés suivent l'ordre chronologique de la réunion et regroupent les échanges par thème.
  Pour chaque point, résume les positions exprimées en attribuant les propos importants à leur auteur.
- Le résumé exécutif doit permettre à un absent de comprendre l'essentiel en moins d'une minute.
- Reste neutre et factuel : pas de jugement sur les participants.
- Le titre est court et décrit le sujet principal de la réunion."""


def rediger_compte_rendu(
    transcription: str,
    titre: Optional[str] = None,
    date: Optional[str] = None,
    participants: Optional[str] = None,
    contexte: Optional[str] = None,
    effort: str = "high",
    client: Optional[anthropic.Anthropic] = None,
) -> CompteRendu:
    """Analyse la transcription et renvoie un compte rendu validé."""
    if not transcription.strip():
        raise ValueError("La transcription est vide.")

    informations = []
    if titre:
        informations.append(f"Titre souhaité : {titre}")
    if date:
        informations.append(f"Date de la réunion : {date}")
    if participants:
        informations.append(f"Participants attendus : {participants}")
    if contexte:
        informations.append(f"Contexte fourni par l'organisateur : {contexte}")
    entete = "\n".join(informations)

    demande = (
        (f"<informations>\n{entete}\n</informations>\n\n" if entete else "")
        + f"<transcription>\n{transcription}\n</transcription>\n\n"
        "Rédige le compte rendu de cette réunion."
    )

    client = client or anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODELE,
        max_tokens=64000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=CONSIGNES,
        messages=[{"role": "user", "content": demande}],
        output_format=CompteRendu,
    ) as flux:
        reponse = flux.get_final_message()

    if reponse.stop_reason == "refusal":
        raise RuntimeError("Claude a refusé de traiter cette transcription.")
    if reponse.stop_reason == "max_tokens":
        raise RuntimeError("Le compte rendu a été tronqué (limite de longueur atteinte).")
    if reponse.parsed_output is None:
        raise RuntimeError("La réponse de Claude n'a pas pu être lue comme un compte rendu.")
    return reponse.parsed_output
