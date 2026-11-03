from datetime import UTC, datetime
from decimal import Decimal

from app.modules.job_intelligence.domain.matching.models import (
    ExperiencePeriod,
    OfferFacts,
    ProfileFacts,
    YearMonth,
)

MAINTENANT = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def profil(**surcharge: object) -> ProfileFacts:
    valeurs: dict[str, object] = {
        "titles": ("Data Analyst",),
        "skills": ("SQL", "Python", "PostgreSQL", "Excel"),
        "experience_periods": (
            ExperiencePeriod(YearMonth(2019, 1), YearMonth(2022, 12)),
            ExperiencePeriod(YearMonth(2023, 1), None, is_current=True),
        ),
        "degrees": ("Master Informatique",),
        "country_codes": ("FR",),
        "cities": ("Lyon",),
        "remote_types": ("hybrid", "remote"),
        "employment_types": ("permanent",),
        "salary_min": Decimal(45000),
        "salary_currency": "EUR",
    }
    valeurs.update(surcharge)
    return ProfileFacts(**valeurs)  # type: ignore[arg-type]


def offre(**surcharge: object) -> OfferFacts:
    valeurs: dict[str, object] = {
        "title": "Data Analyst H/F",
        "description": "",
        "location": "Lyon, France",
        "country_code": "FR",
        "employment_type": "permanent",
        "remote_type": "hybrid",
        "salary_min": Decimal(48000),
        "salary_max": Decimal(55000),
        "salary_currency": "EUR",
        "published_at": datetime(2026, 11, 1, tzinfo=UTC),
    }
    valeurs.update(surcharge)
    return OfferFacts(**valeurs)  # type: ignore[arg-type]
