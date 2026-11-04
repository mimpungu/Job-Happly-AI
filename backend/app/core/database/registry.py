"""Importe tous les modèles pour que `Base.metadata` soit complet (Alembic, tests)."""

from app.core.database.base import Base
from app.modules.ai_management.infrastructure import models as _ai
from app.modules.application_management.infrastructure import models as _applications
from app.modules.candidate_profile.infrastructure import models as _profile
from app.modules.document_generation.infrastructure import models as _documents
from app.modules.interview_preparation.infrastructure import models as _interviews
from app.modules.job_discovery.infrastructure import models as _discovery
from app.modules.job_intelligence.infrastructure import models as _intelligence
from app.modules.notifications.infrastructure import models as _notifications
from app.modules.platform.infrastructure import models as _platform

MODELS_LOADED = (
    _ai,
    _applications,
    _profile,
    _documents,
    _interviews,
    _discovery,
    _intelligence,
    _notifications,
    _platform,
)

metadata = Base.metadata
