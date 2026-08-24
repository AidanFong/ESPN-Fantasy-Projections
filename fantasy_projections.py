import os
import json
import csv
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
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]},
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

    return league.espn_request.league_get(params=params, headers=headers)["players"]


raw_players = fetch_top_players(league, 1000)

print("Fetched:", len(raw_players))

# Override scoring settings here

SCORING = {
    13: 3.0,  # Goals
    14: 2.0,  # Assists
    15: 0.1,  # Plus/Minus
    29: 0.3,  # Shots
    31: 0.2,  # Hits
    32: 0.9,  # Blocks
    33: 0.0,  # Defenseman Point
    38: 0.3,  # PP Points
    39: 0.5,  # SH Points
    # Goalies
    1: 2.0,  # Wins
    4: -1.0,  # Goals Against
    6: 0.3,  # Saves
    7: 2.0,  # Shutouts
    9: 1.0,  # OTL
}

STAT_COLUMNS = [
    ("13", "G"),
    ("14", "A"),
    ("15", "+/-"),
    ("29", "SOG"),
    ("31", "HIT"),
    ("32", "BLK"),
    # ("33", "DPT"),
    ("38", "PPP"),
    ("39", "SHP"),
    ("1", "W"),
    ("4", "GA"),
    ("6", "SV"),
    ("7", "SO"),
    ("9", "OTL"),
]


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
        proj_gp = 84
        proj_total = fantasy_avg * proj_gp

    results.append(
        {
            "name": name,
            "pos": pos,
            "team": team,
            "gp": gp,
            "avg": fantasy_avg,
            "proj_total": proj_total,
            "proj_gp": proj_gp,
            "goalie": is_goalie,
            # Raw stats
            "stats": stats,
        }
    )


# print("Raw players:", len(raw_players))
# print("Processed:", len(results))

# before = len(results)

results = [p for p in results if p["goalie"] or p["gp"] >= MIN_GP]

# print("After GP filter:", len(results))

results.sort(key=lambda x: x["proj_total"], reverse=True)

results = results[:300]

# Export to csv
with open("fantasy_rankings.csv", "w", newline="", encoding="utf-8") as csvfile:

    writer = csv.writer(csvfile)

    # Header
    header = [
        "Rank",
        "Name",
        "Position",
        "Team",
        "Projected Total",
        "Actual GP",
        "Projected GP",
        "Fantasy Avg",
    ]

    # Add all stat column names
    for _, label in STAT_COLUMNS:
        header.append(label)

    writer.writerow(header)

    # Player rows
    for rank, p in enumerate(results, start=1):

        row = [
            rank,
            p["name"],
            p["pos"],
            p["team"],
            round(p["proj_total"], 1),
            int(p["gp"]),
            int(p["proj_gp"]),
            round(p["avg"], 2),
        ]

        # Add each raw stat
        for stat_id, _ in STAT_COLUMNS:
            value = p["stats"].get(stat_id, 0)

            if value == 0:
                row.append("")
            else:
                row.append(int(value))

        writer.writerow(row)

print("Exported fantasy_rankings.csv")

# Formatted print in terminal
# Column headers
header = (
    f"{'Rank':<5}"
    f"{'Name':<20}"
    f"{'Pos':<12}"
    f"{'Team':<24}"
    f"{'ProjTotal':>10}"
    f"{'ActualGP':>9}"
    f"{'ProjGP':>8}"
    f"{'Avg':>7}"
)

for _, label in STAT_COLUMNS:
    header += f"{label:>5}"

print(header)
print("-" * len(header))

# Print players
for i, p in enumerate(results, start=1):

    row = (
        f"{i:<5}"
        f"{p['name']:<20}"
        f"{p['pos']:<12}"
        f"{p['team']:<24}"
        f"{p['proj_total']:>10.1f}"
        f"{int(p['gp']):>9}"
        f"{int(p['proj_gp']):>8}"
        f"{p['avg']:>8.2f}"
    )

    for stat_id, _ in STAT_COLUMNS:
        value = p["stats"].get(stat_id, 0)

        if value == 0:
            row += f"{'':>5}"
        else:
            row += f"{int(value):>5}"

    print(row)
