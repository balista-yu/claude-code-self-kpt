#!/usr/bin/env python3
"""
Claude Code Self-Improvement KPT Dashboard
アクティビティログ + セッション自己分析 + KPT結果 + Experiment を可視化

Usage: python3 ~/.claude/scripts/kpt-viewer.py
"""

import http.server
import json
import os
import re
import glob
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PORT = 8765
HOME = str(Path.home())
KPT_DATA = os.path.join(HOME, ".claude", "kpt-data")
ACTIVITY_DIR = os.path.join(KPT_DATA, "activity-logs")
REVIEWS_DIR = os.path.join(KPT_DATA, "session-reviews")
KPT_DIR = os.path.join(KPT_DATA, "kpt")
EXPERIMENTS_DIR = os.path.join(KPT_DATA, "experiments")
COST_LOGS_DIR = os.path.join(KPT_DATA, "cost-logs")


def load_activity_stats():
    """アクティビティログからプロジェクト別・日別・時間帯の活動量を集計"""
    stats = {
        "daily": {},
        "projects": {},
        "hour_weekday": [[0] * 24 for _ in range(7)],  # weekday(0=Mon) x hour
        "session_sizes": {},  # session_id -> interaction count
    }
    for f in glob.glob(os.path.join(ACTIVITY_DIR, "*.jsonl")):
        try:
            with open(f, "r") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    date = entry.get("local_date", "unknown")
                    project = entry.get("project", "unknown")
                    sid = entry.get("session_id", "unknown")

                    if date not in stats["daily"]:
                        stats["daily"][date] = {"interactions": 0, "projects": set()}
                    stats["daily"][date]["interactions"] += 1
                    stats["daily"][date]["projects"].add(project)

                    if project not in stats["projects"]:
                        stats["projects"][project] = {"interactions": 0, "days": set()}
                    stats["projects"][project]["interactions"] += 1
                    stats["projects"][project]["days"].add(date)

                    # Hour × Weekday ヒートマップ（ローカルTZに変換）
                    ts = entry.get("timestamp", "")
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                        stats["hour_weekday"][dt.weekday()][dt.hour] += 1
                    except Exception:
                        pass

                    # セッションあたりインタラクション数
                    stats["session_sizes"][sid] = stats["session_sizes"].get(sid, 0) + 1
        except Exception:
            continue

    # setをlistに変換（JSON化のため）
    for d in stats["daily"].values():
        d["projects"] = list(d["projects"])
        d["project_count"] = len(d["projects"])
    for p in stats["projects"].values():
        p["days"] = len(p["days"])

    return stats


def load_cost_stats():
    """SessionEnd hook の Haiku 呼び出しコストを月次/直近セッション単位で集計。"""
    monthly = {}  # "YYYY-MM" -> {input, output, cache_read, cache_creation, cost_usd, sessions}
    sessions = []  # 直近セッション（最大 50 件）

    for f in sorted(glob.glob(os.path.join(COST_LOGS_DIR, "cost_*.jsonl"))):
        month = os.path.basename(f).replace("cost_", "").replace(".jsonl", "")
        if month not in monthly:
            monthly[month] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cost_usd": 0.0,
                "sessions": 0,
            }
        try:
            with open(f, "r") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    m = monthly[month]
                    m["input_tokens"] += int(entry.get("input_tokens", 0) or 0)
                    m["output_tokens"] += int(entry.get("output_tokens", 0) or 0)
                    m["cache_read_input_tokens"] += int(entry.get("cache_read_input_tokens", 0) or 0)
                    m["cache_creation_input_tokens"] += int(entry.get("cache_creation_input_tokens", 0) or 0)
                    m["cost_usd"] += float(entry.get("cost_usd", 0) or 0)
                    m["sessions"] += 1
                    sessions.append(entry)
        except Exception:
            continue

    # 直近セッション（timestamp 降順 / 最大 50 件）
    sessions.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    sessions = sessions[:50]

    # 月次を月降順でリスト化
    monthly_list = [
        {"month": k, **v, "cost_usd": round(v["cost_usd"], 4)}
        for k, v in sorted(monthly.items(), reverse=True)
    ]

    totals = {
        "input_tokens": sum(m["input_tokens"] for m in monthly.values()),
        "output_tokens": sum(m["output_tokens"] for m in monthly.values()),
        "cache_read_input_tokens": sum(m["cache_read_input_tokens"] for m in monthly.values()),
        "cache_creation_input_tokens": sum(m["cache_creation_input_tokens"] for m in monthly.values()),
        "cost_usd": round(sum(m["cost_usd"] for m in monthly.values()), 4),
        "sessions": sum(m["sessions"] for m in monthly.values()),
    }

    return {"monthly": monthly_list, "recent": sessions, "totals": totals}


def parse_review(filepath):
    """セッション自己分析ファイルをパース"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(filepath)
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{6})", filename)
        date = date_match.group(1) if date_match else "unknown"
        time_str = date_match.group(2) if date_match else "000000"
        session_id_match = re.match(r"\d{4}-\d{2}-\d{2}_\d{6}_([a-f0-9]+)", filename)
        session_id = session_id_match.group(1) if session_id_match else ""

        project_match = re.search(r"プロジェクト:\s*(.+)", content)
        if not project_match:
            project_match = re.search(r"自己分析:\s*(\S+)", content)
        project = project_match.group(1).strip() if project_match else "unknown"

        # ユーザー指摘事項を抽出
        issues = []
        issues_section = re.search(
            r"## ユーザー指摘事項(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        if issues_section:
            text = issues_section.group(1)
            if "指摘なし" not in text:
                category_issues = re.findall(
                    r"\*\*\[([^\]]+)\]\*\*\s*(.+)", text
                )
                for cat, desc in category_issues:
                    issues.append({"category": cat.strip(), "description": desc.strip()})
                if not category_issues:
                    lines = [l.strip("- ").strip() for l in text.split("\n")
                             if l.strip().startswith("-")]
                    for l in lines:
                        if l and "指摘なし" not in l:
                            issues.append({"category": "その他", "description": l})

        actions = []
        actions_section = re.search(
            r"## 自己改善アクション(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        if actions_section:
            action_items = re.findall(
                r"\*\*\[([^\]]+)\]\*\*\s*(.+)", actions_section.group(1)
            )
            for kind, desc in action_items:
                actions.append({"kind": kind.strip(), "description": desc.strip()})

        summary_match = re.search(r"## 概要\n(.+?)(?=\n## |\Z)", content, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        return {
            "file": filename,
            "date": date,
            "time": time_str,
            "session_id": session_id,
            "project": project,
            "summary": summary[:120],
            "issue_count": len(issues),
            "issues": issues,
            "actions": actions,
            "content": content,
        }
    except Exception as e:
        return {"file": os.path.basename(filepath), "error": str(e)}


def load_experiments():
    """Experimentファイルをパースしてカンバン用データを返す"""
    experiments = []
    if not os.path.exists(EXPERIMENTS_DIR):
        return experiments
    for f in sorted(glob.glob(os.path.join(EXPERIMENTS_DIR, "experiment_*.md"))):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()
            filename = os.path.basename(f)
            week_match = re.search(r"experiment_(\d{4}-W\d{2})", filename)
            week = week_match.group(1) if week_match else "unknown"

            # ## EX: Title 形式で各実験を切り出す
            blocks = re.split(r"\n## (E\d+:[^\n]+)", content)
            # 最初の要素はタイトル前のゴミ
            for i in range(1, len(blocks), 2):
                header = blocks[i].strip()
                body = blocks[i + 1] if i + 1 < len(blocks) else ""
                title_match = re.match(r"E\d+:\s*(.+)", header)
                title = title_match.group(1).strip() if title_match else header

                def field(name):
                    m = re.search(rf"-\s*{name}\s*:\s*(.+)", body)
                    return m.group(1).strip() if m else ""

                experiments.append({
                    "week": week,
                    "id": header.split(":")[0],
                    "title": title,
                    "status": field("status") or "in_progress",
                    "hypothesis": field("hypothesis"),
                    "success_criteria": field("success_criteria"),
                    "measurement": field("measurement"),
                    "scope": field("scope"),
                    "started": field("started"),
                    "content": body.strip(),
                })
        except Exception:
            continue
    return experiments


def extract_tries_from_kpts(kpts):
    """KPTアーカイブからTry項目と実装状況を抽出してTry寿命データにする"""
    tries = []
    for kpt in kpts:
        if "content" not in kpt:
            continue
        content = kpt["content"]
        week_match = re.search(r"(\d{4})[年\s]+第(\d{2})週", content)
        if not week_match:
            week_match = re.match(r"(\d{4})-W(\d{2})\.md", kpt["file"])
        if week_match:
            week = f"{week_match.group(1)}-W{week_match.group(2)}"
        else:
            week = kpt["file"].replace(".md", "")

        try_section = re.search(r"## Try(.*?)(?=\n## |\Z)", content, re.DOTALL)
        if not try_section:
            continue
        try_text = try_section.group(1)
        # T1: タイトル
        for m in re.finditer(r"###\s*(T\d+):\s*([^\n]+)(.*?)(?=\n###|\Z)",
                             try_text, re.DOTALL):
            tid = m.group(1)
            title = m.group(2).strip()
            body = m.group(3)
            impl_marker = re.compile(r"\[✅\s*実装済み\s*(\d{4}-\d{2}-\d{2})\]")
            # タイトル自身にマーカーが入るケース（T1: xxx [✅ 実装済み 2026-04-01]）と
            # ボディに入るケース両方を見る
            impl_date_match = impl_marker.search(title) or impl_marker.search(body)
            impl_date = impl_date_match.group(1) if impl_date_match else None
            clean_title = impl_marker.sub("", title).strip()
            tries.append({
                "week": week,
                "id": tid,
                "title": clean_title,
                "implemented": impl_date is not None,
                "impl_date": impl_date,
            })
    return tries


def aggregate_category_heatmap(reviews):
    """カテゴリ × 週 ヒートマップデータ"""
    matrix = defaultdict(lambda: defaultdict(int))
    weeks = set()
    categories = Counter()
    for r in reviews:
        if "error" in r:
            continue
        try:
            dt = datetime.strptime(r["date"], "%Y-%m-%d")
            iso = dt.isocalendar()
            week_key = f"{iso[0]}-W{iso[1]:02d}"
        except Exception:
            continue
        weeks.add(week_key)
        for issue in r.get("issues", []):
            cat = issue.get("category", "その他")
            matrix[cat][week_key] += 1
            categories[cat] += 1

    week_list = sorted(weeks)[-12:]  # 直近12週
    top_cats = [c for c, _ in categories.most_common(10)]
    data = []
    for cat in top_cats:
        row = {"category": cat, "values": []}
        for w in week_list:
            row["values"].append(matrix[cat].get(w, 0))
        data.append(row)
    return {"weeks": week_list, "rows": data}


def detect_burning_categories(reviews):
    """直近7日の指摘数が過去平均×1.5以上のカテゴリを検出"""
    today = datetime.now().date()
    recent_cutoff = today - timedelta(days=7)
    past_cutoff = today - timedelta(days=28)

    recent = Counter()
    past = Counter()
    for r in reviews:
        if "error" in r:
            continue
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        for issue in r.get("issues", []):
            cat = issue.get("category", "その他")
            if d >= recent_cutoff:
                recent[cat] += 1
            elif d >= past_cutoff:
                past[cat] += 1

    burning = []
    for cat, recent_n in recent.items():
        past_avg = past.get(cat, 0) / 3  # 過去3週平均（週あたり）
        threshold = max(past_avg * 1.5, 2)
        if recent_n >= threshold and recent_n >= 2:
            burning.append({
                "category": cat,
                "recent": recent_n,
                "past_weekly_avg": round(past_avg, 1),
                "multiplier": round(recent_n / past_avg, 1) if past_avg > 0 else None,
            })
    burning.sort(key=lambda x: -x["recent"])
    return burning


def project_issue_distribution(reviews):
    """プロジェクト別指摘分布"""
    by_project = Counter()
    for r in reviews:
        if "error" in r:
            continue
        by_project[r.get("project", "unknown")] += r.get("issue_count", 0)
    return by_project.most_common(10)


def session_quality_scatter(reviews, activity):
    """セッション長 × 指摘件数 散布図データ"""
    sizes = activity.get("session_sizes", {})
    # session_idは先頭8文字だけ保存されているので prefix→size の逆引き辞書を事前構築
    prefix_size = {}
    for full_sid, n in sizes.items():
        prefix_size.setdefault(full_sid[:8], 0)
        prefix_size[full_sid[:8]] += n  # 同prefix衝突時は合算
    points = []
    for r in reviews:
        if "error" in r:
            continue
        sid = r.get("session_id", "")
        if not sid:
            continue
        size = prefix_size.get(sid[:8], 0)
        if size > 0:
            points.append({
                "size": size,
                "issues": r.get("issue_count", 0),
                "project": r.get("project", ""),
                "date": r.get("date", ""),
            })
    return points


def get_dashboard_data():
    activity = load_activity_stats()

    reviews = []
    for month_dir in sorted(glob.glob(os.path.join(REVIEWS_DIR, "*"))):
        if os.path.isdir(month_dir):
            for f in sorted(glob.glob(os.path.join(month_dir, "*.md"))):
                reviews.append(parse_review(f))
        elif month_dir.endswith(".md"):
            reviews.append(parse_review(month_dir))

    kpts = []
    for f in sorted(glob.glob(os.path.join(KPT_DIR, "*.md"))):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                kpts.append({"file": os.path.basename(f), "content": fh.read()})
        except Exception as e:
            kpts.append({"file": os.path.basename(f), "error": str(e)})

    category_freq = {}
    for r in reviews:
        if "error" in r:
            continue
        for issue in r.get("issues", []):
            cat = issue.get("category", "その他")
            category_freq[cat] = category_freq.get(cat, 0) + 1
    top_categories = sorted(category_freq.items(), key=lambda x: -x[1])[:10]

    action_types = {}
    for r in reviews:
        if "error" in r:
            continue
        for action in r.get("actions", []):
            kind = action.get("kind", "other")
            action_types[kind] = action_types.get(kind, 0) + 1

    total_reviews = len([r for r in reviews if "error" not in r])
    clean_reviews = len([r for r in reviews if "error" not in r and r.get("issue_count", 0) == 0])

    experiments = load_experiments()
    tries = extract_tries_from_kpts(kpts)
    category_heatmap = aggregate_category_heatmap(reviews)
    burning = detect_burning_categories(reviews)
    project_issues = project_issue_distribution(reviews)
    quality_scatter = session_quality_scatter(reviews, activity)
    costs = load_cost_stats()

    # hour_weekday は JSON化のため dict に
    hw = activity.pop("hour_weekday", [[0] * 24 for _ in range(7)])
    activity.pop("session_sizes", None)  # 容量削減

    return {
        "activity": activity,
        "hour_weekday": hw,
        "reviews": reviews,
        "kpts": kpts,
        "experiments": experiments,
        "tries": tries,
        "category_heatmap": category_heatmap,
        "burning_categories": burning,
        "project_issues": project_issues,
        "quality_scatter": quality_scatter,
        "top_categories": top_categories,
        "action_types": action_types,
        "total_reviews": total_reviews,
        "clean_rate": round(clean_reviews / total_reviews * 100, 1) if total_reviews else 0,
        "costs": costs,
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code Self-Improvement Dashboard</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#0f172a; color:#e2e8f0; }
  .container { max-width:1200px; margin:0 auto; padding:20px; }
  h1 { font-size:1.6rem; margin-bottom:6px; color:#38bdf8; }
  .subtitle { font-size:0.85rem; color:#64748b; margin-bottom:24px; }
  h2 { font-size:1.2rem; margin-bottom:14px; color:#94a3b8; }
  .stats-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; margin-bottom:28px; }
  .stat-card { background:#1e293b; border-radius:12px; padding:18px; border:1px solid #334155; }
  .stat-value { font-size:2rem; font-weight:bold; color:#38bdf8; }
  .stat-label { font-size:0.8rem; color:#94a3b8; margin-top:4px; }
  .section { background:#1e293b; border-radius:12px; padding:22px; margin-bottom:20px; border:1px solid #334155; }
  .two-col { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
  @media(max-width:768px) { .two-col { grid-template-columns:1fr; } }
  .bar-row { display:flex; align-items:center; margin-bottom:6px; }
  .bar-row .label { flex:1; font-size:0.82rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .bar-row .bar { height:22px; border-radius:4px; margin-left:10px; min-width:28px; display:flex; align-items:center; justify-content:center; font-size:0.72rem; font-weight:bold; }
  .bar-issue { background:#f43f5e; }
  .bar-action { background:#a78bfa; }
  .bar-project { background:#38bdf8; }
  .entry { padding:10px; border-bottom:1px solid #334155; cursor:pointer; transition:background 0.15s; }
  .entry:hover { background:#334155; }
  .entry-date { font-size:0.75rem; color:#64748b; }
  .entry-project { display:inline-block; background:#38bdf833; color:#38bdf8; padding:1px 7px; border-radius:4px; font-size:0.68rem; margin-left:6px; }
  .entry-badge-issue { display:inline-block; background:#f43f5e33; color:#f43f5e; padding:1px 7px; border-radius:4px; font-size:0.72rem; margin-left:6px; }
  .entry-badge-clean { display:inline-block; background:#22c55e33; color:#22c55e; padding:1px 7px; border-radius:4px; font-size:0.72rem; margin-left:6px; }
  .entry-summary { margin-top:3px; font-size:0.85rem; }
  .chart { display:flex; align-items:flex-end; gap:3px; height:100px; margin-top:14px; }
  .chart-bar { flex:1; border-radius:3px 3px 0 0; min-width:16px; position:relative; }
  .chart-bar:hover { opacity:0.8; }
  .chart-bar .tip { display:none; position:absolute; bottom:100%; left:50%; transform:translateX(-50%); background:#334155; padding:3px 7px; border-radius:4px; font-size:0.65rem; white-space:nowrap; z-index:10; }
  .chart-bar:hover .tip { display:block; }
  .chart-labels { display:flex; gap:3px; margin-top:3px; }
  .chart-labels span { flex:1; text-align:center; font-size:0.6rem; color:#64748b; min-width:16px; }
  .modal { display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.8); z-index:100; overflow-y:auto; }
  .modal-inner { max-width:800px; margin:40px auto; background:#1e293b; border-radius:12px; padding:28px; }
  .modal-close { float:right; background:none; border:none; color:#94a3b8; font-size:1.5rem; cursor:pointer; }
  .modal-body { font-size:0.88rem; line-height:1.7; }
  .modal-body h1 { font-size:1.4rem; color:#38bdf8; margin:18px 0 10px; border-bottom:1px solid #334155; padding-bottom:6px; }
  .modal-body h2 { font-size:1.15rem; color:#7dd3fc; margin:16px 0 8px; }
  .modal-body h3 { font-size:1rem; color:#94a3b8; margin:12px 0 6px; }
  .modal-body p { margin:6px 0; }
  .modal-body ul, .modal-body ol { margin:6px 0 6px 20px; }
  .modal-body li { margin:3px 0; }
  .modal-body code { background:#334155; padding:1px 5px; border-radius:3px; font-size:0.82rem; }
  .modal-body pre { background:#0f172a; padding:12px; border-radius:6px; overflow-x:auto; margin:8px 0; }
  .modal-body pre code { background:none; padding:0; }
  .modal-body strong { color:#f8fafc; }
  .modal-body blockquote { border-left:3px solid #38bdf8; padding-left:12px; color:#94a3b8; margin:8px 0; }
  .modal-body table { border-collapse:collapse; margin:8px 0; width:100%; }
  .modal-body th, .modal-body td { border:1px solid #334155; padding:6px 10px; text-align:left; font-size:0.82rem; }
  .modal-body th { background:#334155; color:#e2e8f0; }
  .modal-body hr { border:none; border-top:1px solid #334155; margin:12px 0; }
  .tabs { display:flex; gap:6px; margin-bottom:22px; flex-wrap:wrap; }
  .tab { padding:7px 18px; border-radius:8px; background:#334155; border:none; color:#94a3b8; cursor:pointer; font-size:0.85rem; }
  .tab.active { background:#38bdf8; color:#0f172a; font-weight:bold; }
  .empty { text-align:center; padding:36px; color:#64748b; font-size:0.9rem; }
  /* Burning alert */
  .alert { background:#7f1d1d; border:1px solid #f43f5e; border-radius:12px; padding:14px 18px; margin-bottom:20px; }
  .alert-title { color:#fecaca; font-weight:bold; margin-bottom:6px; }
  .alert-item { font-size:0.85rem; color:#fecaca; margin:3px 0; }
  /* Heatmap */
  .heatmap { display:grid; gap:2px; }
  .heatmap-row { display:grid; gap:2px; align-items:center; }
  .heatmap-label { font-size:0.72rem; color:#94a3b8; padding-right:8px; text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .heatmap-cell { height:22px; border-radius:3px; position:relative; cursor:pointer; }
  .heatmap-cell:hover::after { content:attr(data-tip); position:absolute; bottom:100%; left:50%; transform:translateX(-50%); background:#334155; padding:3px 7px; border-radius:4px; font-size:0.7rem; white-space:nowrap; z-index:10; }
  .heatmap-week-labels { display:grid; gap:2px; margin-top:4px; font-size:0.6rem; color:#64748b; }
  /* Kanban */
  .kanban { display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:14px; }
  @media(max-width:768px) { .kanban { grid-template-columns:1fr; } }
  .kanban-col { background:#0f172a; border-radius:8px; padding:12px; border:1px solid #334155; }
  .kanban-col h3 { font-size:0.9rem; margin-bottom:10px; }
  .kanban-card { background:#1e293b; border-radius:6px; padding:10px; margin-bottom:8px; border-left:3px solid #38bdf8; }
  .kanban-card.success { border-left-color:#22c55e; }
  .kanban-card.fail { border-left-color:#f43f5e; }
  .kanban-card.continue { border-left-color:#f59e0b; }
  .kanban-title { font-size:0.85rem; font-weight:bold; margin-bottom:4px; }
  .kanban-meta { font-size:0.7rem; color:#64748b; }
  .kanban-field { font-size:0.75rem; margin-top:4px; color:#cbd5e1; }
  /* Scatter */
  .scatter { position:relative; height:240px; border-left:1px solid #334155; border-bottom:1px solid #334155; margin:20px 30px 30px 30px; }
  .scatter-dot { position:absolute; width:8px; height:8px; border-radius:50%; background:#38bdf8; opacity:0.7; transform:translate(-50%,50%); cursor:pointer; }
  .scatter-dot:hover { opacity:1; width:10px; height:10px; }
  .scatter-dot:hover::after { content:attr(data-tip); position:absolute; bottom:100%; left:50%; transform:translateX(-50%); background:#334155; padding:3px 7px; border-radius:4px; font-size:0.68rem; white-space:nowrap; z-index:10; }
  .scatter-xlabel, .scatter-ylabel { position:absolute; font-size:0.7rem; color:#64748b; }
  .scatter-xlabel { bottom:-22px; left:50%; transform:translateX(-50%); }
  .scatter-ylabel { top:50%; left:-28px; transform:rotate(-90deg); transform-origin:left top; }
  /* Try timeline */
  .try-row { display:flex; align-items:center; margin-bottom:6px; font-size:0.8rem; }
  .try-id { width:50px; color:#64748b; }
  .try-title { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .try-week { width:80px; color:#64748b; font-size:0.7rem; }
  .try-status { width:80px; text-align:center; font-size:0.7rem; padding:2px 0; border-radius:3px; }
  .try-status.done { background:#22c55e33; color:#22c55e; }
  .try-status.pending { background:#64748b33; color:#94a3b8; }
</style>
</head>
<body>
<div class="container">
  <h1>Claude Code Self-Improvement Dashboard</h1>
  <div class="subtitle">AIが自分自身の仕事を振り返り、自動で改善するシステム</div>
  <div class="tabs">
    <button class="tab active" onclick="showTab('overview',this)">Overview</button>
    <button class="tab" onclick="showTab('heatmaps',this)">Heatmaps</button>
    <button class="tab" onclick="showTab('experiments',this)">Experiments</button>
    <button class="tab" onclick="showTab('tries',this)">Tries</button>
    <button class="tab" onclick="showTab('costs',this)">Costs</button>
    <button class="tab" onclick="showTab('reviews',this)">Self-Reviews</button>
    <button class="tab" onclick="showTab('kpts',this)">KPT Archive</button>
  </div>

  <div id="overview">
    <div id="burning-alert"></div>
    <div class="stats-grid" id="stats"></div>
    <div class="two-col">
      <div class="section"><h2>Issue Categories</h2><div id="categories"></div></div>
      <div class="section"><h2>Suggested Action Types</h2><div id="actions"></div></div>
    </div>
    <div class="two-col">
      <div class="section"><h2>Project Issue Distribution</h2><div id="project-issues"></div></div>
      <div class="section"><h2>Session Length × Issues</h2><div class="scatter" id="scatter"><span class="scatter-xlabel">Interactions →</span><span class="scatter-ylabel">Issues →</span></div></div>
    </div>
    <div class="section"><h2>Daily Activity (last 30 days)</h2><div class="chart" id="chart"></div><div class="chart-labels" id="chart-labels"></div></div>
  </div>

  <div id="heatmaps" style="display:none">
    <div class="section">
      <h2>Issue Categories × Week (last 12 weeks)</h2>
      <div id="cat-heatmap"></div>
    </div>
    <div class="section">
      <h2>Activity Heatmap (Weekday × Hour, local TZ)</h2>
      <div id="time-heatmap"></div>
    </div>
  </div>

  <div id="experiments" style="display:none">
    <div class="section">
      <h2>Experiment Board</h2>
      <div class="subtitle" style="margin-bottom:16px;">`/forward-kpt` で設定した実験の進捗。成功したものは次回KPTでTry昇格。</div>
      <div class="kanban" id="kanban"></div>
    </div>
  </div>

  <div id="tries" style="display:none">
    <div class="section">
      <h2>Try Lifetime Timeline</h2>
      <div class="subtitle" style="margin-bottom:16px;">KPTで設定された Try が実装済みか追跡。実装ラグを検出。</div>
      <div id="try-list"></div>
    </div>
  </div>

  <div id="costs" style="display:none">
    <div class="section">
      <h2>Haiku Cost Tracking</h2>
      <div class="subtitle" style="margin-bottom:16px;">SessionEnd hook が Haiku を呼び出した実測コスト（Anthropic API 課金プランのみ）。Pro/Max 定額プランではローカル計測値であり実課金ではない。</div>
      <div class="stats-grid" id="cost-totals"></div>
    </div>
    <div class="section">
      <h2>Monthly Breakdown</h2>
      <div id="cost-monthly"></div>
    </div>
    <div class="section">
      <h2>Recent Sessions (last 50)</h2>
      <div id="cost-recent"></div>
    </div>
  </div>

  <div id="reviews" style="display:none">
    <div class="section"><h2>Session Self-Reviews</h2><div id="review-list"></div></div>
  </div>
  <div id="kpts" style="display:none">
    <div class="section"><h2>KPT Archive</h2><div id="kpt-list"></div></div>
  </div>
</div>
<div class="modal" id="modal" onclick="if(event.target===this)this.style.display='none'">
  <div class="modal-inner">
    <button class="modal-close" onclick="document.getElementById('modal').style.display='none'">&times;</button>
    <div class="modal-body" id="modal-body"></div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
let D;
async function load(){D=await(await fetch('/api/data')).json();render();}
function showTab(n,el){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  ['overview','heatmaps','experiments','tries','costs','reviews','kpts'].forEach(id=>{document.getElementById(id).style.display=id===n?'block':'none';});
}
function showModal(c){document.getElementById('modal-body').innerHTML=marked.parse(c);document.getElementById('modal').style.display='block';}
function heatColor(v,mx){if(!mx||!v)return'#1e293b';const r=v/mx;const h=220-(r*220);return`hsl(${h},70%,${35+r*20}%)`;}
function E(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function render(){
  if(!D)return;
  window.__contents={reviews:D.reviews.map(r=>r.content||''),kpts:D.kpts.map(k=>k.content||''),experiments:D.experiments.map(e=>e.content||'')};

  // Burning alert
  const ba=document.getElementById('burning-alert');
  if(D.burning_categories && D.burning_categories.length){
    ba.innerHTML=`<div class="alert"><div class="alert-title">🔥 燃えてるカテゴリ（直近7日で急増）</div>${D.burning_categories.map(b=>`<div class="alert-item">• <strong>${E(b.category)}</strong>: ${b.recent}件（過去平均: ${b.past_weekly_avg}/週${b.multiplier?' × '+b.multiplier+'倍':''}）</div>`).join('')}</div>`;
  } else ba.innerHTML='';

  const pCount=Object.keys(D.activity.projects||{}).length;
  const activeExp=D.experiments.filter(e=>e.status==='in_progress').length;
  document.getElementById('stats').innerHTML=`
    <div class="stat-card"><div class="stat-value">${D.total_reviews}</div><div class="stat-label">Sessions Analyzed</div></div>
    <div class="stat-card"><div class="stat-value">${D.clean_rate}%</div><div class="stat-label">Clean Rate</div></div>
    <div class="stat-card"><div class="stat-value">${pCount}</div><div class="stat-label">Projects</div></div>
    <div class="stat-card"><div class="stat-value">${D.kpts.length}</div><div class="stat-label">KPT Reports</div></div>
    <div class="stat-card"><div class="stat-value">${activeExp}</div><div class="stat-label">Active Experiments</div></div>
    <div class="stat-card"><div class="stat-value">${D.tries.filter(t=>t.implemented).length}/${D.tries.length}</div><div class="stat-label">Try Implementation</div></div>`;

  // Categories
  const cats=document.getElementById('categories');
  if(!D.top_categories.length){cats.innerHTML='<div class="empty">No issues yet</div>';}
  else{const mx=D.top_categories[0][1];cats.innerHTML=D.top_categories.map(([l,c])=>`<div class="bar-row"><span class="label">${E(l)}</span><div class="bar bar-issue" style="width:${(c/mx)*180}px">${c}</div></div>`).join('');}

  // Actions
  const acts=document.getElementById('actions');
  const actEntries=Object.entries(D.action_types).sort((a,b)=>b[1]-a[1]);
  if(!actEntries.length){acts.innerHTML='<div class="empty">No actions yet</div>';}
  else{const mx=actEntries[0][1];acts.innerHTML=actEntries.map(([l,c])=>`<div class="bar-row"><span class="label">${E(l)}</span><div class="bar bar-action" style="width:${(c/mx)*180}px">${c}</div></div>`).join('');}

  // Project issues
  const pi=document.getElementById('project-issues');
  if(!D.project_issues.length){pi.innerHTML='<div class="empty">No data</div>';}
  else{const mx=D.project_issues[0][1]||1;pi.innerHTML=D.project_issues.map(([p,c])=>`<div class="bar-row"><span class="label">${E(p)}</span><div class="bar bar-project" style="width:${(c/mx)*180}px">${c}</div></div>`).join('');}

  // Scatter
  const sc=document.getElementById('scatter');
  const dots=D.quality_scatter||[];
  if(!dots.length){sc.innerHTML+='<div class="empty">No data</div>';}
  else{
    const maxX=Math.max(...dots.map(d=>d.size),1);
    const maxY=Math.max(...dots.map(d=>d.issues),1);
    sc.innerHTML+=dots.map(d=>{
      const x=(d.size/maxX)*95;
      const y=(d.issues/maxY)*90;
      return`<div class="scatter-dot" style="left:${x}%;bottom:${y}%" data-tip="${E(d.date)} ${E(d.project)}: ${d.size} interactions, ${d.issues} issues"></div>`;
    }).join('');
  }

  // Chart
  const daily=D.activity.daily||{};const dates=Object.keys(daily).sort().slice(-30);
  const mx2=Math.max(...dates.map(d=>daily[d].interactions),1);
  document.getElementById('chart').innerHTML=dates.map(d=>{const s=daily[d];const h=(s.interactions/mx2)*100;
    return`<div class="chart-bar" style="height:${h}%;background:#38bdf8"><span class="tip">${d}: ${s.interactions} interactions, ${s.project_count} projects</span></div>`;}).join('');
  document.getElementById('chart-labels').innerHTML=dates.map(d=>`<span>${d.slice(5)}</span>`).join('');

  // Category heatmap
  const chm=document.getElementById('cat-heatmap');
  const heatmap=D.category_heatmap;
  if(!heatmap.rows.length){chm.innerHTML='<div class="empty">No data</div>';}
  else{
    const nw=heatmap.weeks.length;
    const cols=`120px repeat(${nw},1fr)`;
    let mxH=0;heatmap.rows.forEach(r=>r.values.forEach(v=>{if(v>mxH)mxH=v;}));
    let html=`<div class="heatmap">`;
    heatmap.rows.forEach(row=>{
      html+=`<div class="heatmap-row" style="grid-template-columns:${cols}"><div class="heatmap-label">${E(row.category)}</div>`;
      row.values.forEach((v,i)=>{
        html+=`<div class="heatmap-cell" style="background:${heatColor(v,mxH)}" data-tip="${E(row.category)} @ ${E(heatmap.weeks[i])}: ${v}件"></div>`;
      });
      html+=`</div>`;
    });
    html+=`<div class="heatmap-week-labels" style="grid-template-columns:${cols}"><div></div>`;
    heatmap.weeks.forEach(w=>{html+=`<div style="text-align:center">${E(w.slice(-3))}</div>`;});
    html+=`</div></div>`;
    chm.innerHTML=html;
  }

  // Time heatmap (weekday × hour)
  const thm=document.getElementById('time-heatmap');
  const hw=D.hour_weekday;
  const weekdays=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  let mxT=0;hw.forEach(r=>r.forEach(v=>{if(v>mxT)mxT=v;}));
  if(!mxT){thm.innerHTML='<div class="empty">No data</div>';}
  else{
    const cols=`60px repeat(24,1fr)`;
    let html=`<div class="heatmap">`;
    hw.forEach((row,d)=>{
      html+=`<div class="heatmap-row" style="grid-template-columns:${cols}"><div class="heatmap-label">${weekdays[d]}</div>`;
      row.forEach((v,h)=>{
        html+=`<div class="heatmap-cell" style="background:${heatColor(v,mxT)}" data-tip="${weekdays[d]} ${h}時: ${v}件"></div>`;
      });
      html+=`</div>`;
    });
    html+=`<div class="heatmap-week-labels" style="grid-template-columns:${cols}"><div></div>`;
    for(let h=0;h<24;h++){html+=`<div style="text-align:center">${h%3===0?h:''}</div>`;}
    html+=`</div></div>`;
    thm.innerHTML=html;
  }

  // Experiment Kanban
  const kb=document.getElementById('kanban');
  if(!D.experiments.length){kb.innerHTML='<div class="empty" style="grid-column:1/-1">No experiments. Run `/forward-kpt` to set one.</div>';}
  else{
    const cols={in_progress:[],success:[],fail:[],continue:[]};
    D.experiments.forEach((e,i)=>{e.__idx=i;(cols[e.status]||cols.in_progress).push(e);});
    const renderCard=e=>`<div class="kanban-card ${E(e.status)}" onclick="showModal(window.__contents.experiments[${e.__idx}])">
      <div class="kanban-title">${E(e.id)}: ${E(e.title)}</div>
      <div class="kanban-meta">${E(e.week)} · ${E(e.scope||'')}</div>
      ${e.hypothesis?`<div class="kanban-field">💡 ${E(e.hypothesis)}</div>`:''}
      ${e.success_criteria?`<div class="kanban-field">🎯 ${E(e.success_criteria)}</div>`:''}
    </div>`;
    kb.innerHTML=`
      <div class="kanban-col"><h3 style="color:#38bdf8">🧪 In Progress (${cols.in_progress.length})</h3>${cols.in_progress.map(renderCard).join('')||'<div class="empty" style="padding:10px">—</div>'}</div>
      <div class="kanban-col"><h3 style="color:#22c55e">✅ Success (${cols.success.length})</h3>${cols.success.map(renderCard).join('')||'<div class="empty" style="padding:10px">—</div>'}</div>
      <div class="kanban-col"><h3 style="color:#f59e0b">🔄 Continue (${cols.continue.length})</h3>${cols.continue.map(renderCard).join('')||'<div class="empty" style="padding:10px">—</div>'}</div>
      <div class="kanban-col"><h3 style="color:#f43f5e">❌ Fail (${cols.fail.length})</h3>${cols.fail.map(renderCard).join('')||'<div class="empty" style="padding:10px">—</div>'}</div>`;
  }

  // Try timeline
  const tl=document.getElementById('try-list');
  if(!D.tries.length){tl.innerHTML='<div class="empty">No tries yet. Run `/weekly-kpt` to generate KPT.</div>';}
  else{
    tl.innerHTML=D.tries.slice().reverse().map(t=>`<div class="try-row">
      <span class="try-id">${E(t.id)}</span>
      <span class="try-title">${E(t.title)}</span>
      <span class="try-week">${E(t.week)}</span>
      <span class="try-status ${t.implemented?'done':'pending'}">${t.implemented?'✅ '+E(t.impl_date):'pending'}</span>
    </div>`).join('');
  }

  // Costs
  const c=D.costs||{totals:{},monthly:[],recent:[]};
  const fmtNum=n=>(n||0).toLocaleString();
  const fmtUsd=n=>'$'+(n||0).toFixed(4);
  document.getElementById('cost-totals').innerHTML=`
    <div class="stat-card"><div class="stat-value">${fmtUsd(c.totals.cost_usd)}</div><div class="stat-label">Total Cost</div></div>
    <div class="stat-card"><div class="stat-value">${fmtNum(c.totals.sessions)}</div><div class="stat-label">Hook Invocations</div></div>
    <div class="stat-card"><div class="stat-value">${fmtNum(c.totals.input_tokens)}</div><div class="stat-label">Input Tokens</div></div>
    <div class="stat-card"><div class="stat-value">${fmtNum(c.totals.output_tokens)}</div><div class="stat-label">Output Tokens</div></div>
    <div class="stat-card"><div class="stat-value">${fmtNum(c.totals.cache_read_input_tokens)}</div><div class="stat-label">Cache Read</div></div>
    <div class="stat-card"><div class="stat-value">${fmtNum(c.totals.cache_creation_input_tokens)}</div><div class="stat-label">Cache Creation</div></div>`;
  const cm=document.getElementById('cost-monthly');
  if(!c.monthly.length){cm.innerHTML='<div class="empty">No cost data yet. SessionEnd hook が初回 Haiku 呼び出し以降に蓄積される。</div>';}
  else{
    cm.innerHTML=`<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:0.85rem">
      <thead><tr style="color:#94a3b8;text-align:left;border-bottom:1px solid #334155">
        <th style="padding:8px 6px">Month</th><th style="padding:8px 6px">Sessions</th>
        <th style="padding:8px 6px">Input</th><th style="padding:8px 6px">Output</th>
        <th style="padding:8px 6px">Cache R/W</th><th style="padding:8px 6px">Cost</th>
      </tr></thead><tbody>${c.monthly.map(m=>`<tr style="border-bottom:1px solid #334155">
        <td style="padding:8px 6px"><strong>${E(m.month)}</strong></td>
        <td style="padding:8px 6px">${fmtNum(m.sessions)}</td>
        <td style="padding:8px 6px">${fmtNum(m.input_tokens)}</td>
        <td style="padding:8px 6px">${fmtNum(m.output_tokens)}</td>
        <td style="padding:8px 6px">${fmtNum(m.cache_read_input_tokens)} / ${fmtNum(m.cache_creation_input_tokens)}</td>
        <td style="padding:8px 6px;color:#38bdf8">${fmtUsd(m.cost_usd)}</td>
      </tr>`).join('')}</tbody></table></div>`;
  }
  const cr=document.getElementById('cost-recent');
  if(!c.recent.length){cr.innerHTML='<div class="empty">No sessions logged yet.</div>';}
  else{
    cr.innerHTML=c.recent.map(s=>`<div class="entry">
      <span class="entry-date">${E((s.timestamp||'').replace('T',' ').replace('Z',''))}</span>
      <span class="entry-project">${E(s.project||'unknown')}</span>
      <div class="entry-summary">in ${fmtNum(s.input_tokens)} / out ${fmtNum(s.output_tokens)} / cache ${fmtNum(s.cache_read_input_tokens)}+${fmtNum(s.cache_creation_input_tokens)} · ${fmtUsd(s.cost_usd)} · ${s.duration_ms||0}ms</div>
    </div>`).join('');
  }

  // Reviews
  const rl=document.getElementById('review-list');
  if(!D.reviews.length){rl.innerHTML='<div class="empty">No self-reviews yet. Complete a session to generate one.</div>';}
  else{rl.innerHTML=D.reviews.slice().reverse().map((r,i)=>{
    const idx=D.reviews.length-1-i;
    if(r.error)return`<div class="entry">${E(r.file)}: ${E(r.error)}</div>`;
    const badge=r.issue_count>0?`<span class="entry-badge-issue">${r.issue_count} issues</span>`:`<span class="entry-badge-clean">clean</span>`;
    return`<div class="entry" onclick="showModal(window.__contents.reviews[${idx}])">
      <span class="entry-date">${E(r.date)} ${E(r.time.replace(/(\\d{2})(\\d{2})(\\d{2})/,"$1:$2:$3"))}</span>
      <span class="entry-project">${E(r.project)}</span>${badge}
      <div class="entry-summary">${E(r.summary)}</div></div>`;}).join('');}

  // KPTs
  const kl=document.getElementById('kpt-list');
  if(!D.kpts.length){kl.innerHTML='<div class="empty">No KPT reports yet. Run /weekly-kpt to generate one.</div>';}
  else{kl.innerHTML=D.kpts.slice().reverse().map((k,i)=>{
    const idx=D.kpts.length-1-i;
    return`<div class="entry" onclick="showModal(window.__contents.kpts[${idx}])"><span class="entry-date">${E(k.file)}</span></div>`;}).join('');}
}
load();
</script>
</body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/data":
            d = get_dashboard_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(d, ensure_ascii=False, default=str).encode())
        elif self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    for d in (ACTIVITY_DIR, REVIEWS_DIR, KPT_DIR, EXPERIMENTS_DIR):
        os.makedirs(d, exist_ok=True)
    import webbrowser
    print(f"Dashboard: http://localhost:{PORT}")
    print(f"Data dir: {KPT_DATA}")
    webbrowser.open(f"http://localhost:{PORT}")
    try:
        http.server.HTTPServer(("", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
