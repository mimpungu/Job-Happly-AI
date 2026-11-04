"""Brouillon de relance post-entretien (TASK-016-14). Rien n'est envoyé par l'application."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.interview_preparation.domain.models import FollowUpDraft, InterviewData, OfferFacts

_DELAY = timedelta(days=2)


def suggest_follow_up_date(interview: InterviewData, *, now: datetime) -> datetime:
    """Deux jours après l'entretien ; si la date est inconnue ou passée, deux jours après `now`."""
    reference = interview.scheduled_at if interview.scheduled_at else now
    return max(reference, now) + _DELAY


def draft_follow_up(
    interview: InterviewData,
    offer: OfferFacts,
    *,
    candidate_name: str | None,
    language: str,
    now: datetime | None = None,
) -> FollowUpDraft:
    maintenant = (now or datetime.now(UTC)).astimezone(UTC)
    destinataire = interview.interviewers[0] if interview.interviewers else None
    societe = offer.company
    quand = suggest_follow_up_date(interview, now=maintenant)
    if language.lower().startswith("en"):
        salut = f"Hello {destinataire}," if destinataire else "Hello,"
        chez = f" at {societe}" if societe else ""
        corps = (
            f"{salut}\n\nThank you for taking the time to talk with me about the {offer.title} "
            f"role{chez}. Our conversation reinforced my interest in the position.\n\n"
            "[To complete: one specific point from the discussion you want to come back to.]\n\n"
            "I remain available for any further information.\n\nBest regards,\n"
            f"{candidate_name or ''}".rstrip()
        )
        sujet = f"Thank you - {offer.title} interview"
    else:
        salut = f"Bonjour {destinataire}," if destinataire else "Bonjour,"
        chez = f" chez {societe}" if societe else ""
        corps = (
            f"{salut}\n\nMerci d'avoir pris le temps d'échanger avec moi au sujet du poste de "
            f"{offer.title}{chez}. Notre discussion a renforcé mon intérêt pour ce poste.\n\n"
            "[À compléter : un point précis de l'échange sur lequel vous souhaitez revenir.]\n\n"
            "Je reste disponible pour tout complément d'information.\n\nCordialement,\n"
            f"{candidate_name or ''}".rstrip()
        )
        sujet = f"Merci pour notre échange - poste de {offer.title}"
    return FollowUpDraft(subject=sujet, body=corps, suggested_follow_up_at=quand)
