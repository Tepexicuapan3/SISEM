from django.conf import settings


_SOURCE_DB = "db"
_SOURCE_STATIC = "static"
_SOURCE_AUTO = "auto"


def resolve_navigation_menu_source() -> str:
    raw_source = str(
        getattr(settings, "NAVIGATION_MENU_SOURCE", _SOURCE_AUTO)
    ).strip().lower()

    if raw_source in {_SOURCE_DB, _SOURCE_STATIC}:
        return raw_source

    if bool(getattr(settings, "NAVIGATION_MENU_DB_ENABLED", False)):
        return _SOURCE_DB

    return _SOURCE_STATIC


