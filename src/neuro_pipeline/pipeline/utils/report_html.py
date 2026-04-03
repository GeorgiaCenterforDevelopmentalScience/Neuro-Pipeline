#!/usr/bin/env python3
"""HTML rendering for the pipeline report (CSS, section builders, render_html)."""

import html as html_module
from datetime import datetime
from typing import Optional

import pandas as pd


def _e(text) -> str:
    """HTML-escape a value."""
    return html_module.escape(str(text) if text is not None else '')


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px; color: #2c2c2c; background: #fff; line-height: 1.55;
}
.container { max-width: 1150px; margin: 0 auto; padding: 28px 36px 60px; }
header { margin-bottom: 28px; }
h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
.subtitle { color: #666; font-size: 13px; margin-bottom: 14px; }
.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 4px 32px;
    font-size: 13px;
}
.meta-item { display: flex; gap: 10px; }
.meta-label { color: #888; min-width: 72px; flex-shrink: 0; }
.meta-val { word-break: break-all; }
h2 {
    font-size: 14px; font-weight: 600;
    margin: 32px 0 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #e4e4e4;
    color: #222;
}
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th {
    background: #f6f6f6; font-weight: 600; padding: 7px 12px;
    text-align: left; border-bottom: 2px solid #ddd; white-space: nowrap;
}
td { padding: 6px 12px; border-bottom: 1px solid #f0f0f0; }
tr:last-child td { border-bottom: none; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.fail { color: #c0392b; font-weight: 500; }
.empty { color: #999; font-style: italic; font-size: 13px; padding: 6px 0; }
details { margin-bottom: 6px; }
details > summary {
    cursor: pointer; padding: 7px 12px;
    background: #f6f6f6; border: 1px solid #e4e4e4;
    border-radius: 3px; font-size: 13px;
    list-style: none; user-select: none;
}
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: '▶ '; font-size: 10px; color: #888; }
details[open] > summary::before { content: '▼ '; }
details > summary:hover { background: #ececec; }
details[open] > summary { margin-bottom: 8px; border-radius: 3px 3px 0 0; }
.details-body { padding: 10px 14px; border: 1px solid #e4e4e4;
                border-top: none; border-radius: 0 0 3px 3px; }
pre {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
    font-size: 11px; background: #f8f8f8; border: 1px solid #e8e8e8;
    padding: 10px 14px; overflow-x: auto; white-space: pre-wrap;
    word-break: break-all; line-height: 1.45; margin-top: 6px;
}
.heatmap-img { max-width: 100%; height: auto; display: block; }
.appendix { margin-top: 40px; }
.appendix > summary {
    background: #f0f0f0; font-size: 12px; color: #666; font-style: italic;
}
"""


def _section_task_summary(summary: list) -> str:
    if not summary:
        return '<p class="empty">No task data found.</p>'

    rows = []
    for r in summary:
        fail_cell = (f'<td class="num fail">{r["failed"]}</td>'
                     if r['failed'] > 0
                     else f'<td class="num">{r["failed"]}</td>')
        pct = f'{r["ok"] / r["total"] * 100:.0f}%' if r['total'] > 0 else '—'
        rows.append(
            f'<tr>'
            f'<td>{_e(r["task"])}</td>'
            f'<td class="num">{r["ok"]} / {r["total"]}</td>'
            f'<td class="num">{pct}</td>'
            f'{fail_cell}'
            f'<td class="num">{r["not_run"]}</td>'
            f'<td>{_e(r["dur"])}</td>'
            f'<td>{_e(r["last"])}</td>'
            f'</tr>'
        )
    return (
        '<table>'
        '<thead><tr>'
        '<th>Task</th><th class="num">Completed</th><th class="num">%</th>'
        '<th class="num">Failed</th><th class="num">Not Run</th>'
        '<th>Avg Duration</th><th>Last Run</th>'
        '</tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody>'
        '</table>'
    )


def _section_failed_jobs(failed_jobs: list) -> str:
    if not failed_jobs:
        return '<p class="empty">No failed jobs.</p>'

    by_task: dict = {}
    for j in failed_jobs:
        by_task.setdefault(j['task_name'], []).append(j)

    parts = []
    for task, jobs in sorted(by_task.items()):
        rows = []
        for j in jobs:
            ts = str(j.get('start_time', '') or '')[:16]
            exit_code = j.get('exit_code')

            stdout_raw = j.get('stdout') or ''
            log_html = (
                f'<details><summary style="font-size:11px;color:#888">stdout</summary>'
                f'<pre>{_e(stdout_raw)}</pre></details>'
                if stdout_raw.strip() else '<span style="color:#bbb">—</span>'
            )

            rows.append(
                f'<tr>'
                f'<td>{_e(j["subject"])}</td>'
                f'<td class="num">{_e(exit_code) if exit_code is not None else "—"}</td>'
                f'<td>{_e(ts)}</td>'
                f'<td>{log_html}</td>'
                f'</tr>'
            )
        table = (
            '<table>'
            '<thead><tr><th>Subject</th><th class="num">Exit</th>'
            '<th>Started</th><th>Stdout</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody>'
            '</table>'
        )
        parts.append(
            f'<details>'
            f'<summary>{_e(task)} — {len(jobs)} failed</summary>'
            f'<div class="details-body">{table}</div>'
            f'</details>'
        )
    return '\n'.join(parts)


def _section_check_results(
    check_df: Optional[pd.DataFrame],
    check_heatmap_b64: Optional[str] = None,
) -> str:
    if check_df is None or check_df.empty:
        return '<p class="empty">No check-results data provided (use --check-results).</p>'

    heatmap_html = (
        f'<img class="heatmap-img" style="margin-bottom:16px" '
        f'src="data:image/png;base64,{check_heatmap_b64}" '
        f'alt="Output validation status matrix">'
        if check_heatmap_b64 else ''
    )

    rows = []
    for _, r in check_df.iterrows():
        status = str(r.get('status', ''))
        is_fail = status.upper().startswith('FAIL')
        status_cell = (f'<td class="fail">{_e(status)}</td>'
                       if is_fail else f'<td>{_e(status)}</td>')
        rows.append(
            f'<tr>'
            f'<td>{_e(r.get("task", ""))}</td>'
            f'<td>{_e(r.get("subject", ""))}</td>'
            f'<td>{_e(r.get("session", ""))}</td>'
            f'<td>{_e(r.get("check_type", ""))}</td>'
            f'<td style="font-size:12px;font-family:monospace">{_e(r.get("pattern", ""))}</td>'
            f'<td class="num">{_e(r.get("actual", ""))}</td>'
            f'{status_cell}'
            f'</tr>'
        )
    table = (
        '<table>'
        '<thead><tr>'
        '<th>Task</th><th>Subject</th><th>Session</th>'
        '<th>Check Type</th><th>Pattern</th><th class="num">Actual</th><th>Status</th>'
        '</tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody>'
        '</table>'
    )

    n_fail = sum(1 for _, r in check_df.iterrows()
                 if str(r.get('status', '')).upper().startswith('FAIL'))
    summary = f'{len(check_df)} checks — {n_fail} failed'

    return (
        f'{heatmap_html}'
        f'<details>'
        f'<summary>Detail table &nbsp;<span style="color:#888;font-size:12px">({summary})</span></summary>'
        f'<div class="details-body">{table}</div>'
        f'</details>'
    )


def _section_environment(wrapper_scripts: list) -> str:
    if not wrapper_scripts:
        return '<p class="empty">No wrapper script records found.</p>'

    parts = []
    for w in wrapper_scripts:
        fields = [
            ('SLURM command',    w.get('slurm_cmd')),
            ('Modules',          w.get('env_modules')),
            ('Global Python',    w.get('global_python')),
            ('Environment vars', w.get('global_env_vars')),
            ('Execute command',  w.get('execute_cmd')),
        ]
        inner = []
        for label, val in fields:
            if val and str(val).strip():
                inner.append(
                    f'<p style="font-size:12px;color:#666;margin:8px 0 2px">'
                    f'<strong>{_e(label)}</strong></p>'
                    f'<pre>{_e(val)}</pre>'
                )
        if not inner:
            continue
        ts = str(w.get('submission_time', '') or '')[:16]
        parts.append(
            f'<details>'
            f'<summary>{_e(w["task_name"])} &nbsp;'
            f'<span style="color:#aaa;font-size:11px">last submitted {_e(ts)}</span>'
            f'</summary>'
            f'<div class="details-body">{"".join(inner)}</div>'
            f'</details>'
        )
    return '\n'.join(parts) if parts else '<p class="empty">No environment data recorded.</p>'

def render_html(
    metadata: dict,
    task_summary: list,
    heatmap_b64: str,
    history_heatmap_b64: Optional[str],
    failed_jobs: list,
    check_df: Optional[pd.DataFrame],
    check_heatmap_b64: Optional[str],
    wrapper_scripts: list,
    project_name: str,
    session: Optional[str],
) -> str:
    generated = datetime.now().strftime('%Y-%m-%d %H:%M')
    last_exec = str(metadata.get('execution_time', '') or '')[:16]

    subtitle_parts = [f'Project: <strong>{_e(project_name)}</strong>']
    if session:
        subtitle_parts.append(f'Session: <strong>{_e(session)}</strong>')
    subtitle_parts.append(f'Generated: {_e(generated)}')

    meta_items = []
    for label, key in [('Input', 'input_dir'), ('Output', 'output_dir'), ('Work', 'work_dir')]:
        val = metadata.get(key, '')
        if val:
            meta_items.append(
                f'<div class="meta-item">'
                f'<span class="meta-label">{label}</span>'
                f'<span class="meta-val">{_e(val)}</span>'
                f'</div>'
            )
    if last_exec:
        meta_items.append(
            f'<div class="meta-item">'
            f'<span class="meta-label">Last run</span>'
            f'<span class="meta-val">{_e(last_exec)}</span>'
            f'</div>'
        )
    cmd_line = metadata.get('command_line', '')
    if cmd_line:
        meta_items.append(
            f'<div class="meta-item" style="grid-column:1/-1">'
            f'<span class="meta-label">Command</span>'
            f'<span class="meta-val" style="font-family:monospace;font-size:12px">'
            f'{_e(cmd_line)}</span>'
            f'</div>'
        )

    heatmap_tag = (
        f'<img class="heatmap-img" src="data:image/png;base64,{heatmap_b64}" '
        f'alt="Subject × Task status matrix">'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pipeline Report · {_e(project_name)}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="container">

  <header>
    <h1>Pipeline Report</h1>
    <p class="subtitle">{'  &nbsp;|&nbsp;  '.join(subtitle_parts)}</p>
    <div class="meta-grid">{''.join(meta_items)}</div>
  </header>

  <section>
    <h2>Task Completion</h2>
    {_section_task_summary(task_summary)}
  </section>

  <section>
    <h2>Subject × Task Status</h2>
    {heatmap_tag}
    {f'''<details style="margin-top:12px">
      <summary>Run History</summary>
      <div class="details-body">
        <img class="heatmap-img" src="data:image/png;base64,{history_heatmap_b64}"
             alt="Run history matrix">
      </div>
    </details>''' if history_heatmap_b64 else ''}
  </section>

  <section>
    <h2>Failed Jobs</h2>
    {_section_failed_jobs(failed_jobs)}
  </section>

  <section>
    <h2>Output Validation</h2>
    {_section_check_results(check_df, check_heatmap_b64)}
  </section>

  <details class="appendix">
    <summary>Environment &amp; Reproducibility (per task)</summary>
    <div class="details-body">
      {_section_environment(wrapper_scripts)}
    </div>
  </details>

</div>
</body>
</html>"""
