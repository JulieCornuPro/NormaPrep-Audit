"""Lecture d'un référentiel d'audit sous forme d'arborescence."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Noeud, Referentiel


@dataclass
class NoeudA:
    code: str
    libelle: str
    niveau: int
    profils: list[str]
    description: str = ""
    methode: str = ""
    preuves_attendues: list[str] = field(default_factory=list)
    recommandation: str = ""
    interlocuteurs: list[str] = field(default_factory=list)
    parent: "NoeudA | None" = None
    enfants: list["NoeudA"] = field(default_factory=list)

    def descendants(self) -> list["NoeudA"]:
        resultat = []
        for e in self.enfants:
            resultat.append(e)
            resultat += e.descendants()
        return resultat

    def ancetre(self, niveau: int) -> "NoeudA | None":
        n: NoeudA | None = self
        while n is not None and n.niveau > niveau:
            n = n.parent
        return n if n is not None and n.niveau == niveau else None

    def applicable(self, profil: str | None) -> bool:
        return not profil or not self.profils or profil in self.profils


@dataclass
class Arbre:
    referentiel: Referentiel
    racines: list[NoeudA]
    par_code: dict[str, NoeudA]

    def au_niveau(self, niveau: int, profil: str | None = None) -> list[NoeudA]:
        """Éléments d'un niveau donné, dans l'ordre du référentiel. Un élément plus
        haut qui n'a aucun descendant à ce niveau (mesure sans contrôle, par
        exemple) n'est pas concerné : on ne descend pas sous lui."""
        resultat: list[NoeudA] = []

        def parcourir(n: NoeudA) -> None:
            if not n.applicable(profil):
                return
            if n.niveau == niveau:
                resultat.append(n)
                return
            for e in n.enfants:
                parcourir(e)

        for r in self.racines:
            parcourir(r)
        return resultat


def charger(session: Session, referentiel: Referentiel) -> Arbre:
    noeuds = session.scalars(select(Noeud).where(Noeud.referentiel_id == referentiel.id).order_by(Noeud.ordre)).all()
    par_id: dict[int, NoeudA] = {}
    racines: list[NoeudA] = []
    for n in noeuds:
        a = NoeudA(
            n.code, n.libelle, n.niveau, n.profils, n.description, n.methode, n.preuves_attendues, n.recommandation,
            n.interlocuteurs,
        )  # fmt: skip
        par_id[n.id] = a
        if n.parent_id is None:
            racines.append(a)
        else:
            parent = par_id[n.parent_id]  # le parent précède toujours l'enfant (ordre d'import)
            a.parent = parent
            parent.enfants.append(a)
    return Arbre(referentiel, racines, {a.code: a for a in par_id.values()})


def en_dict(n: NoeudA) -> dict[str, Any]:
    return {
        "code": n.code,
        "libelle": n.libelle,
        "niveau": n.niveau,
        "profils": n.profils,
        "description": n.description,
        "methode": n.methode,
        "preuves_attendues": n.preuves_attendues,
        "recommandation": n.recommandation,
        "interlocuteurs": n.interlocuteurs,
        "enfants": [en_dict(e) for e in n.enfants],
    }
