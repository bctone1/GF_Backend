# models/loader.py
def load_partner_models() -> None:
    import models.partner.partner_core  # noqa
    import models.partner.course        # noqa
    import models.partner.student       # noqa
    import models.partner.session       # noqa
    import models.partner.usage         # noqa


#### usage test 용 추후에 삭제 해도 무방 2026-01-07 ####