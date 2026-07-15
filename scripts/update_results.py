import json
import os
import urllib.request

from firebase_auth import get_db_token

API_TOKEN = os.environ.get("FOOTBALL_API_TOKEN", "49b916e7852b422187139132b9cb6ad7")
FIREBASE_URL = "https://wc2026-predictor-56ab2-default-rtdb.firebaseio.com"

# Admin access token so writes to results/scores/fixtures succeed once those
# paths are locked to read-only for clients. Falls back to None (unauthenticated,
# rules-governed) when FIREBASE_SERVICE_ACCOUNT isn't set.
DB_TOKEN = get_db_token(os.environ.get("FIREBASE_SERVICE_ACCOUNT"))


def _auth_url(url):
    """Append the OAuth access token so the request is treated as admin."""
    if not DB_TOKEN:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}access_token={DB_TOKEN}"

TEAM_MAP = {
    "Korea Republic": "South Korea",
    "Czechia": "Czech Republic",
    "Bosnia-H.": "Bosnia & Herzegovina",
    "USA": "United States",
    "Curaçao": "Curacao",
    "Türkiye": "Turkey",
    "IR Iran": "Iran",
    "Congo DR": "DR Congo",
    "Cape Verde Islands": "Cape Verde",
}

HARDCODED = [
    ("md1_01", "Mexico", "South Africa"),
    ("md1_02", "South Korea", "Czech Republic"),
    ("md1_03", "Canada", "Bosnia & Herzegovina"),
    ("md1_04", "United States", "Paraguay"),
    ("md1_05", "Qatar", "Switzerland"),
    ("md1_06", "Brazil", "Morocco"),
    ("md1_07", "Haiti", "Scotland"),
    ("md1_08", "Australia", "Turkey"),
    ("md1_09", "Germany", "Curacao"),
    ("md1_10", "Netherlands", "Japan"),
    ("md1_11", "Ivory Coast", "Ecuador"),
    ("md1_12", "Sweden", "Tunisia"),
    ("md1_13", "Spain", "Cape Verde"),
    ("md1_14", "Belgium", "Egypt"),
    ("md1_15", "Saudi Arabia", "Uruguay"),
    ("md1_16", "Iran", "New Zealand"),
    ("md1_17", "France", "Senegal"),
    ("md1_18", "Iraq", "Norway"),
    ("md1_19", "Argentina", "Algeria"),
    ("md1_20", "Austria", "Jordan"),
    ("md1_21", "Portugal", "DR Congo"),
    ("md1_22", "England", "Croatia"),
    ("md1_23", "Ghana", "Panama"),
    ("md1_24", "Uzbekistan", "Colombia"),
    ("md2_01", "Czech Republic", "South Africa"),
    ("md2_02", "Switzerland", "Bosnia & Herzegovina"),
    ("md2_03", "Canada", "Qatar"),
    ("md2_04", "Mexico", "South Korea"),
    ("md2_05", "United States", "Australia"),
    ("md2_06", "Scotland", "Morocco"),
    ("md2_07", "Brazil", "Haiti"),
    ("md2_08", "Turkey", "Paraguay"),
    ("md2_09", "Netherlands", "Sweden"),
    ("md2_10", "Germany", "Ivory Coast"),
    ("md2_11", "Ecuador", "Curacao"),
    ("md2_12", "Tunisia", "Japan"),
    ("md2_13", "Spain", "Saudi Arabia"),
    ("md2_14", "Belgium", "Iran"),
    ("md2_15", "Uruguay", "Cape Verde"),
    ("md2_16", "New Zealand", "Egypt"),
    ("md2_17", "Argentina", "Austria"),
    ("md2_18", "France", "Iraq"),
    ("md2_19", "Norway", "Senegal"),
    ("md2_20", "Jordan", "Algeria"),
    ("md2_21", "Portugal", "Uzbekistan"),
    ("md2_22", "England", "Ghana"),
    ("md2_23", "Panama", "Croatia"),
    ("md2_24", "Colombia", "DR Congo"),
    ("md3_01", "Switzerland", "Canada"),
    ("md3_02", "Bosnia & Herzegovina", "Qatar"),
    ("md3_03", "Scotland", "Brazil"),
    ("md3_04", "Morocco", "Haiti"),
    ("md3_05", "Czech Republic", "Mexico"),
    ("md3_06", "South Africa", "South Korea"),
    ("md3_07", "Curacao", "Ivory Coast"),
    ("md3_08", "Ecuador", "Germany"),
    ("md3_09", "Japan", "Sweden"),
    ("md3_10", "Tunisia", "Netherlands"),
    ("md3_11", "Turkey", "United States"),
    ("md3_12", "Paraguay", "Australia"),
    ("md3_13", "Norway", "France"),
    ("md3_14", "Senegal", "Iraq"),
    ("md3_15", "Cape Verde", "Saudi Arabia"),
    ("md3_16", "Uruguay", "Spain"),
    ("md3_17", "Egypt", "Iran"),
    ("md3_18", "New Zealand", "Belgium"),
    ("md3_19", "Panama", "England"),
    ("md3_20", "Croatia", "Ghana"),
    ("md3_21", "Colombia", "Portugal"),
    ("md3_22", "DR Congo", "Uzbekistan"),
    ("md3_23", "Algeria", "Austria"),
    ("md3_24", "Jordan", "Argentina"),
]


def normalize(name):
    return TEAM_MAP.get(name, name).lower()


def knockout_scoreline(score, is_knockout):
    """Scoreline used for scoreline/exact points: end of regulation/extra time,
    EXCLUDING any penalty shootout.

    fullTime already includes extra-time goals, so it is correct for normal
    matches and for matches decided in extra time. Only when a knockout is
    decided on penalties does fullTime hold the shootout tally — in that case
    the true end-of-ET score is regularTime + extraTime (extraTime is the goals
    scored IN extra time, i.e. incremental, so we add the two)."""
    ft = score.get("fullTime") or {}
    pen = score.get("penalties") or {}
    decided_on_pens = is_knockout and pen.get("home") is not None and pen.get("away") is not None
    if decided_on_pens:
        reg = score.get("regularTime") or {}
        et = score.get("extraTime") or {}
        return {
            "home": (reg.get("home") or 0) + (et.get("home") or 0),
            "away": (reg.get("away") or 0) + (et.get("away") or 0),
        }
    return {"home": ft.get("home"), "away": ft.get("away")}


def find_hardcoded(home, away):
    h = normalize(home)
    a = normalize(away)
    for mid, t1, t2 in HARDCODED:
        if normalize(t1) == h and normalize(t2) == a:
            return mid, t1, t2
    return None, None, None


def firebase_put(path, value):
    url = _auth_url(f"{FIREBASE_URL}/{path}.json")
    data = json.dumps(value).encode()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"  Error writing {path}: {e}")
        return False


def firebase_get(path):
    url = _auth_url(f"{FIREBASE_URL}/{path}.json")
    try:
        resp = urllib.request.urlopen(url)
        return json.loads(resp.read())
    except Exception:
        return None


def main():
    url = "https://api.football-data.org/v4/competitions/WC/matches"
    req = urllib.request.Request(url)
    req.add_header("X-Auth-Token", API_TOKEN)
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    matches = data.get("matches", [])

    updated = 0
    for m in matches:
        if m["status"] != "FINISHED":
            continue
        score = m["score"]
        winner = score.get("winner")
        is_knockout = m.get("stage") != "GROUP_STAGE"

        # Knockout matches decided on penalties report winner=null (regulation
        # was a draw). Derive the winner from the penalty tally / fullTime
        # aggregate — a knockout can never end in a draw.
        if is_knockout and (not winner or winner == "DRAW"):
            pen = score.get("penalties") or {}
            agg = score.get("fullTime") or {}
            if pen.get("home") is not None and pen.get("away") is not None and pen["home"] != pen["away"]:
                winner = "HOME_TEAM" if pen["home"] > pen["away"] else "AWAY_TEAM"
            elif agg.get("home") is not None and agg.get("away") is not None and agg["home"] != agg["away"]:
                winner = "HOME_TEAM" if agg["home"] > agg["away"] else "AWAY_TEAM"

        if not winner:
            continue

        home = m["homeTeam"].get("shortName", "")
        away = m["awayTeam"].get("shortName", "")
        if not home or not away:
            continue

        mid, t1, t2 = find_hardcoded(home, away)
        api_id = f'api_{m["id"]}'

        if winner == "HOME_TEAM":
            hc_winner = t1 if t1 else home
            dyn_winner = home
        elif winner == "AWAY_TEAM":
            hc_winner = t2 if t2 else away
            dyn_winner = away
        else:
            hc_winner = "Draw"
            dyn_winner = "Draw"

        ft = knockout_scoreline(score, is_knockout)
        score_data = {
            "homeScore": ft.get("home"),
            "awayScore": ft.get("away"),
            "status": m["status"],
        }

        # Write under hardcoded ID
        if mid:
            if firebase_put(f"results/{mid}", hc_winner):
                updated += 1
            firebase_put(f"scores/{mid}", score_data)

        # Write under api_ ID
        if firebase_put(f"results/{api_id}", dyn_winner):
            updated += 1
        firebase_put(f"scores/{api_id}", score_data)

    # Also write live/in-play matches
    for m in matches:
        if m["status"] not in ("IN_PLAY", "PAUSED"):
            continue
        home = m["homeTeam"].get("shortName", "")
        away = m["awayTeam"].get("shortName", "")
        if not home or not away:
            continue
        mid, t1, t2 = find_hardcoded(home, away)
        api_id = f'api_{m["id"]}'
        is_knockout = m.get("stage") != "GROUP_STAGE"
        ft = knockout_scoreline(m["score"], is_knockout)
        score_data = {
            "homeScore": ft.get("home"),
            "awayScore": ft.get("away"),
            "status": m["status"],
        }
        if mid:
            firebase_put(f"scores/{mid}", score_data)
        firebase_put(f"scores/{api_id}", score_data)

    # Write knockout fixtures to Firebase (so app works even if API call fails in browser)
    fixtures = {}
    for m in matches:
        if m.get("stage") == "GROUP_STAGE":
            continue
        home = m["homeTeam"].get("shortName", "") or ""
        away = m["awayTeam"].get("shortName", "") or ""
        if not home or home == "None" or not away or away == "None":
            continue
        api_id = f'api_{m["id"]}'
        fixtures[str(m["id"])] = {
            "home": home,
            "away": away,
            "utcDate": m["utcDate"],
            "stage": m.get("stage", ""),
            "status": m["status"],
        }
    if fixtures:
        firebase_put("fixtures", fixtures)
        print(f"  Wrote {len(fixtures)} knockout fixtures to Firebase")

    # Verification: check that md and api results are consistent
    fb_results = firebase_get("results") or {}
    fb_scores = firebase_get("scores") or {}
    inconsistencies = 0

    for m in matches:
        if m["status"] != "FINISHED":
            continue
        home = m["homeTeam"].get("shortName", "")
        away = m["awayTeam"].get("shortName", "")
        mid, t1, t2 = find_hardcoded(home, away)
        api_id = f'api_{m["id"]}'

        if mid:
            md_result = fb_results.get(mid)
            api_result = fb_results.get(api_id)
            md_score = fb_scores.get(mid, {})
            api_score = fb_scores.get(api_id, {})

            if md_result and api_result:
                if normalize(md_result or "") != normalize(api_result or ""):
                    print(f"  WARN: result mismatch {mid}={md_result} vs {api_id}={api_result}")
                    inconsistencies += 1
            if md_score and api_score:
                if md_score.get("homeScore") != api_score.get("homeScore") or \
                   md_score.get("awayScore") != api_score.get("awayScore"):
                    print(f"  WARN: score mismatch {mid}={md_score} vs {api_id}={api_score}")
                    inconsistencies += 1

    finished = len([m for m in matches if m["status"] == "FINISHED"])
    print(f"Updated {updated} result entries for {finished} finished matches")
    if inconsistencies:
        print(f"  WARNING: {inconsistencies} inconsistencies detected!")
    else:
        print("  Verification passed: all md/api pairs consistent")


if __name__ == "__main__":
    main()
