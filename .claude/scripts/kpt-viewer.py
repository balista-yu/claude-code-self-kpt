#!/usr/bin/env python3
"""
KPT Dashboard Viewer (Global Version)
~/.claude/kpt-data/ の作業ログとKPT結果をブラウザで可視化

Usage:
  python3 ~/.claude/scripts/kpt-viewer.py
  # → http://localhost:8765 でダッシュボードが開く
"""

import http.server
import json
import os
import re
import glob
from pathlib import Path

PORT = 8765
KPT_DATA_DIR = os.path.join(str(Path.home()), ".claude", "kpt-data")
WORK_LOGS_DIR = os.path.join(KPT_DATA_DIR, "work-logs")
KPT_DIR = os.path.join(KPT_DATA_DIR, "kpt")


def parse_work_log(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(filepath)
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{6})", filename)
        date = date_match.group(1) if date_match else "unknown"
        time = date_match.group(2) if date_match else "000000"

        # プロジェクト名を抽出
        project_match = re.search(r"プロジェクト:\s*(.+)", content)
        project = project_match.group(1).strip() if project_match else "unknown"

        # ユーザー指摘事項をカウント
        issues_section = re.search(
            r"## ユーザー指摘事項\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        issues = []
        if issues_section:
            lines = issues_section.group(1).strip().split("\n")
            issues = [
                l.strip("- ").strip()
                for l in lines
                if l.strip().startswith("-") and "特になし" not in l
            ]

        summary_match = re.search(r"## 概要\n(.+?)(?=\n## |\Z)", content, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        proposals = len(re.findall(r"### 提案\d+", content))

        return {
            "file": filename,
            "date": date,
            "time": time,
            "project": project,
            "summary": summary[:100],
            "issue_count": len(issues),
            "issues": issues,
            "proposal_count": proposals,
            "content": content,
        }
    except Exception as e:
        return {"file": os.path.basename(filepath), "error": str(e)}


def parse_kpt(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return {"file": os.path.basename(filepath), "content": content}
    except Exception as e:
        return {"file": os.path.basename(filepath), "error": str(e)}


def get_dashboard_data():
    logs = []
    for f in sorted(glob.glob(os.path.join(WORK_LOGS_DIR, "*.md"))):
        logs.append(parse_work_log(f))

    kpts = []
    for f in sorted(glob.glob(os.path.join(KPT_DIR, "*.md"))):
        kpts.append(parse_kpt(f))

    # プロジェクト一覧
    projects = sorted(set(
        l.get("project", "unknown") for l in logs if "error" not in l
    ))

    # 日別集計
    daily_stats = {}
    for log in logs:
        if "error" in log:
            continue
        date = log["date"]
        if date not in daily_stats:
            daily_stats[date] = {"sessions": 0, "issues": 0, "no_issue_sessions": 0}
        daily_stats[date]["sessions"] += 1
        daily_stats[date]["issues"] += log["issue_count"]
        if log["issue_count"] == 0:
            daily_stats[date]["no_issue_sessions"] += 1

    # プロジェクト別集計
    project_stats = {}
    for log in logs:
        if "error" in log:
            continue
        p = log.get("project", "unknown")
        if p not in project_stats:
            project_stats[p] = {"sessions": 0, "issues": 0, "no_issue_sessions": 0}
        project_stats[p]["sessions"] += 1
        project_stats[p]["issues"] += log["issue_count"]
        if log["issue_count"] == 0:
            project_stats[p]["no_issue_sessions"] += 1

    # 指摘頻度
    issue_freq = {}
    for log in logs:
        if "error" in log:
            continue
        for issue in log.get("issues", []):
            key = issue[:40] if len(issue) > 40 else issue
            issue_freq[key] = issue_freq.get(key, 0) + 1
    top_issues = sorted(issue_freq.items(), key=lambda x: -x[1])[:10]

    total_sessions = len([l for l in logs if "error" not in l])
    no_issue_sessions = len(
        [l for l in logs if "error" not in l and l.get("issue_count", 0) == 0]
    )

    return {
        "logs": logs,
        "kpts": kpts,
        "projects": projects,
        "daily_stats": daily_stats,
        "project_stats": project_stats,
        "top_issues": top_issues,
        "total_sessions": total_sessions,
        "no_issue_rate": (
            round(no_issue_sessions / total_sessions * 100, 1) if total_sessions else 0
        ),
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code KPT Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }
  .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 1.8rem; margin-bottom: 24px; color: #38bdf8; }
  h2 { font-size: 1.3rem; margin-bottom: 16px; color: #94a3b8; }
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .stat-card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }
  .stat-value { font-size: 2.2rem; font-weight: bold; color: #38bdf8; }
  .stat-label { font-size: 0.9rem; color: #94a3b8; margin-top: 4px; }
  .section { background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #334155; }
  .issue-bar { display: flex; align-items: center; margin-bottom: 8px; }
  .issue-bar .label { flex: 1; font-size: 0.85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .issue-bar .bar { height: 24px; background: #f43f5e; border-radius: 4px; margin-left: 12px; min-width: 30px; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: bold; }
  .log-entry { padding: 12px; border-bottom: 1px solid #334155; cursor: pointer; transition: background 0.2s; }
  .log-entry:hover { background: #334155; }
  .log-date { font-size: 0.8rem; color: #64748b; }
  .log-project { display: inline-block; background: #38bdf833; color: #38bdf8; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; margin-left: 8px; }
  .log-summary { margin-top: 4px; }
  .log-issues { display: inline-block; background: #f43f5e33; color: #f43f5e; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px; }
  .log-no-issues { display: inline-block; background: #22c55e33; color: #22c55e; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px; }
  .chart { display: flex; align-items: flex-end; gap: 4px; height: 120px; margin-top: 16px; }
  .chart-bar { flex: 1; border-radius: 4px 4px 0 0; min-width: 20px; position: relative; transition: background 0.2s; }
  .chart-bar:hover { opacity: 0.8; }
  .chart-bar .tooltip { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: #334155; padding: 4px 8px; border-radius: 4px; font-size: 0.7rem; white-space: nowrap; z-index: 10; }
  .chart-bar:hover .tooltip { display: block; }
  .chart-labels { display: flex; gap: 4px; margin-top: 4px; }
  .chart-labels span { flex: 1; text-align: center; font-size: 0.65rem; color: #64748b; min-width: 20px; }
  .project-card { display: inline-block; background: #334155; border-radius: 8px; padding: 12px 16px; margin: 4px; }
  .project-name { font-weight: bold; color: #38bdf8; }
  .project-detail { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
  .filter-bar { margin-bottom: 16px; }
  .filter-bar select { background: #334155; color: #e2e8f0; border: 1px solid #475569; padding: 6px 12px; border-radius: 6px; font-size: 0.9rem; }
  .modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 100; overflow-y: auto; }
  .modal-content { max-width: 800px; margin: 40px auto; background: #1e293b; border-radius: 12px; padding: 32px; }
  .modal-close { float: right; background: none; border: none; color: #94a3b8; font-size: 1.5rem; cursor: pointer; }
  .modal pre { white-space: pre-wrap; font-size: 0.85rem; line-height: 1.6; }
  .tab-bar { display: flex; gap: 8px; margin-bottom: 24px; }
  .tab { padding: 8px 20px; border-radius: 8px; background: #334155; border: none; color: #94a3b8; cursor: pointer; font-size: 0.9rem; }
  .tab.active { background: #38bdf8; color: #0f172a; font-weight: bold; }
  .empty { text-align: center; padding: 40px; color: #64748b; }
</style>
</head>
<body>
<div class="container">
  <h1>Claude Code KPT Dashboard</h1>
  <div class="tab-bar">
    <button class="tab active" onclick="showTab('overview')">Overview</button>
    <button class="tab" onclick="showTab('projects')">Projects</button>
    <button class="tab" onclick="showTab('logs')">Work Logs</button>
    <button class="tab" onclick="showTab('kpts')">KPT Archive</button>
  </div>

  <div id="overview">
    <div class="stats-grid" id="stats-grid"></div>
    <div class="section">
      <h2>Daily Sessions</h2>
      <div class="chart" id="daily-chart"></div>
      <div class="chart-labels" id="daily-labels"></div>
    </div>
    <div class="section">
      <h2>Top Issues</h2>
      <div id="top-issues"></div>
    </div>
  </div>

  <div id="projects" style="display:none">
    <div class="section">
      <h2>Project Stats</h2>
      <div id="project-list"></div>
    </div>
  </div>

  <div id="logs" style="display:none">
    <div class="section">
      <h2>Session Work Logs</h2>
      <div class="filter-bar">
        <select id="project-filter" onchange="renderLogs()">
          <option value="all">All Projects</option>
        </select>
      </div>
      <div id="log-list"></div>
    </div>
  </div>

  <div id="kpts" style="display:none">
    <div class="section">
      <h2>KPT Archive</h2>
      <div id="kpt-list"></div>
    </div>
  </div>
</div>

<div class="modal" id="modal" onclick="if(event.target===this)this.style.display='none'">
  <div class="modal-content">
    <button class="modal-close" onclick="document.getElementById('modal').style.display='none'">&times;</button>
    <pre id="modal-body"></pre>
  </div>
</div>

<script>
let DATA = null;

async function loadData() {
  const res = await fetch('/api/data');
  DATA = await res.json();
  render();
}

function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  ['overview','projects','logs','kpts'].forEach(id => {
    document.getElementById(id).style.display = id === name ? 'block' : 'none';
  });
}

function showModal(content) {
  document.getElementById('modal-body').textContent = content;
  document.getElementById('modal').style.display = 'block';
}

function renderLogs() {
  const filter = document.getElementById('project-filter').value;
  const logList = document.getElementById('log-list');
  const filtered = DATA.logs.filter(l => {
    if ('error' in l) return true;
    return filter === 'all' || l.project === filter;
  });

  if (filtered.length === 0) {
    logList.innerHTML = '<div class="empty">No work logs found.</div>';
    return;
  }

  logList.innerHTML = filtered.slice().reverse().map(log => {
    if (log.error) return `<div class="log-entry">${log.file}: ${log.error}</div>`;
    const badge = log.issue_count > 0
      ? `<span class="log-issues">${log.issue_count} issues</span>`
      : `<span class="log-no-issues">clean</span>`;
    return `<div class="log-entry" onclick='showModal(${JSON.stringify(JSON.stringify(log.content))})'>
      <span class="log-date">${log.date} ${log.time.replace(/(\\d{2})(\\d{2})(\\d{2})/, '$1:$2:$3')}</span>
      <span class="log-project">${log.project}</span>${badge}
      <div class="log-summary">${log.summary}</div>
    </div>`;
  }).join('');
}

function render() {
  if (!DATA) return;

  // Stats
  const grid = document.getElementById('stats-grid');
  grid.innerHTML = `
    <div class="stat-card"><div class="stat-value">${DATA.total_sessions}</div><div class="stat-label">Total Sessions</div></div>
    <div class="stat-card"><div class="stat-value">${DATA.no_issue_rate}%</div><div class="stat-label">No-Issue Rate</div></div>
    <div class="stat-card"><div class="stat-value">${DATA.projects.length}</div><div class="stat-label">Projects</div></div>
    <div class="stat-card"><div class="stat-value">${DATA.kpts.length}</div><div class="stat-label">KPT Reports</div></div>
  `;

  // Daily chart
  const dates = Object.keys(DATA.daily_stats).sort();
  const maxSessions = Math.max(...dates.map(d => DATA.daily_stats[d].sessions), 1);
  const chart = document.getElementById('daily-chart');
  const labels = document.getElementById('daily-labels');
  chart.innerHTML = dates.map(d => {
    const s = DATA.daily_stats[d];
    const h = (s.sessions / maxSessions) * 100;
    const issueRatio = s.sessions > 0 ? ((s.sessions - s.no_issue_sessions) / s.sessions) * 100 : 0;
    return `<div class="chart-bar" style="height:${h}%;background:linear-gradient(to top, #f43f5e ${issueRatio}%, #38bdf8 ${issueRatio}%)">
      <span class="tooltip">${d}<br>${s.sessions} sessions, ${s.issues} issues</span>
    </div>`;
  }).join('');
  labels.innerHTML = dates.map(d => `<span>${d.slice(5)}</span>`).join('');

  // Top issues
  const issuesDiv = document.getElementById('top-issues');
  if (DATA.top_issues.length === 0) {
    issuesDiv.innerHTML = '<div class="empty">No issues recorded yet</div>';
  } else {
    const maxCount = DATA.top_issues[0][1];
    issuesDiv.innerHTML = DATA.top_issues.map(([label, count]) =>
      `<div class="issue-bar"><span class="label">${label}</span><div class="bar" style="width:${(count/maxCount)*200}px">${count}</div></div>`
    ).join('');
  }

  // Project stats
  const projectList = document.getElementById('project-list');
  projectList.innerHTML = Object.entries(DATA.project_stats).map(([name, s]) => {
    const rate = s.sessions > 0 ? Math.round(s.no_issue_sessions / s.sessions * 100) : 0;
    return `<div class="project-card">
      <div class="project-name">${name}</div>
      <div class="project-detail">${s.sessions} sessions | ${rate}% clean | ${s.issues} issues</div>
    </div>`;
  }).join('');

  // Project filter
  const select = document.getElementById('project-filter');
  select.innerHTML = '<option value="all">All Projects</option>' +
    DATA.projects.map(p => `<option value="${p}">${p}</option>`).join('');

  renderLogs();

  // KPTs
  const kptList = document.getElementById('kpt-list');
  if (DATA.kpts.length === 0) {
    kptList.innerHTML = '<div class="empty">No KPT reports yet. Run /weekly-kpt to generate one.</div>';
  } else {
    kptList.innerHTML = DATA.kpts.slice().reverse().map(kpt =>
      `<div class="log-entry" onclick='showModal(${JSON.stringify(JSON.stringify(kpt.content))})'>
        <span class="log-date">${kpt.file}</span>
      </div>`
    ).join('');
  }
}

loadData();
</script>
</body>
</html>
"""


class KPTHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/data":
            data = get_dashboard_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    os.makedirs(WORK_LOGS_DIR, exist_ok=True)
    os.makedirs(KPT_DIR, exist_ok=True)

    import webbrowser

    print(f"KPT Dashboard: http://localhost:{PORT}")
    print(f"Data: {KPT_DATA_DIR}")
    print("Press Ctrl+C to stop")

    webbrowser.open(f"http://localhost:{PORT}")

    server = http.server.HTTPServer(("", PORT), KPTHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
