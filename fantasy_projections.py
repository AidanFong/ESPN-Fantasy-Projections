import os
import json
from dotenv import load_dotenv
from espn_api.hockey import League
from espn_api.hockey.constant import POSITION_MAP, PRO_TEAM_MAP

load_dotenv()

league = League(
    league_id=os.environ["league_id"],
    year=2026,
    espn_s2=os.environ["ESPN_S2"],
    swid=os.environ["SWID"],
)

YEAR = 2026
TOTAL_SPLIT_ID = f"00{YEAR}"
MIN_GP = 25


def fetch_top_players(league, size):
    filters = {
        "players": {
            "filterStatus": {
                "value": ["FREEAGENT", "WAIVERS", "ONTEAM"]
            },
            "limit": size,
            "offset": 0,
            "sortDraftRanks": {
                "sortPriority": 1000,
                "sortAsc": True,
                "value": "STANDARD",
            },
        }
    }

    headers = {"x-fantasy-filter": json.dumps(filters)}
    params = {
        "view": "kona_player_info",
        "scoringPeriodId": league.current_week,
    }

    return league.espn_request.league_get(
        params=params,
        headers=headers
    )["players"]


raw_players = fetch_top_players(league, 1000)

print("Fetched:", len(raw_players))

# ------------------------------------
# Override scoring settings here
# statId : fantasy points
# ------------------------------------

SCORING = {
    13: 3.0,     # Goals
    14: 2.0,     # Assists
    15: 0.1,     # Plus/Minus
    29: 0.3,     # Shots
    31: 0.2,     # Hits
    32: 0.9,     # Blocks
    33: 0.0,     # Defenseman Point
    38: 0.3,     # PP Points
    39: 0.5,     # SH Points

    # Goalies
    1: 2.0,      # Wins
    4: -1.0,     # Goals Against
    6: 0.3,      # Saves
    7: 2.0,      # Shutouts
    9: 1.0,      # OTL
}


def calculate_points(stats, scoring, position):
    total = 0

    for stat_id, pts in scoring.items():

        value = stats.get(str(stat_id), 0)

        # Only defensemen receive defenseman point bonus
        if stat_id == 33 and position != "Defense":
            continue

        total += value * pts

    return total


results = []

for entry in raw_players:

    player = entry.get("playerPoolEntry", {}).get("player") or entry.get("player")

    if not player:
        continue

    name = player["fullName"]
    pos = POSITION_MAP.get(player["defaultPositionId"], "Unknown")
    team = PRO_TEAM_MAP.get(player["proTeamId"], "FA")

    is_goalie = pos == "Goalie"

    stats = None

    for split in player["stats"]:
        if split["id"] == TOTAL_SPLIT_ID:
            stats = split["stats"]
            break

    if stats is None:
        continue

    gp_key = "0" if is_goalie else "34"

    gp = stats.get(gp_key, 0)

    if gp == 0:
        continue

    fantasy_total = calculate_points(stats, SCORING, pos)

    fantasy_avg = fantasy_total / gp

    if is_goalie:
        proj_gp = gp
        proj_total = fantasy_total
    else:
        proj_gp = 82
        proj_total = fantasy_avg * 82

    results.append({
        "name": name,
        "pos": pos,
        "team": team,
        "gp": gp,
        "avg": fantasy_avg,
        "proj_total": proj_total,
        "proj_gp": proj_gp,
        "goalie": is_goalie,
    })


# print("Raw players:", len(raw_players))
# print("Processed:", len(results))

# before = len(results)

results = [
    p for p in results
    if p["goalie"] or p["gp"] >= MIN_GP
]

# print("After GP filter:", len(results))

results.sort(key=lambda x: x["proj_total"], reverse=True)

results = results[:300]

print(
    f"{'Rank':<5}"
    f"{'Name':<22}"
    f"{'Pos':<12}"
    f"{'Team':<24}"
    f"{'ProjTotal':>11}"
    f"{'GP':>6}"
    f"{'Avg':>8}"
)

print("-" * 90)

for i, p in enumerate(results, start=1):
    print(
        f"{i:<5}"
        f"{p['name']:<22}"
        f"{p['pos']:<12}"
        f"{p['team']:<24}"
        f"{p['proj_total']:>11.1f}"
        f"{int(p['proj_gp']):>6}"
        f"{p['avg']:>8.2f}"
    )