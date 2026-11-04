class DemoError(Exception):
    """Base des erreurs du mode démonstration ; messages affichables tels quels."""


class RealDataPresentError(DemoError):
    """Le mode démonstration ne se mêle jamais à des données réelles."""


class DemoModeActiveError(DemoError):
    """Une action sur des données réelles est refusée tant que la démonstration est active."""
