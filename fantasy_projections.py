import os
from dotenv import load_dotenv

load_dotenv()

league_id = os.environ.get("league_id")
espn_s2 = os.environ.get("ESPN_S2")
swid = os.environ.get("SWID")

import json
from espn_api.hockey import League
from espn_api.hockey.constant import POSITION_MAP, PRO_TEAM_MAP

YEAR = 2026
league = League(league_id=league_id, year=YEAR, espn_s2=espn_s2, swid=swid)

TOTAL_SPLIT_ID = f"00{YEAR}"  # e.g. '002026'


def fetch_top_players(league, size):
    filters = {
        "players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]},
            "limit": size,
            "offset": 0,
            "sortDraftRanks": {
                "sortPriority": 100,
                "sortAsc": True,
                "value": "STANDARD",
            },
        }
    }
    headers = {"x-fantasy-filter": json.dumps(filters)}
    params = {"view": "kona_player_info", "scoringPeriodId": league.current_week}
    data = league.espn_request.league_get(params=params, headers=headers)
    return data["players"]


raw_players = fetch_top_players(league, size=100)

MIN_GP = 40

results = []

for entry in raw_players:
    player = entry.get("playerPoolEntry", {}).get("player") or entry.get("player")
    if not player:
        continue

    name = player.get("fullName")
    pos = POSITION_MAP.get(player.get("defaultPositionId"), "Unknown")
    pro_team = PRO_TEAM_MAP.get(player.get("proTeamId"), "FA")
    is_goalie = pos == "Goalie"

    espn_total, espn_gp = 0, 0

    for split in player.get("stats", []):
        if split.get("id") == TOTAL_SPLIT_ID:
            espn_total = split.get("appliedTotal", 0)

            stats_dict = split.get("stats", {})
            gp_key = "0" if is_goalie else "34"
            espn_gp = stats_dict.get(gp_key, 0)

            break

    espn_avg = espn_total / espn_gp if espn_gp else 0

    if is_goalie:
        proj_gp = espn_gp
        proj_total = espn_total
        proj_avg = espn_avg
    else:
        proj_gp = 82
        proj_avg = espn_avg
        proj_total = proj_avg * 82

    results.append({
        "name": name,
        "pos": pos,
        "team": pro_team,
        "proj_total": round(proj_total, 1),
        "proj_gp": proj_gp,
        "proj_avg": round(proj_avg, 2),
        "is_goalie": is_goalie,
        "raw_gp": espn_gp,
    })

results = [p for p in results if p["is_goalie"] or p["raw_gp"] >= MIN_GP]
results.sort(key=lambda x: x["proj_total"], reverse=True)

print(f"{'Rank':<5}{'Name':<22}{'Pos':<15}{'Team':<24}{'ProjTotal':>10}{'ProjGP':>8}{'ProjAvg':>9}")
print("-" * 100)

for i, p in enumerate(results, start=1):
    print(f"{i:<5}{p['name']:<22}{p['pos']:<15}{p['team']:<24}"
          f"{p['proj_total']:>10.1f}{p['proj_gp']:>8}{p['proj_avg']:>9.2f}")