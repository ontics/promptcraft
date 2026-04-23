#!/usr/bin/env python3
"""
Export one game from Supabase as JSON, and/or render an HTML teammate report
of post-game free-text fields from that export.

Usage (from repo root or promptcraft/; needs SUPABASE_URL + SUPABASE_KEY in .env):

  cd promptcraft
  python scripts/export_game_survey_bundle.py export 60 -o game_60.json
  python scripts/export_game_survey_bundle.py report -i game_60.json -o game_60_freeform.html
  python scripts/export_game_survey_bundle.py full 60 --analysis-dir ../analysis

`full` writes under repo `analysis/`: game_{id}_bundle.json, game_{id}_post_survey_analysis.json,
game_{id}_post_survey_freeform.html (HTML includes automated checks + free-text table).

The HTML report is standalone (embedded CSS) for easy sharing.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional


EXPORT_VERSION = 1

# Repo root = parent of `promptcraft/` (this file: promptcraft/scripts/…)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ANALYSIS_DIR = REPO_ROOT / "analysis"

# Heuristic substrings for “might be flagging images / fairness” (manual + LLM follow-up).
Q4_SCAN_KEYWORDS = [
    "rigged",
    "unfair",
    "not fair",
    "duplicate",
    "identical",
    "same image",
    "suspicious",
    "suspect",
    "weird",
    "strange",
    "cheat",
    "cheating",
    "fake",
    "stock photo",
    "didn't match",
    "did not match",
    "wrong image",
    "copied",
    "stole",
    "obvious",
    "biased",
    "targeted",
    "knew",
    "figured out",
    "given away",
    "spoiler",
]

FREE_FIELD_PROMPTS = [
    (
        "post_survey_free_q1",
        "Open response 1",
        "What was your thought process when allocating points in voting?",
    ),
    (
        "post_survey_free_q2",
        "Open response 2",
        "How did you decide when to give an image more or less points than another image in the same round of voting?",
    ),
    (
        "post_survey_free_q3",
        "Open response 3",
        "During image creation, what information, if any, was displayed about your prompting?",
    ),
    (
        "post_survey_free_q4",
        "Open response 4",
        "On the voting screen, what information, if any, was displayed about the images?",
    ),
]


def _find_dotenv() -> Path | None:
    """Prefer promptcraft/.env (parent of this scripts/ directory)."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / ".env",  # promptcraft/.env — most reliable when script lives in scripts/
        here / ".env",
        here.parent.parent / ".env",  # repo root
        Path.cwd() / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _apply_simple_env_file(path: Path) -> None:
    """Parse KEY=value lines so export works even when python-dotenv is not installed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, rest = s.partition("=")
        key = key.strip()
        val = rest.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key:
            os.environ[key] = val


def _load_env() -> None:
    p = _find_dotenv()
    if p:
        _apply_simple_env_file(p)
        try:
            from dotenv import load_dotenv

            load_dotenv(p, override=True)
        except ImportError:
            pass
    else:
        try:
            from dotenv import load_dotenv

            load_dotenv(override=True)
        except ImportError:
            pass


def _client():
    _load_env()
    url = os.getenv("SUPABASE_URL", "").strip()
    # App uses SUPABASE_KEY; some setups use SUPABASE_SERVICE_ROLE_KEY for the secret JWT / sb_secret key.
    key = (
        os.getenv("SUPABASE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        dot = _find_dotenv()
        hint = f" (looked for .env at: {dot})" if dot else " (no .env file found on known paths)"
        print(
            "Missing SUPABASE_URL or SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) in environment."
            + hint,
            file=sys.stderr,
        )
        sys.exit(1)
    from supabase import create_client

    return create_client(url, key)


def fetch_bundle(game_id: int) -> dict:
    sb = _client()
    g = sb.table("games").select("*").eq("game_id", game_id).execute()
    players = sb.table("players").select("*").eq("game_id", game_id).execute()
    rounds = sb.table("rounds").select("*").eq("game_id", game_id).execute()
    game_row = (g.data or [None])[0] if g.data else None
    return {
        "export_version": EXPORT_VERSION,
        "game_id": game_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "game": game_row,
        "players": players.data or [],
        "rounds": rounds.data or [],
    }


def cmd_export(game_id: int, out_path: Path, pretty: bool) -> None:
    bundle = fetch_bundle(game_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2 if pretty else None, ensure_ascii=False)
        if not pretty:
            f.write("\n")
    print(f"Wrote {out_path} ({len(bundle['players'])} players, {len(bundle['rounds'])} rounds).")


def _is_likely_gamemaster_row(p: dict) -> bool:
    """DB has no is_admin; gamemaster row is usually no team/character."""
    if p.get("condition") is None and p.get("character") is None:
        return True
    name = (p.get("player_name") or "").lower()
    return "admin" in name or name == "gamemaster"


def _scan_keywords(text: str, keywords: List[str]) -> List[Dict[str, Any]]:
    if not text:
        return []
    low = text.lower()
    out: List[Dict[str, Any]] = []
    for kw in keywords:
        k = kw.lower()
        if k in low:
            out.append({"keyword": kw, "count": low.count(k)})
    return out


def analyze_bundle(bundle: dict) -> dict:
    game = bundle.get("game") or {}
    players: List[dict] = bundle.get("players") or []
    gid = bundle.get("game_id") or game.get("game_id")
    total_players = game.get("total_players")

    non_gm = [p for p in players if not _is_likely_gamemaster_row(p)]
    gm_rows = [p for p in players if _is_likely_gamemaster_row(p)]

    def is_incomplete(p: dict) -> bool:
        if not p.get("post_survey_submitted_at"):
            return False
        for col, _, _ in FREE_FIELD_PROMPTS:
            if not str(p.get(col) or "").strip():
                return True
        if not str(p.get("post_survey_likert_best_work") or "").strip():
            return True
        if not str(p.get("post_survey_likert_effort") or "").strip():
            return True
        return False

    missing_sub = [p.get("player_name") or p.get("player_id") for p in non_gm if not p.get("post_survey_submitted_at")]
    incomplete = [p.get("player_name") or p.get("player_id") for p in non_gm if is_incomplete(p)]
    no_extended = [
        p.get("player_name") or p.get("player_id")
        for p in non_gm
        if p.get("post_survey_submitted_at") and p.get("post_survey_extended") is None
    ]

    q4_triggers: List[dict] = []
    for p in non_gm:
        q4 = str(p.get("post_survey_free_q4") or "")
        matches = _scan_keywords(q4, Q4_SCAN_KEYWORDS)
        if matches:
            q4_triggers.append(
                {
                    "player_name": p.get("player_name"),
                    "player_id": p.get("player_id"),
                    "matches": matches,
                    "q4_char_count": len(q4.strip()),
                }
            )

    roster_gap = None
    if total_players is not None:
        roster_gap = int(total_players) - len(players)

    return {
        "game_id": gid,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Gamemaster is inferred as rows with condition IS NULL AND character IS NULL, or player_name containing 'admin'.",
            "Keyword list is a crude screen for fairness/image-suspicion language in Q4 only; use an LLM on the bundle JSON for real thematic coding.",
        ],
        "roster": {
            "games_total_players_at_start": total_players,
            "player_rows_in_this_export": len(players),
            "likely_gamemaster_rows": len(gm_rows),
            "likely_participant_rows": len(non_gm),
            "delta_total_players_minus_export_rows": roster_gap,
            "export_looks_complete": roster_gap == 0 if roster_gap is not None else None,
        },
        "post_survey": {
            "participant_submitted_count": sum(1 for p in non_gm if p.get("post_survey_submitted_at")),
            "participant_missing_submission": missing_sub,
            "participant_incomplete_after_submit": incomplete,
            "participant_missing_post_survey_extended": no_extended,
        },
        "q4_keyword_scan": {
            "keywords_used": Q4_SCAN_KEYWORDS,
            "players_with_any_q4_keyword_hit": q4_triggers,
        },
    }


def _analysis_to_html_section(analysis: dict) -> str:
    roster = analysis.get("roster") or {}
    ps = analysis.get("post_survey") or {}
    q4 = analysis.get("q4_keyword_scan") or {}
    hits = q4.get("players_with_any_q4_keyword_hit") or []

    complete = roster.get("export_looks_complete")
    warn = ""
    if complete is False:
        warn = (
            '<p class="warn"><strong>Incomplete roster export:</strong> '
            "<code>games.total_players</code> does not match the number of <code>players</code> rows "
            f"({roster.get('games_total_players_at_start')} vs {roster.get('player_rows_in_this_export')}). "
            "Re-run with a Supabase key that can read all rows (e.g. secret key) and no row limit.</p>"
        )
    elif complete is None:
        warn = '<p class="sub">Could not compare roster completeness (missing <code>total_players</code>).</p>'

    miss = ps.get("participant_missing_submission") or []
    miss_li = "".join(f"<li>{html.escape(str(m))}</li>" for m in miss) or "<li>None</li>"

    hit_rows = ""
    for row in hits:
        mstr = ", ".join(f"{m['keyword']}×{m['count']}" for m in row.get("matches") or [])
        pname = html.escape(str(row.get("player_name") or ""))
        hit_rows += f"<tr><td>{pname}</td><td>{html.escape(mstr)}</td><td>{row.get('q4_char_count', '')}</td></tr>"

    if not hit_rows:
        hit_rows = '<tr><td colspan="3" class="empty">No Q4 keyword hits (heuristic list only).</td></tr>'

    notes = analysis.get("notes") or []
    notes_html = "".join(f"<li>{html.escape(n)}</li>" for n in notes)

    return f"""
  <section class="analysis">
    <h2>Automated checks</h2>
    {warn}
    <ul class="sub">{notes_html}</ul>
    <div class="stats">
      <div class="stat">Participant rows: <strong>{roster.get('likely_participant_rows')}</strong></div>
      <div class="stat">Submitted post-survey: <strong>{ps.get('participant_submitted_count')}</strong></div>
      <div class="stat">Missing submission (participants): <strong>{len(miss)}</strong></div>
      <div class="stat">Q4 keyword hits: <strong>{len(hits)}</strong> players</div>
    </div>
    <h3>Missing post-survey (participant names / ids)</h3>
    <ul class="miss">{miss_li}</ul>
    <h3>Q4 keyword hits (heuristic)</h3>
    <div class="wrap">
      <table class="small">
        <thead><tr><th>Player</th><th>Matches</th><th>Q4 chars</th></tr></thead>
        <tbody>{hit_rows}</tbody>
      </table>
    </div>
  </section>
"""


def build_report_html(bundle: dict, source_label: str, analysis_section_html: Optional[str] = None) -> str:
    game = bundle.get("game") or {}
    players = bundle.get("players") or []
    gid = bundle.get("game_id") or game.get("game_id")

    rows_html = []
    submitted = 0
    missing = 0
    incomplete = 0

    def is_incomplete(p: dict) -> bool:
        if not p.get("post_survey_submitted_at"):
            return False
        for col, _, _ in FREE_FIELD_PROMPTS:
            if not str(p.get(col) or "").strip():
                return True
        if not str(p.get("post_survey_likert_best_work") or "").strip():
            return True
        if not str(p.get("post_survey_likert_effort") or "").strip():
            return True
        return False

    for p in sorted(players, key=lambda x: (x.get("player_name") or "").lower()):
        name = html.escape(str(p.get("player_name") or ""))
        pid = html.escape(str(p.get("player_id") or ""))
        cond = html.escape(str(p.get("condition") or ""))
        sub_at = p.get("post_survey_submitted_at")
        if sub_at:
            submitted += 1
        else:
            missing += 1
        inc = is_incomplete(p)
        if inc:
            incomplete += 1
        status = "Submitted" if sub_at else "Not submitted"
        if inc:
            status += " (incomplete columns)"
        status_e = html.escape(status)
        sub_e = html.escape(str(sub_at or ""))

        tds = [
            f"<td class=\"name\"><strong>{name}</strong><br><span class=\"pid\">{pid}</span></td>",
            f"<td>{cond}</td>",
            f"<td class=\"meta\">{status_e}<br><span class=\"ts\">{sub_e}</span></td>",
        ]
        for col, _, _ in FREE_FIELD_PROMPTS:
            tds.append(_cell(p.get(col)))
        rows_html.append("<tr>" + "".join(tds) + "</tr>")

    thead_cols = ["<th>Player</th>", "<th>Condition</th>", "<th>Survey status</th>"]
    for _, legend, prompt in FREE_FIELD_PROMPTS:
        thead_cols.append(
            f"<th><span class=\"leg\">{html.escape(legend)}</span><br>"
            f"<span class=\"pr\">{html.escape(prompt)}</span></th>"
        )
    thead = "<tr>" + "".join(thead_cols) + "</tr>"

    started = html.escape(str(game.get("started_at") or ""))
    ended = html.escape(str(game.get("ended_at") or ""))
    total_p = game.get("total_players")
    total_players_note = (
        f' · <code>total_players</code> at start: <strong>{html.escape(str(total_p))}</strong>'
        if total_p is not None
        else ""
    )

    analysis_block = analysis_section_html or ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Post-game free text — game {html.escape(str(gid))}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 1.25rem 1.5rem 2rem; color: #1a1a1a; background: #f6f7f9; }}
    h1 {{ font-size: 1.35rem; margin: 0 0 0.35rem; }}
    h2 {{ font-size: 1.1rem; margin: 1.5rem 0 0.5rem; }}
    h3 {{ font-size: 0.95rem; margin: 1rem 0 0.35rem; }}
    .sub {{ color: #444; font-size: 0.95rem; margin-bottom: 1rem; line-height: 1.45; }}
    .warn {{ background: #fff8e6; border: 1px solid #e8c96b; border-radius: 8px; padding: 0.75rem 1rem; margin: 0.75rem 0; font-size: 0.9rem; color: #5c4a10; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0 1.25rem; }}
    .stat {{ background: #fff; border: 1px solid #e2e4e8; border-radius: 8px; padding: 0.6rem 0.9rem; font-size: 0.9rem; }}
    .wrap {{ overflow-x: auto; background: #fff; border: 1px solid #e2e4e8; border-radius: 10px; padding: 0.5rem; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 720px; font-size: 0.88rem; }}
    table.small {{ min-width: 480px; font-size: 0.82rem; }}
    th, td {{ border: 1px solid #e8eaef; padding: 0.5rem 0.55rem; vertical-align: top; text-align: left; }}
    th {{ background: #eef1f6; font-weight: 600; }}
    th .leg {{ font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; color: #555; }}
    th .pr {{ font-weight: 500; color: #222; margin-top: 0.25rem; display: block; line-height: 1.35; }}
    td.name .pid {{ font-size: 0.72rem; color: #666; word-break: break-all; }}
    td.meta {{ font-size: 0.82rem; white-space: nowrap; }}
    td.meta .ts {{ color: #666; font-size: 0.78rem; }}
    td.free {{ max-width: 22rem; }}
    td.free .free-inner {{ white-space: pre-wrap; word-break: break-word; line-height: 1.4; max-height: 16rem; overflow: auto; }}
    td.empty {{ color: #999; text-align: center; }}
    ul.miss {{ margin: 0.25rem 0 1rem 1.2rem; }}
    section.analysis {{ margin-bottom: 1.5rem; }}
    footer {{ margin-top: 1.25rem; font-size: 0.8rem; color: #666; }}
  </style>
</head>
<body>
  <h1>Post-game survey — free text</h1>
  <p class="sub">Game ID <strong>{html.escape(str(gid))}</strong> · source: <code>{html.escape(source_label)}</code><br>
  Session window (DB): <strong>{started}</strong> → <strong>{ended}</strong>{total_players_note}</p>
  {analysis_block}
  <div class="stats">
    <div class="stat"><strong>{len(players)}</strong> player rows</div>
    <div class="stat"><strong>{submitted}</strong> with <code>post_survey_submitted_at</code></div>
    <div class="stat"><strong>{missing}</strong> missing submission</div>
    <div class="stat"><strong>{incomplete}</strong> submitted but incomplete columns</div>
  </div>
  <p class="sub">Open responses below map to <code>post_survey_free_q1</code>–<code>q4</code>. Q4 is the voting-screen wording — useful for spotting comments about images.</p>
  <div class="wrap">
    <table>
      <thead>{thead}</thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table>
  </div>
  <footer>Generated {html.escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))}. Do not publish if it contains identifiable participant text without consent.</footer>
</body>
</html>
"""


def cmd_full(game_id: int, analysis_dir: Path, pretty: bool) -> None:
    bundle = fetch_bundle(game_id)
    analysis_dir = analysis_dir.resolve()
    analysis_dir.mkdir(parents=True, exist_ok=True)
    base = analysis_dir / f"game_{game_id}"

    bundle_path = base.parent / f"{base.name}_bundle.json"
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2 if pretty else None, ensure_ascii=False)
        if not pretty:
            f.write("\n")

    analysis = analyze_bundle(bundle)
    analysis_path = base.parent / f"{base.name}_post_survey_analysis.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    section = _analysis_to_html_section(analysis)
    html_doc = build_report_html(bundle, bundle_path.name, analysis_section_html=section)
    html_path = base.parent / f"{base.name}_post_survey_freeform.html"
    html_path.write_text(html_doc, encoding="utf-8")

    print(f"Wrote {bundle_path}")
    print(f"Wrote {analysis_path}")
    print(f"Wrote {html_path}")
    print(f"Players: {len(bundle['players'])}, rounds: {len(bundle['rounds'])}.")


def _cell(text: str | None) -> str:
    s = (text or "").strip()
    if not s:
        return '<td class="empty">—</td>'
    esc = html.escape(s)
    return f'<td class="free"><div class="free-inner">{esc}</div></td>'


def cmd_report(in_path: Path, out_path: Path) -> None:
    with open(in_path, encoding="utf-8") as f:
        bundle = json.load(f)
    analysis = analyze_bundle(bundle)
    section = _analysis_to_html_section(analysis)
    doc = build_report_html(bundle, in_path.name, analysis_section_html=section)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    print(f"Wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export game JSON from Supabase and/or HTML free-text report.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ex = sub.add_parser("export", help="Fetch game + players + rounds from Supabase into one JSON file.")
    p_ex.add_argument("game_id", type=int, help="games.game_id")
    p_ex.add_argument("-o", "--output", type=Path, required=True, help="Output .json path")
    p_ex.add_argument("--no-pretty", action="store_true", help="Minify JSON")

    p_rp = sub.add_parser("report", help="Build HTML teammate report from a bundle JSON (no DB needed).")
    p_rp.add_argument("-i", "--input", type=Path, required=True, help="Bundle .json from export")
    p_rp.add_argument("-o", "--output", type=Path, required=True, help="Output .html path")

    p_fu = sub.add_parser(
        "full",
        help="Export bundle + analysis JSON + HTML report into analysis/ (default: repo root analysis/).",
    )
    p_fu.add_argument("game_id", type=int, help="games.game_id")
    p_fu.add_argument(
        "--analysis-dir",
        type=Path,
        default=DEFAULT_ANALYSIS_DIR,
        help=f"Output directory (default: {DEFAULT_ANALYSIS_DIR})",
    )
    p_fu.add_argument("--no-pretty", action="store_true", help="Minify bundle JSON")

    args = parser.parse_args()
    if args.cmd == "export":
        cmd_export(args.game_id, args.output, pretty=not args.no_pretty)
    elif args.cmd == "report":
        cmd_report(args.input, args.output)
    elif args.cmd == "full":
        cmd_full(args.game_id, args.analysis_dir, pretty=not args.no_pretty)
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
