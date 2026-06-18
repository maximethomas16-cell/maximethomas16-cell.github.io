#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT_DIR / "scripts" / "reference"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "data" / "live-data.json"
DEFAULT_INPUT_URL = "https://api.football-data.org/v4/competitions/WC/matches?season=2026"
DISPLAY_TZ = ZoneInfo("Europe/Paris")
SUPPORTED_STAGES = {"GROUP_STAGE", "LAST_32"}

STATUS_MAP = {
    "SCHEDULED": "SCHEDULED",
    "TIMED": "SCHEDULED",
    "POSTPONED": "SCHEDULED",
    "SUSPENDED": "SCHEDULED",
    "CANCELLED": "SCHEDULED",
    "IN_PLAY": "LIVE",
    "PAUSED": "LIVE",
    "EXTRA_TIME": "LIVE",
    "PENALTY_SHOOTOUT": "LIVE",
    "FINISHED": "FINISHED",
    "AWARDED": "FINISHED",
}

EXPLICIT_ALIASES = {
    "Mexico": "mexique",
    "South Africa": "afrique-du-sud",
    "Curaçao": "curacao",
    "Curacao": "curacao",
    "South Korea": "coree-du-sud",
    "Korea Republic": "coree-du-sud",
    "Czechia": "republique-tcheque",
    "Czech Republic": "republique-tcheque",
    "Bosnia and Herzegovina": "bosnie-herzegovine",
    "Canada": "canada",
    "Qatar": "qatar",
    "United States": "etats-unis",
    "USA": "etats-unis",
    "Paraguay": "paraguay",
    "Brazil": "bresil",
    "Haiti": "haiti",
    "Australia": "australie",
    "Scotland": "ecosse",
    "Turkey": "turquie",
    "Turkiye": "turquie",
    "Morocco": "maroc",
    "Switzerland": "suisse",
    "Ivory Coast": "cote-ivoire",
    "Cote d'Ivoire": "cote-ivoire",
    "Ecuador": "equateur",
    "Germany": "allemagne",
    "Netherlands": "pays-bas",
    "Japan": "japon",
    "Sweden": "suede",
    "Tunisia": "tunisie",
    "Saudi Arabia": "arabie-saoudite",
    "Spain": "espagne",
    "Cape Verde": "cap-vert",
    "Cape Verde Islands": "cap-vert",
    "Iran": "iran",
    "New Zealand": "nouvelle-zelande",
    "Uruguay": "uruguay",
    "Belgium": "belgique",
    "Egypt": "egypte",
    "France": "france",
    "Senegal": "senegal",
    "Iraq": "irak",
    "Norway": "norvege",
    "Argentina": "argentine",
    "Algeria": "algerie",
    "Austria": "autriche",
    "Jordan": "jordanie",
    "Ghana": "ghana",
    "Panama": "panama",
    "England": "angleterre",
    "Croatia": "croatie",
    "Portugal": "portugal",
    "DR Congo": "rd-congo",
    "Congo DR": "rd-congo",
    "Uzbekistan": "ouzbekistan",
    "Colombia": "colombie",
}


@dataclass(frozen=True)
class ScheduleSlot:
    match_number: int
    stage: str
    kickoff: datetime
    stadium: str
    home_id: str | None
    away_id: str | None


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn" and ch.isalnum())


def normalize_venue(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.strip().lower())
    ascii_only = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    collapsed = "".join(ch if ch.isalnum() else " " for ch in ascii_only)
    tokens = [token for token in collapsed.split() if token not in {"stadium", "estadio"}]
    return " ".join(tokens)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(DISPLAY_TZ)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_schedule() -> list[ScheduleSlot]:
    raw_slots = load_json(REFERENCE_DIR / "official_schedule_2026.json")
    slots: list[ScheduleSlot] = []
    for item in raw_slots:
        slots.append(
            ScheduleSlot(
                match_number=int(item["matchNumber"]),
                stage=item["stage"],
                kickoff=parse_datetime(item["date"]),
                stadium=item["stadium"],
                home_id=item.get("homeId"),
                away_id=item.get("awayId"),
            )
        )
    return slots


def build_alias_lookup() -> dict[str, str]:
    teams = load_json(REFERENCE_DIR / "teams_2026.json")
    aliases: dict[str, str] = {}

    for team in teams:
        aliases[normalize_key(team["name"])] = team["id"]
        aliases[normalize_key(team["id"].replace("-", " "))] = team["id"]

    for alias, team_id in EXPLICIT_ALIASES.items():
        aliases[normalize_key(alias)] = team_id

    return aliases


def resolve_team_id(team_name: str | None, aliases: dict[str, str]) -> str | None:
    if not team_name:
        return None
    return aliases.get(normalize_key(team_name))


def map_status(api_status: str, has_score: bool) -> str:
    mapped = STATUS_MAP.get(api_status, "SCHEDULED")
    if api_status == "AWARDED" and not has_score:
        return "SCHEDULED"
    return mapped


def full_time_score(match: dict[str, Any]) -> tuple[int | None, int | None]:
    score = match.get("score") or {}
    full_time = score.get("fullTime") or {}
    home = full_time.get("home")
    away = full_time.get("away")
    return home, away


def slot_score(
    slot: ScheduleSlot,
    api_stage: str,
    api_kickoff: datetime,
    api_venue: str,
    api_home_id: str | None,
    api_away_id: str | None,
) -> float:
    if slot.stage != api_stage:
        return float("-inf")

    score = 0.0
    time_delta_minutes = abs((slot.kickoff - api_kickoff).total_seconds()) / 60.0

    if slot.home_id and slot.away_id and api_home_id and api_away_id:
        if slot.home_id == api_home_id:
            score += 300
        if slot.away_id == api_away_id:
            score += 300
        if slot.home_id == api_home_id and slot.away_id == api_away_id:
            score += 1_000

    normalized_slot_venue = normalize_venue(slot.stadium)
    normalized_api_venue = normalize_venue(api_venue)
    if normalized_slot_venue and normalized_api_venue:
        if normalized_slot_venue == normalized_api_venue:
            score += 150
        elif normalized_slot_venue in normalized_api_venue or normalized_api_venue in normalized_slot_venue:
            score += 75

    if time_delta_minutes <= 5:
        score += 250
    elif time_delta_minutes <= 60:
        score += 100
    elif time_delta_minutes <= 360:
        score += 30
    else:
        score -= min(time_delta_minutes, 1_440) / 12.0

    return score


def match_slot(
    match: dict[str, Any],
    aliases: dict[str, str],
    available_slots: list[ScheduleSlot],
) -> ScheduleSlot | None:
    api_stage = match.get("stage")
    if api_stage not in SUPPORTED_STAGES:
        return None

    api_home_id = resolve_team_id((match.get("homeTeam") or {}).get("name"), aliases)
    api_away_id = resolve_team_id((match.get("awayTeam") or {}).get("name"), aliases)
    api_kickoff = parse_datetime(match["utcDate"])
    api_venue = match.get("venue") or ""

    ranked = sorted(
        available_slots,
        key=lambda slot: slot_score(
            slot=slot,
            api_stage=api_stage,
            api_kickoff=api_kickoff,
            api_venue=api_venue,
            api_home_id=api_home_id,
            api_away_id=api_away_id,
        ),
        reverse=True,
    )

    if not ranked:
        return None

    best = ranked[0]
    best_score = slot_score(
        slot=best,
        api_stage=api_stage,
        api_kickoff=api_kickoff,
        api_venue=api_venue,
        api_home_id=api_home_id,
        api_away_id=api_away_id,
    )
    if best_score < 100:
        return None

    return best


def fetch_remote_payload(api_token: str) -> dict[str, Any]:
    request = Request(
        DEFAULT_INPUT_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "WidgetCDM2026LiveData/1.0",
            "X-Auth-Token": api_token,
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"football-data.org HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"football-data.org unavailable: {exc.reason}") from exc


def load_input_payload(input_file: str | None) -> dict[str, Any]:
    if input_file:
        return json.loads(Path(input_file).read_text(encoding="utf-8-sig"))

    api_token = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_token:
        raise RuntimeError("Missing FOOTBALL_DATA_API_KEY environment variable")
    return fetch_remote_payload(api_token)


def build_live_data(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    aliases = build_alias_lookup()
    schedule_slots = load_schedule()
    available_slots = list(schedule_slots)
    warnings: list[str] = []
    output_matches: list[dict[str, Any]] = []

    for match in payload.get("matches", []):
        if match.get("stage") not in SUPPORTED_STAGES:
            continue

        slot = match_slot(match, aliases, available_slots)
        if slot is None:
            home_name = (match.get("homeTeam") or {}).get("name", "?")
            away_name = (match.get("awayTeam") or {}).get("name", "?")
            warnings.append(f"Unmatched match: {home_name} vs {away_name} ({match.get('utcDate')})")
            continue

        available_slots = [candidate for candidate in available_slots if candidate.match_number != slot.match_number]
        home_score, away_score = full_time_score(match)
        status = map_status(match.get("status", "SCHEDULED"), home_score is not None and away_score is not None)

        item: dict[str, Any] = {
            "matchNumber": slot.match_number,
            "status": status,
            "date": parse_datetime(match["utcDate"]).isoformat(),
        }

        venue = match.get("venue")
        if venue:
            item["stadium"] = venue

        if home_score is not None:
            item["homeScore"] = int(home_score)
        if away_score is not None:
            item["awayScore"] = int(away_score)

        output_matches.append(item)

    output_matches.sort(key=lambda item: item["matchNumber"])
    document = {
        "schemaVersion": 1,
        "updatedAt": datetime.now(tz=DISPLAY_TZ).isoformat(),
        "matches": output_matches,
    }
    return document, warnings


def write_output(document: dict[str, Any], output_path: Path) -> None:
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate live-data.json for Widget CDM 2026")
    parser.add_argument("--input-file", help="Use a local football-data.org response JSON")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to the generated live-data.json",
    )
    parser.add_argument(
        "--allow-unmatched",
        action="store_true",
        help="Do not fail if a supported match cannot be mapped to a local match number",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        payload = load_input_payload(args.input_file)
        document, warnings = build_live_data(payload)
        write_output(document, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if warnings and not args.allow_unmatched:
        return 2

    print(f"Generated {Path(args.output).resolve()} with {len(document['matches'])} matches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
