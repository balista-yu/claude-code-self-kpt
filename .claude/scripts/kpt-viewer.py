#!/usr/bin/env python3
"""
Claude Code Self-Improvement KPT Dashboard
アクティビティログ + セッション自己分析 + KPT結果を可視化

Usage: python3 ~/.claude/scripts/kpt-viewer.py
"""

import http.server
import json
import os
import re
import glob
from pathlib import Path

PORT = 8765
HOME = str(Path.home())
KPT_DATA = os.path.join(HOME, ".claude", "kpt-data")
ACTIVITY_DIR = os.path.join(KPT_DATA, "activity-logs")
REVIEWS_DIR = os.path.join(KPT_DATA, "session-reviews")
KPT_DIR = os.path.join(KPT_DATA, "kpt")


def load_activity_stats():
    """アクティビティログからプロジェクト別・日別の活動量を集計"""
    stats = {"daily": {}, "projects": {}}
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

                    if date not in stats["daily"]:
                        stats["daily"][date] = {"interactions": 0, "projects": set()}
                    stats["daily"][date]["interactions"] += 1
                    stats["daily"][date]["projects"].add(project)

                    if project not in stats["projects"]:
                        stats["projects"][project] = {"interactions": 0, "days": set()}
                    stats["projects"][project]["interactions"] += 1
                    stats["projects"][project]["days"].add(date)
        except Exception:
            continue

    # setをlistに変換（JSON化のため）
    for d in stats["daily"].values():
        d["projects"] = list(d["projects"])
        d["project_count"] = len(d["projects"])
    for p in stats["projects"].values():
        p["days"] = len(p["days"])

    return stats


def parse_review(filepath):
    """セッション自己分析ファイルをパース"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(filepath)
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{6})", filename)
        date = date_match.group(1) if date_match else "unknown"
        time_str = date_match.group(2) if date_match else "000000"

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
                # カテゴリ付き指摘を抽出
                category_issues = re.findall(
                    r"\*\*\[([^\]]+)\]\*\*\s*(.+)", text
                )
                for cat, desc in category_issues:
                    issues.append({"category": cat.strip(), "description": desc.strip()})
                # カテゴリなし指摘
                if not category_issues:
                    lines = [l.strip("- ").strip() for l in text.split("\n")
                             if l.strip().startswith("-")]
                    for l in lines:
                        if l and "指摘なし" not in l:
                            issues.append({"category": "その他", "description": l})

        # 改善アクション抽出
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
            "project": project,
            "summary": summary[:120],
            "issue_count": len(issues),
            "issues": issues,
            "actions": actions,
            "content": content,
        }
    except Exception as e:
        return {"file": os.path.basename(filepath), "error": str(e)}


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

    # 指摘カテゴリ集計
    category_freq = {}
    for r in reviews:
        if "error" in r:
            continue
        for issue in r.get("issues", []):
            cat = issue.get("category", "その他")
            category_freq[cat] = category_freq.get(cat, 0) + 1
    top_categories = sorted(category_freq.items(), key=lambda x: -x[1])[:10]

    # 改善アクション種別集計
    action_types = {}
    for r in reviews:
        if "error" in r:
            continue
        for action in r.get("actions", []):
            kind = action.get("kind", "other")
            action_types[kind] = action_types.get(kind, 0) + 1

    total_reviews = len([r for r in reviews if "error" not in r])
    clean_reviews = len([r for r in reviews if "error" not in r and r.get("issue_count", 0) == 0])

    return {
        "activity": activity,
        "reviews": reviews,
        "kpts": kpts,
        "top_categories": top_categories,
        "action_types": action_types,
        "total_reviews": total_reviews,
        "clean_rate": round(clean_reviews / total_reviews * 100, 1) if total_reviews else 0,
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
  .tabs { display:flex; gap:6px; margin-bottom:22px; }
  .tab { padding:7px 18px; border-radius:8px; background:#334155; border:none; color:#94a3b8; cursor:pointer; font-size:0.85rem; }
  .tab.active { background:#38bdf8; color:#0f172a; font-weight:bold; }
  .empty { text-align:center; padding:36px; color:#64748b; font-size:0.9rem; }
</style>
</head>
<body>
<div class="container">
  <h1>Claude Code Self-Improvement Dashboard</h1>
  <div class="subtitle">AIが自分自身の仕事を振り返り、自動で改善するシステム</div>
  <div class="tabs">
    <button class="tab active" onclick="showTab('overview',this)">Overview</button>
    <button class="tab" onclick="showTab('reviews',this)">Self-Reviews</button>
    <button class="tab" onclick="showTab('kpts',this)">KPT Archive</button>
  </div>
  <div id="overview">
    <div class="stats-grid" id="stats"></div>
    <div class="two-col">
      <div class="section"><h2>Issue Categories</h2><div id="categories"></div></div>
      <div class="section"><h2>Suggested Action Types</h2><div id="actions"></div></div>
    </div>
    <div class="section"><h2>Daily Activity</h2><div class="chart" id="chart"></div><div class="chart-labels" id="chart-labels"></div></div>
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
  ['overview','reviews','kpts'].forEach(id=>{document.getElementById(id).style.display=id===n?'block':'none';});
}
function showModal(c){document.getElementById('modal-body').innerHTML=marked.parse(c);document.getElementById('modal').style.display='block';}
function render(){
  if(!D)return;
  window.__contents={reviews:D.reviews.map(r=>r.content||''),kpts:D.kpts.map(k=>k.content||'')};
  const pCount=Object.keys(D.activity.projects||{}).length;
  document.getElementById('stats').innerHTML=`
    <div class="stat-card"><div class="stat-value">${D.total_reviews}</div><div class="stat-label">Sessions Analyzed</div></div>
    <div class="stat-card"><div class="stat-value">${D.clean_rate}%</div><div class="stat-label">Clean Rate (no issues)</div></div>
    <div class="stat-card"><div class="stat-value">${pCount}</div><div class="stat-label">Projects</div></div>
    <div class="stat-card"><div class="stat-value">${D.kpts.length}</div><div class="stat-label">KPT Reports</div></div>`;
  // Categories
  const cats=document.getElementById('categories');
  if(!D.top_categories.length){cats.innerHTML='<div class="empty">No issues yet</div>';}
  else{const mx=D.top_categories[0][1];cats.innerHTML=D.top_categories.map(([l,c])=>`<div class="bar-row"><span class="label">${l}</span><div class="bar bar-issue" style="width:${(c/mx)*180}px">${c}</div></div>`).join('');}
  // Actions
  const acts=document.getElementById('actions');
  const actEntries=Object.entries(D.action_types).sort((a,b)=>b[1]-a[1]);
  if(!actEntries.length){acts.innerHTML='<div class="empty">No actions yet</div>';}
  else{const mx=actEntries[0][1];acts.innerHTML=actEntries.map(([l,c])=>`<div class="bar-row"><span class="label">${l}</span><div class="bar bar-action" style="width:${(c/mx)*180}px">${c}</div></div>`).join('');}
  // Chart
  const daily=D.activity.daily||{};const dates=Object.keys(daily).sort().slice(-30);
  const mx2=Math.max(...dates.map(d=>daily[d].interactions),1);
  document.getElementById('chart').innerHTML=dates.map(d=>{const s=daily[d];const h=(s.interactions/mx2)*100;
    return`<div class="chart-bar" style="height:${h}%;background:#38bdf8"><span class="tip">${d}: ${s.interactions} interactions, ${s.project_count} projects</span></div>`;}).join('');
  document.getElementById('chart-labels').innerHTML=dates.map(d=>`<span>${d.slice(5)}</span>`).join('');
  // Reviews
  const rl=document.getElementById('review-list');
  if(!D.reviews.length){rl.innerHTML='<div class="empty">No self-reviews yet. Complete a session to generate one.</div>';}
  else{rl.innerHTML=D.reviews.slice().reverse().map((r,i)=>{
    const idx=D.reviews.length-1-i;
    if(r.error)return`<div class="entry">${r.file}: ${r.error}</div>`;
    const badge=r.issue_count>0?`<span class="entry-badge-issue">${r.issue_count} issues</span>`:`<span class="entry-badge-clean">clean</span>`;
    return`<div class="entry" onclick="showModal(window.__contents.reviews[${idx}])">
      <span class="entry-date">${r.date} ${r.time.replace(/(\\d{2})(\\d{2})(\\d{2})/,"$1:$2:$3")}</span>
      <span class="entry-project">${r.project}</span>${badge}
      <div class="entry-summary">${r.summary}</div></div>`;}).join('');}
  // KPTs
  const kl=document.getElementById('kpt-list');
  if(!D.kpts.length){kl.innerHTML='<div class="empty">No KPT reports yet. Run /weekly-kpt to generate one.</div>';}
  else{kl.innerHTML=D.kpts.slice().reverse().map((k,i)=>{
    const idx=D.kpts.length-1-i;
    return`<div class="entry" onclick="showModal(window.__contents.kpts[${idx}])"><span class="entry-date">${k.file}</span></div>`;}).join('');}
}
load();
</script>
</body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path=="/api/data":
            d=get_dashboard_data()
            self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
            self.wfile.write(json.dumps(d,ensure_ascii=False,default=str).encode())
        elif self.path in ("/","/index.html"):
            self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        else: self.send_error(404)
    def log_message(self,*a): pass

if __name__=="__main__":
    for d in (ACTIVITY_DIR,REVIEWS_DIR,KPT_DIR): os.makedirs(d,exist_ok=True)
    import webbrowser
    print(f"Dashboard: http://localhost:{PORT}")
    print(f"Data dir: {KPT_DATA}")
    webbrowser.open(f"http://localhost:{PORT}")
    try: http.server.HTTPServer(("",PORT),Handler).serve_forever()
    except KeyboardInterrupt: print("\\nStopped.")
