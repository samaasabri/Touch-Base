"""Team directory lookup wrapper."""

from app.touch_base.factories import get_people_service


def lookup_team_member(name: str) -> dict:
    return get_people_service().lookup_member(name)
