"""Journal d'audit : qui a fait quoi, quand.

L'entrée est ajoutée à la session de l'appelant et part avec sa transaction :
une action annulée ne laisse pas de trace trompeuse. Pour les événements qui
doivent rester même si l'action échoue (connexion refusée, import refusé),
l'appelant valide la session juste après.

La base interdit toute modification ou suppression du journal (règles créées
par la migration initiale).
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models import EntreeJournal


def journaliser(
    session: Session,
    action: str,
    *,
    utilisateur_id: int | None = None,
    objet_type: str | None = None,
    objet_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    adresse_ip: str | None = None,
) -> None:
    session.add(
        EntreeJournal(
            action=action,
            utilisateur_id=utilisateur_id,
            objet_type=objet_type,
            objet_id=None if objet_id is None else str(objet_id),
            details=details,
            adresse_ip=adresse_ip,
        )
    )
