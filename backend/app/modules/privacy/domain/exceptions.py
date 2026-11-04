class PrivacyError(Exception):
    """Base des erreurs de confidentialité ; messages affichables tels quels."""


class ConfirmationRequiredError(PrivacyError):
    pass


class DeletionBlockedError(PrivacyError):
    pass


class UnknownCategoryError(PrivacyError):
    pass
