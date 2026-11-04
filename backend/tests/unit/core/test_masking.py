from pydantic import SecretStr

from app.core.observability.masking import key_hint


def test_indice_de_cle_ne_revele_que_la_fin() -> None:
    cle = SecretStr("AIzaSyA1234567890abcdefghij")

    assert key_hint(cle) == "…ghij"
    assert "AIza" not in (key_hint(cle) or "")


def test_cle_courte_n_est_pas_devoilee() -> None:
    assert key_hint(SecretStr("abc123")) == "…"


def test_absence_de_cle() -> None:
    assert key_hint(None) is None
