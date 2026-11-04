from app.modules.platform.domain.health import ComponentHealth, Status, overall_status


def _c(nom: str, statut: Status) -> ComponentHealth:
    return ComponentHealth(nom, statut)


def test_tout_ok() -> None:
    assert overall_status([_c("database", Status.OK), _c("ai", Status.OK)]) is Status.OK


def test_composant_facultatif_non_configure_ne_degrade_pas() -> None:
    assert overall_status([_c("database", Status.OK), _c("ai", Status.NOT_CONFIGURED)]) is Status.OK


def test_base_ou_stockage_en_panne_donne_down() -> None:
    assert overall_status([_c("database", Status.DOWN), _c("ai", Status.OK)]) is Status.DOWN
    assert overall_status([_c("storage", Status.DOWN)]) is Status.DOWN


def test_panne_d_un_composant_non_essentiel_donne_degrade() -> None:
    assert (
        overall_status([_c("database", Status.OK), _c("sources", Status.DOWN)]) is Status.DEGRADED
    )
    assert overall_status([_c("latex", Status.DEGRADED)]) is Status.DEGRADED
