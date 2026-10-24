"""Structure du compte rendu produit par l'agent."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Participant(BaseModel):
    nom: str
    role: Optional[str] = Field(None, description="Fonction ou rôle dans la réunion, si mentionné")


class PointAborde(BaseModel):
    sujet: str
    discussion: str = Field(description="Synthèse des échanges sur ce sujet, avec les positions de chacun")
    conclusions: List[str] = Field(description="Ce qui ressort de la discussion sur ce sujet")


class Decision(BaseModel):
    decision: str
    justification: Optional[str] = None


class Action(BaseModel):
    tache: str
    responsable: Optional[str] = Field(None, description="Personne chargée de la tâche, si identifiée")
    echeance: Optional[str] = Field(None, description="Date ou délai mentionné, sinon null")
    priorite: Literal["haute", "moyenne", "basse"]


class CompteRendu(BaseModel):
    titre: str
    date: Optional[str] = None
    duree: Optional[str] = None
    participants: List[Participant]
    objet: str = Field(description="Objectif de la réunion en une ou deux phrases")
    resume: str = Field(description="Synthèse exécutive de 5 à 10 lignes")
    points_abordes: List[PointAborde]
    decisions: List[Decision]
    actions: List[Action]
    questions_en_suspens: List[str]
    prochaine_reunion: Optional[str] = None
