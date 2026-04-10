#!/usr/bin/env python3
"""HTML rendering for the pipeline report (CSS, section builders, render_html)."""

import html as html_module
from datetime import datetime
from typing import Optional

import pandas as pd


def _e(text) -> str:
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
/* Status matrix cells */
.cell-ok      { background: #C5E0B3; text-align: center; font-size: 11px; color: #2d6a2d; }
.cell-fail    { background: #F8786E; text-align: center; font-size: 11px; color: #7a1a14; font-weight: 600; }
.cell-notrun  { background: #ebebeb; text-align: center; font-size: 11px; color: #aaa; }
.matrix-wrap  { overflow-x: auto; }
.matrix-wrap table { width: auto; }
.matrix-wrap th, .matrix-wrap td {
    padding: 4px 8px; white-space: nowrap; border: 1px solid #e8e8e8;
}
.matrix-wrap th { background: #f6f6f6; font-size: 11px; }
.run-header td {
    background: #eef2f7; font-size: 11px; color: #555;
    font-style: italic; padding: 3px 8px;
    border-top: 2px solid #bbb;
}
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
.legend { display: flex; gap: 16px; font-size: 12px; color: #555; margin-bottom: 10px; }
.legend-dot { display: inline-block; width: 12px; height: 12px;
              border-radius: 2px; margin-right: 4px; vertical-align: middle; }
.appendix { margin-top: 40px; }
.appendix > summary {
    background: #f0f0f0; font-size: 12px; color: #666; font-style: italic;
}
"""

_LEGEND = (
    '<div class="legend">'
    '<span><span class="legend-dot" style="background:#C5E0B3"></span>OK</span>'
    '<span><span class="legend-dot" style="background:#F8786E"></span>FAIL</span>'
    '<span><span class="legend-dot" style="background:#ebebeb"></span>Not run</span>'
    '</div>'
)


def _cell(status: str) -> str:
    s = (status or '').upper()
    if s == 'SUCCESS':
        return '<td class="cell-ok">OK</td>'
    if s == 'FAILED':
        return '<td class="cell-fail">FAIL</td>'
    return '<td class="cell-notrun">—</td>'


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


def _section_status_matrix(job_status: list, all_subjects: list, all_tasks: list) -> str:
    """Subject × Task status as a colour-coded HTML table."""
    if not all_subjects or not all_tasks:
        return '<p class="empty">No data.</p>'

    def _subj_key(s):
        d = ''.join(filter(str.isdigit, s))
        return int(d) if d else 0

    sorted_subjects = sorted(all_subjects, key=_subj_key)

    # Index: (subject, task_name) -> status
    status_map: dict = {}
    for j in job_status:
        status_map[(j['subject'], j['task_name'])] = j.get('status', '')

    header = '<tr><th>Task</th>' + ''.join(f'<th>{_e(s)}</th>' for s in sorted_subjects) + '</tr>'
    rows = []
    for task in all_tasks:
        cells = ''.join(_cell(status_map.get((subj, task), '')) for subj in sorted_subjects)
        rows.append(f'<tr><td>{_e(task)}</td>{cells}</tr>')

    return (
        _LEGEND +
        '<div class="matrix-wrap">'
        f'<table><thead>{header}</thead><tbody>{"".join(rows)}</tbody></table>'
        '</div>'
    )


def _section_history_matrix(all_runs: list, all_subjects: list, all_tasks: list) -> str:
    """Run history as grouped Subject × Task tables, one block per run."""
    if not all_runs or not all_subjects or not all_tasks:
        return '<p class="empty">Only one run recorded — no history to compare.</p>'

    def _subj_key(s):
        d = ''.join(filter(str.isdigit, s))
        return int(d) if d else 0

    sorted_subjects = sorted(all_subjects, key=_subj_key)

    header_row = '<tr><th>Task</th>' + ''.join(f'<th>{_e(s)}</th>' for s in sorted_subjects) + '</tr>'
    n_cols = len(sorted_subjects) + 1

    parts = [_LEGEND, '<div class="matrix-wrap"><table>']
    for run in all_runs:
        rdf = {(j['subject'], j['task_name']): j.get('status', '') for j in run['jobs']}
        tasks_in_run = run.get('tasks', '') or ''
        parts.append(
            f'<thead>'
            f'<tr class="run-header"><td colspan="{n_cols}">'
            f'Run: {_e(run["label"])}'
            + (f' &nbsp;·&nbsp; tasks: {_e(tasks_in_run)}' if tasks_in_run else '')
            + f'</td></tr>'
            f'{header_row}'
            f'</thead><tbody>'
        )
        for task in all_tasks:
            cells = ''.join(_cell(rdf.get((subj, task), '')) for subj in sorted_subjects)
            parts.append(f'<tr><td>{_e(task)}</td>{cells}</tr>')
        parts.append('</tbody>')

    parts.append('</table></div>')
    return ''.join(parts)


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


def _section_check_results(check_df: Optional[pd.DataFrame]) -> str:
    if check_df is None or check_df.empty:
        return '<p class="empty">No check-results data provided (use --check-results).</p>'

    # Summary pivot: task/check_type rows × subject columns
    df = check_df.copy()
    df['subject'] = df['subject'].astype(str)
    df['row_key'] = df['task'] + '/' + df['check_type'].str.split(':').str[-1]
    row_keys = list(dict.fromkeys(df['row_key'].tolist()))
    subjects = sorted(
        df['subject'].unique().tolist(),
        key=lambda s: int(''.join(filter(str.isdigit, s)) or '0'),
    )

    status_map = {}
    for _, row in df.iterrows():
        is_fail = str(row.get('status', '')).upper().startswith('FAIL')
        status_map[(row['row_key'], row['subject'])] = 'FAILED' if is_fail else 'SUCCESS'

    header_row = '<tr><th>Check</th>' + ''.join(f'<th>{_e(s)}</th>' for s in subjects) + '</tr>'

    prev_task = None
    rows = []
    for rk in row_keys:
        task = rk.split('/')[0]
        if prev_task is not None and task != prev_task:
            # visual separator between task groups
            rows.append(f'<tr style="height:4px;background:#e0e0e0"><td colspan="{len(subjects)+1}"></td></tr>')
        prev_task = task
        cells = ''.join(_cell(status_map.get((rk, subj), '')) for subj in subjects)
        rows.append(f'<tr><td style="font-size:12px;font-family:monospace">{_e(rk)}</td>{cells}</tr>')

    n_fail = sum(1 for _, r in df.iterrows() if str(r.get('status', '')).upper().startswith('FAIL'))
    summary = f'{len(df)} checks — {n_fail} failed'

    matrix_html = (
        _LEGEND +
        '<div class="matrix-wrap">'
        f'<table><thead>{header_row}</thead><tbody>{"".join(rows)}</tbody></table>'
        '</div>'
    )

    # Detailed flat table collapsed by default
    detail_rows = []
    for _, r in df.iterrows():
        status = str(r.get('status', ''))
        is_fail = status.upper().startswith('FAIL')
        status_cell = (f'<td class="fail">{_e(status)}</td>'
                       if is_fail else f'<td>{_e(status)}</td>')
        detail_rows.append(
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
    detail_table = (
        '<table>'
        '<thead><tr>'
        '<th>Task</th><th>Subject</th><th>Session</th>'
        '<th>Check Type</th><th>Pattern</th><th class="num">Actual</th><th>Status</th>'
        '</tr></thead>'
        '<tbody>' + ''.join(detail_rows) + '</tbody>'
        '</table>'
    )

    return (
        matrix_html +
        f'<details style="margin-top:12px">'
        f'<summary>Detail table &nbsp;<span style="color:#888;font-size:12px">({summary})</span></summary>'
        f'<div class="details-body">{detail_table}</div>'
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
    all_subjects: list,
    all_tasks: list,
    all_runs: list,
    failed_jobs: list,
    check_df: Optional[pd.DataFrame],
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

    history_section = ''
    if len(all_runs) > 1:
        history_section = f'''
  <section>
    <h2>Run History</h2>
    {_section_history_matrix(all_runs, all_subjects, all_tasks)}
  </section>'''

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
    {_section_status_matrix([], all_subjects, all_tasks) if not task_summary
      else _section_status_matrix(
          [j for r in [{'jobs': []}] for j in r['jobs']], all_subjects, all_tasks
      )}
  </section>
{history_section}
  <section>
    <h2>Failed Jobs</h2>
    {_section_failed_jobs(failed_jobs)}
  </section>

  <section>
    <h2>Output Validation</h2>
    {_section_check_results(check_df)}
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
