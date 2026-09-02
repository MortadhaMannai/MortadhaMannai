#!/usr/bin/env python3
"""
F1 Pit Stop Challenge — state engine for a GitHub-Issues-driven mini-game.

How it works (mirrors the mechanic timburgan uses for his chess game):
1. A visitor opens an issue on your profile repo titled exactly:
      pitstop: push
   or
      pitstop: pit <tyre>          (tyre = soft | medium | hard | wet)

2. The workflow in .github/workflows/f1-pitstop.yml fires on that issue,
   runs this script, which:
     - reads data/pitstop_state.json
     - applies the action (advance laps, or take a pit stop + tyre change)
     - credits the visitor's username on the leaderboard
     - regenerates assets/f1-pitstop.svg with the new numbers
     - writes the state back to disk
   The workflow then commits the changes and closes the issue.

This is a STARTER KIT: the state model and SVG are intentionally simple so
you can extend them (penalties, safety cars, a full "season", etc.) without
fighting scaffolding. Test it in a scratch repo before relying on it.
"""

import json
import os
import re
import sys
from pathlib import Path

STATE_PATH = Path("data/pitstop_state.json")
SVG_PATH = Path("assets/f1-pitstop.svg")

VALID_TYRES = {"soft", "medium", "hard", "wet"}
TYRE_COLORS = {
    "soft": "#e10600",
    "medium": "#f5d300",
    "hard": "#ffffff",
    "wet": "#0072c6",
}


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "season_laps": 0,
        "current_tyre": "medium",
        "pit_stops": 0,
        "leaderboard": {},
        "last_action_by": None,
        "last_action": None,
    }


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def apply_action(state: dict, title: str, actor: str) -> str:
    """Parse the issue title and mutate state in place. Returns a human summary."""
    title = title.strip().lower()

    push_match = re.match(r"pitstop:\s*push\s*$", title)
    pit_match = re.match(r"pitstop:\s*pit\s+(\w+)\s*$", title)

    if push_match:
        state["season_laps"] += 1
        summary = f"@{actor} put the pedal down — lap {state['season_laps']} complete."
    elif pit_match:
        tyre = pit_match.group(1)
        if tyre not in VALID_TYRES:
            return (
                f"@{actor} tried to fit **{tyre}** tyres, but that compound "
                f"doesn't exist. Valid options: {', '.join(sorted(VALID_TYRES))}."
            )
        state["current_tyre"] = tyre
        state["pit_stops"] += 1
        summary = f"@{actor} called an in-lap and fitted {tyre} tyres (stop #{state['pit_stops']})."
    else:
        return (
            "Didn't recognize that command. Open an issue titled exactly "
            "`pitstop: push` or `pitstop: pit <soft|medium|hard|wet>`."
        )

    state["leaderboard"][actor] = state["leaderboard"].get(actor, 0) + 1
    state["last_action_by"] = actor
    state["last_action"] = summary
    return summary


def top_leaderboard(state: dict, n: int = 3):
    return sorted(state["leaderboard"].items(), key=lambda kv: kv[1], reverse=True)[:n]


def render_svg(state: dict) -> str:
    tyre = state["current_tyre"]
    tyre_color = TYRE_COLORS.get(tyre, "#f5d300")
    board = top_leaderboard(state)
    board_rows = ""
    if not board:
        board_rows = '<text x="40" y="150" fill="#484f58" font-size="11" font-style="italic">No moves yet — be the first to push!</text>'
    for i, (name, count) in enumerate(board):
        y = 150 + i * 20
        bar_w = min(count * 18, 200)
        board_rows += (
            f'<text x="40" y="{y}" fill="#e6edf3" font-size="11">{i + 1}. {name}</text>'
            f'<rect x="180" y="{y - 10}" width="{bar_w}" height="10" rx="3" fill="#e10600"/>'
            f'<text x="{190 + bar_w}" y="{y}" fill="#8b949e" font-size="10">{count}</text>'
        )

    return f"""<svg viewBox="0 0 500 260" xmlns="http://www.w3.org/2000/svg" font-family="'Courier New', monospace">
  <rect x="1" y="1" width="498" height="258" rx="12" fill="#0d1117" stroke="#e10600" stroke-width="1.5"/>
  <text x="250" y="28" text-anchor="middle" fill="#e10600" font-size="15" font-weight="bold">🏁 PIT STOP CHALLENGE 🏁</text>
  <text x="40" y="60" fill="#e6edf3" font-size="13">Season laps: {state['season_laps']}</text>
  <text x="40" y="82" fill="#e6edf3" font-size="13">Pit stops: {state['pit_stops']}</text>
  <text x="40" y="104" fill="#e6edf3" font-size="13">Current tyre:</text>
  <circle cx="175" cy="100" r="7" fill="{tyre_color}" stroke="#333" stroke-width="1"/>
  <text x="190" y="104" fill="{tyre_color}" font-size="13">{tyre.upper()}</text>
  <text x="40" y="135" fill="#8b949e" font-size="11">Top crew chiefs:</text>
  {board_rows}
  <text x="250" y="248" text-anchor="middle" fill="#484f58" font-size="10" font-style="italic">
    Open an issue: "pitstop: push" or "pitstop: pit soft"
  </text>
</svg>"""


def main():
    if len(sys.argv) < 3:
        print("usage: update_pitstop.py '<issue title>' '<issue author>'", file=sys.stderr)
        sys.exit(1)

    title, actor = sys.argv[1], sys.argv[2]
    state = load_state()
    summary = apply_action(state, title, actor)
    save_state(state)

    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(render_svg(state))

    # Emit the summary so the workflow can post it back as an issue comment.
    print(summary)

    # Also expose it to later workflow steps via GITHUB_OUTPUT.
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"summary={summary}\n")


if __name__ == "__main__":
    main()
