from __future__ import annotations

import json

from rapidfuzz import fuzz, process

from app.config import Settings
from app.domain.ports.people_directory_repository import PeopleDirectoryRepository

MATCH_THRESHOLD = 60


class FilePeopleDirectoryRepository(PeopleDirectoryRepository):
    def __init__(self, settings: Settings):
        self.settings = settings

    def lookup_member(self, name: str) -> dict:
        try:
            if not self.settings.team_directory_file.exists():
                return {
                    "status": "error",
                    "matches": [],
                    "message": f"Team directory not found at {self.settings.team_directory_file}",
                }
            data = json.loads(self.settings.team_directory_file.read_text(encoding="utf-8"))
            team = data.get("team", [])
            if not team:
                return {"status": "not_found", "matches": [], "message": "The team directory is empty."}
            names = [member["name"] for member in team]
            results = process.extract(name, names, scorer=fuzz.WRatio, limit=3)
            matches = [
                {"name": team[idx]["name"], "email": team[idx]["email"], "score": int(score)}
                for _, score, idx in results
                if score >= MATCH_THRESHOLD
            ]
            if not matches:
                return {
                    "status": "not_found",
                    "matches": [],
                    "message": f"No team member found matching '{name}'. Please check the name.",
                }
            return {
                "status": "found",
                "matches": matches,
                "message": f"Found {len(matches)} match(es) for '{name}'.",
            }
        except Exception as e:
            return {"status": "error", "matches": [], "message": f"Error reading team directory: {e}"}
