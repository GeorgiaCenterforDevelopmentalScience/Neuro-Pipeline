#!/usr/bin/env python3
"""Generate a standalone HTML pipeline report from the job database."""

import base64
import glob
import io
import os
import sqlite3
from datetime import datetime
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from .report_html import render_html

from .config_utils import get_all_task_names
TASK_ORDER = get_all_task_names()

STATUS_COLOR = {
    'SUCCESS': '#C5E0B3',
    'FAILED':  '#F8786E',
    'NOT_RUN': '#D3D3D3',
}

def _rows(conn: sqlite3.Connection, sql: str, params=()):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_report_data(db_path: str, project_name: str, session: Optional[str]) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    meta_sql = ("SELECT * FROM pipeline_executions WHERE project_name = ?"
                + (" AND session = ?" if session else "")
                + " ORDER BY execution_time DESC LIMIT 1")
    meta_params = [project_name] + ([session] if session else [])
    meta_row = conn.execute(meta_sql, meta_params).fetchone()
    metadata = dict(meta_row) if meta_row else {}

    subj_rows = conn.execute(
        "SELECT subjects FROM pipeline_executions WHERE project_name = ?",
        [project_name]
    ).fetchall()
    all_subjects: set = set()
    for row in subj_rows:
        if row[0]:
            all_subjects.update(s.strip() for s in row[0].split(',') if s.strip())

    if all_subjects:
        ph = ','.join('?' * len(all_subjects))
        sess_filter_subq  = "AND session = ?"    if session else ""  # inside subquery, no alias
        sess_filter_alias = "AND js.session = ?" if session else ""  # outer query with js alias
        latest_sql = f"""
            SELECT js.subject, js.task_name, js.session, js.status,
                   js.duration_hours, js.start_time, js.end_time,
                   js.error_msg, js.exit_code, js.node_name
            FROM job_status js
            INNER JOIN (
                SELECT subject, task_name, session, MAX(start_time) AS max_start
                FROM job_status
                WHERE subject IN ({ph})
                {sess_filter_subq}
                GROUP BY subject, task_name, session
            ) latest
              ON  js.subject   = latest.subject
              AND js.task_name = latest.task_name
              AND (js.session = latest.session
                   OR (js.session IS NULL AND latest.session IS NULL))
              AND js.start_time = latest.max_start
        """
        latest_params = list(all_subjects) + ([session] if session else [])
        job_status = _rows(conn, latest_sql, latest_params)

        failed_sql = f"""
            SELECT js.subject, js.task_name, js.session,
                   js.start_time, js.exit_code, js.error_msg,
                   co.stderr, co.stdout
            FROM job_status js
            LEFT JOIN command_outputs co
              ON co.id = (
                    SELECT id FROM command_outputs
                    WHERE subject   = js.subject
                      AND task_name = js.task_name
                      AND (session  = js.session
                           OR (session IS NULL AND js.session IS NULL))
                    ORDER BY execution_time DESC LIMIT 1
                  )
            WHERE js.status = 'FAILED'
              AND js.subject IN ({ph})
              {sess_filter_alias}
            ORDER BY js.task_name, js.subject
        """
        failed_jobs = _rows(conn, failed_sql, latest_params)
    else:
        job_status = []
        failed_jobs = []

    exec_sql = ("SELECT execution_time, requested_tasks FROM pipeline_executions "
                "WHERE project_name = ?"
                + (" AND session = ?" if session else "")
                + " ORDER BY execution_time ASC")
    executions = _rows(conn, exec_sql, meta_params)

    if all_subjects:
        all_jobs_sql = f"""
            SELECT subject, task_name, session, status, start_time
            FROM job_status
            WHERE subject IN ({ph})
            {sess_filter_subq}
            ORDER BY start_time ASC
        """
        all_jobs = _rows(conn, all_jobs_sql, list(all_subjects) + ([session] if session else []))

        all_runs = []
        for i, ex in enumerate(executions):
            t0 = ex['execution_time']
            t1 = executions[i + 1]['execution_time'] if i + 1 < len(executions) else None
            run_jobs = [j for j in all_jobs
                        if j['start_time'] >= t0 and (t1 is None or j['start_time'] < t1)]
            if run_jobs:
                all_runs.append({
                    'label': t0[:16],
                    'tasks': ex.get('requested_tasks', ''),
                    'jobs':  run_jobs,
                })
    else:
        all_runs = []

    wrapper_sql = """
        SELECT ws.task_name, ws.submission_time, ws.slurm_cmd,
               ws.env_modules, ws.global_python, ws.global_env_vars,
               ws.execute_cmd
        FROM wrapper_scripts ws
        WHERE ws.submission_time = (
            SELECT MAX(submission_time) FROM wrapper_scripts
            WHERE task_name = ws.task_name
        )
        ORDER BY ws.task_name
    """
    wrapper_scripts = _rows(conn, wrapper_sql)

    conn.close()
    return {
        'metadata':        metadata,
        'all_subjects':    sorted(all_subjects, key=lambda x: x.lower()),
        'job_status':      job_status,
        'failed_jobs':     failed_jobs,
        'wrapper_scripts': wrapper_scripts,
        'all_runs':        all_runs,
    }


def compute_task_summary(job_status: list, all_subjects: list) -> list:
    df = (pd.DataFrame(job_status)
          if job_status
          else pd.DataFrame(columns=['subject', 'task_name', 'status', 'duration_hours', 'start_time']))

    data_tasks = set(df['task_name'].unique()) if not df.empty else set()
    ordered = [t for t in TASK_ORDER if t in data_tasks]
    extras  = sorted(data_tasks - set(ordered))
    all_tasks = ordered + extras

    total = len(all_subjects)
    rows = []
    for task in all_tasks:
        tdf = df[df['task_name'] == task] if not df.empty else df
        n_ok   = int((tdf['status'] == 'SUCCESS').sum())
        n_fail = int((tdf['status'] == 'FAILED').sum())
        n_none = total - len(tdf)

        durs = tdf[tdf['status'] == 'SUCCESS']['duration_hours'].dropna()
        if len(durs) >= 2:
            dur_str = f"{durs.mean():.1f}h ± {durs.std():.1f}h"
        elif len(durs) == 1:
            dur_str = f"{durs.iloc[0]:.1f}h"
        else:
            dur_str = "—"

        last_run = "—"
        if not tdf.empty and 'start_time' in tdf.columns:
            ts = tdf['start_time'].dropna().max()
            if ts:
                try:
                    last_run = datetime.fromisoformat(ts).strftime('%Y-%m-%d')
                except ValueError:
                    last_run = str(ts)[:10]

        rows.append({
            'task':    task,
            'total':   total,
            'ok':      n_ok,
            'failed':  n_fail,
            'not_run': n_none,
            'dur':     dur_str,
            'last':    last_run,
        })
    return rows


def ordered_tasks_from_summary(summary: list) -> list:
    return [r['task'] for r in summary]

def create_heatmap_png(job_status: list, all_subjects: list, all_tasks: list) -> str:
    """Render the Subject × Task status matrix as a base64-encoded PNG."""
    df = (pd.DataFrame(job_status)
          if job_status
          else pd.DataFrame(columns=['subject', 'task_name', 'session', 'status']))

    # Determine sessions
    if 'session' in df.columns and df['session'].notna().any():
        sessions = sorted(df['session'].dropna().unique())
    else:
        sessions = [None]

    def _subj_key(s):
        d = ''.join(filter(str.isdigit, s))
        return int(d) if d else 0

    sorted_subjects = sorted(all_subjects, key=_subj_key)
    n_subj  = len(sorted_subjects)
    n_tasks = len(all_tasks)
    n_sess  = len(sessions)

    if n_subj == 0 or n_tasks == 0:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes, color='#888', fontsize=11)
        ax.axis('off')
    else:
        cell_w  = max(0.15, min(0.32, 14.0 / n_subj))
        cell_h  = 0.20
        label_w = max(1.8, max(len(t) for t in all_tasks) * 0.09)
        label_h = max(0.7, max(len(s) for s in sorted_subjects) * 0.065)

        fig_w = min(22, label_w + n_subj * cell_w + 1.2)
        fig_h = (label_h + n_tasks * cell_h + 0.6) * n_sess + 0.4 * max(0, n_sess - 1)

        fig, axes = plt.subplots(n_sess, 1,
                                 figsize=(fig_w, fig_h),
                                 squeeze=False,
                                 layout='constrained')

        # NOT_RUN=0, FAILED=1, SUCCESS=2
        cmap = ListedColormap([STATUS_COLOR['NOT_RUN'],
                               STATUS_COLOR['FAILED'],
                               STATUS_COLOR['SUCCESS']])
        s2n = {'SUCCESS': 2, 'FAILED': 1}

        for si, session in enumerate(sessions):
            ax  = axes[si, 0]
            sdf = df[df['session'] == session] if session is not None else df

            matrix = np.zeros((n_tasks, n_subj), dtype=int)
            for ti, task in enumerate(all_tasks):
                for xi, subj in enumerate(sorted_subjects):
                    rec = sdf[(sdf['task_name'] == task) & (sdf['subject'] == subj)]
                    if not rec.empty:
                        matrix[ti, xi] = s2n.get(rec.iloc[0]['status'], 0)

            ax.imshow(matrix, cmap=cmap, vmin=0, vmax=2,
                      aspect='auto', interpolation='none')

            title = f"Session {session}" if session is not None else "Status"
            ax.set_title(title, fontsize=9, loc='left', pad=5,
                         fontdict={'fontweight': 'normal', 'color': '#444'})

            ax.set_xticks(range(n_subj))
            ax.set_xticklabels(sorted_subjects, rotation=45, ha='right', fontsize=7)
            ax.set_yticks(range(n_tasks))
            ax.set_yticklabels(all_tasks, fontsize=8)
            ax.tick_params(length=0)
            for spine in ax.spines.values():
                spine.set_visible(False)

            ax.set_xticks(np.arange(-0.5, n_subj),  minor=True)
            ax.set_yticks(np.arange(-0.5, n_tasks), minor=True)
            ax.grid(which='minor', color='white', linewidth=0.8)
            ax.tick_params(which='minor', length=0)

        legend_patches = [
            Patch(facecolor=STATUS_COLOR['SUCCESS'], edgecolor='#bbb', linewidth=0.5, label='OK'),
            Patch(facecolor=STATUS_COLOR['FAILED'],  edgecolor='#bbb', linewidth=0.5, label='FAIL'),
            Patch(facecolor=STATUS_COLOR['NOT_RUN'], edgecolor='#bbb', linewidth=0.5, label='Not run'),
        ]
        axes[0, 0].legend(handles=legend_patches, loc='upper left',
                          bbox_to_anchor=(1.02, 1.0), borderaxespad=0,
                          fontsize=8, framealpha=0.95, edgecolor='#ddd', handlelength=1.2)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')

def create_history_heatmap_png(all_runs: list, all_subjects: list, all_tasks: list) -> str:
    def _subj_key(s):
        d = ''.join(filter(str.isdigit, s))
        return int(d) if d else 0

    sorted_subjects = sorted(all_subjects, key=_subj_key)
    n_subj  = len(sorted_subjects)
    n_tasks = len(all_tasks)
    n_runs  = len(all_runs)

    if n_subj == 0 or n_tasks == 0 or n_runs == 0:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.text(0.5, 0.5, 'No history data', ha='center', va='center',
                transform=ax.transAxes, color='#888', fontsize=11)
        ax.axis('off')
    else:
        total_rows = n_runs * n_tasks
        matrix = np.zeros((total_rows, n_subj), dtype=int)
        s2n = {'SUCCESS': 2, 'FAILED': 1}

        for ri, run in enumerate(all_runs):
            rdf = pd.DataFrame(run['jobs'])
            for ti, task in enumerate(all_tasks):
                row_idx = ri * n_tasks + ti
                for xi, subj in enumerate(sorted_subjects):
                    rec = rdf[(rdf['task_name'] == task) & (rdf['subject'] == subj)]
                    if not rec.empty:
                        matrix[row_idx, xi] = s2n.get(rec.iloc[0]['status'], 0)

        cell_w  = max(0.15, min(0.32, 14.0 / n_subj))
        cell_h  = 0.25
        label_w = max(1.8, max(len(t) for t in all_tasks) * 0.09)
        label_h = max(0.7, max(len(s) for s in sorted_subjects) * 0.065)

        fig_w = min(22, label_w + n_subj * cell_w + 2.0)
        fig_h = max(2.0, label_h + total_rows * cell_h + 0.5)

        fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), layout='constrained')
        cmap = ListedColormap([STATUS_COLOR['NOT_RUN'],
                               STATUS_COLOR['FAILED'],
                               STATUS_COLOR['SUCCESS']])
        ax.imshow(matrix, cmap=cmap, vmin=0, vmax=2, aspect='auto', interpolation='none')

        ax.set_xticks(range(n_subj))
        ax.set_xticklabels(sorted_subjects, rotation=45, ha='right', fontsize=7)
        ax.set_yticks(range(total_rows))
        ax.set_yticklabels(all_tasks * n_runs, fontsize=7)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_xticks(np.arange(-0.5, n_subj),    minor=True)
        ax.set_yticks(np.arange(-0.5, total_rows), minor=True)
        ax.grid(which='minor', color='white', linewidth=0.6)
        ax.tick_params(which='minor', length=0)

        # run separators + labels
        for ri, run in enumerate(all_runs):
            if ri > 0:
                ax.axhline(ri * n_tasks - 0.5, color='#666', linewidth=1.2, zorder=3)
            mid = ri * n_tasks + (n_tasks - 1) / 2
            ax.text(n_subj - 0.4, mid, run['label'], fontsize=7, color='#444',
                    ha='left', va='center',
                    bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                              alpha=0.85, edgecolor='none'))

        legend_patches = [
            Patch(facecolor=STATUS_COLOR['SUCCESS'], edgecolor='#bbb', linewidth=0.5, label='OK'),
            Patch(facecolor=STATUS_COLOR['FAILED'],  edgecolor='#bbb', linewidth=0.5, label='FAIL'),
            Patch(facecolor=STATUS_COLOR['NOT_RUN'], edgecolor='#bbb', linewidth=0.5, label='Not run'),
        ]
        ax.legend(handles=legend_patches, loc='upper left',
                  bbox_to_anchor=(1.02, 1.0), borderaxespad=0,
                  fontsize=8, framealpha=0.95, edgecolor='#ddd', handlelength=1.2)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')


def create_check_heatmap_png(check_df: pd.DataFrame, all_subjects: list) -> str:
    """Render check results as a Subject × Check heatmap with one row per check type."""
    df = check_df.copy()
    df['subject'] = df['subject'].astype(str)

    df['row_key'] = df['task'] + '/' + df['check_type'].str.split(':').str[-1]

    # Preserve CSV row order for row_keys
    row_keys = list(dict.fromkeys(df['row_key'].tolist()))

    check_subjects = sorted(
        df['subject'].unique().tolist(),
        key=lambda s: int(''.join(filter(str.isdigit, s)) or '0'),
    )

    n_subj = len(check_subjects)
    n_rows = len(row_keys)

    if n_subj == 0 or n_rows == 0:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.text(0.5, 0.5, 'No check data', ha='center', va='center',
                transform=ax.transAxes, color='#888', fontsize=11)
        ax.axis('off')
    else:
        status_map = {}
        for _, row in df.iterrows():
            is_fail = str(row.get('status', '')).upper().startswith('FAIL')
            status_map[(row['row_key'], row['subject'])] = 1 if is_fail else 2

        matrix = np.zeros((n_rows, n_subj), dtype=int)
        for ri, rk in enumerate(row_keys):
            for xi, subj in enumerate(check_subjects):
                matrix[ri, xi] = status_map.get((rk, subj), 0)

        cell_w  = max(0.15, min(0.32, 14.0 / n_subj))
        cell_h  = 0.20
        label_w = max(1.8, max(len(r) for r in row_keys) * 0.085)
        label_h = max(0.5, max(len(s) for s in check_subjects) * 0.065)

        fig_w = min(22, label_w + n_subj * cell_w + 1.5)  # +1.5 for legend outside
        fig_h = max(2.0, label_h + n_rows * cell_h + 0.3)

        fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))

        cmap = ListedColormap([STATUS_COLOR['NOT_RUN'],
                               STATUS_COLOR['FAILED'],
                               STATUS_COLOR['SUCCESS']])
        ax.imshow(matrix, cmap=cmap, vmin=0, vmax=2, aspect='auto', interpolation='none')

        ax.set_xticks(range(n_subj))
        ax.set_xticklabels(check_subjects, rotation=45, ha='right', fontsize=8)
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(row_keys, fontsize=7)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_xticks(np.arange(-0.5, n_subj), minor=True)
        ax.set_yticks(np.arange(-0.5, n_rows),  minor=True)
        ax.grid(which='minor', color='white', linewidth=0.8)
        ax.tick_params(which='minor', length=0)

        # Separator lines between task groups
        prev_task = None
        for ri, rk in enumerate(row_keys):
            task = rk.split('/')[0]
            if prev_task is not None and task != prev_task:
                ax.axhline(ri - 0.5, color='#777', linewidth=1.0, zorder=3)
            prev_task = task

        legend_patches = [
            Patch(facecolor=STATUS_COLOR['SUCCESS'], edgecolor='#bbb', linewidth=0.5, label='PASS'),
            Patch(facecolor=STATUS_COLOR['FAILED'],  edgecolor='#bbb', linewidth=0.5, label='FAIL'),
            Patch(facecolor=STATUS_COLOR['NOT_RUN'], edgecolor='#bbb', linewidth=0.5, label='N/A'),
        ]
        ax.legend(handles=legend_patches, loc='upper left',
                  bbox_to_anchor=(1.02, 1.0), borderaxespad=0,
                  fontsize=8, framealpha=0.95, edgecolor='#ddd', handlelength=1.2)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')


def generate_report(
    db_path: str,
    project_name: str,
    output_path: Optional[str] = None,
    session: Optional[str] = None,
    check_results_path: Optional[str] = None,
) -> str:
    """Generate the HTML report and write it to disk. Returns the output path."""

    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    print(f"Reading database: {db_path}")
    data = get_report_data(db_path, project_name, session)

    if not data['all_subjects']:
        raise ValueError(
            f"No records found for project '{project_name}'"
            + (f", session '{session}'" if session else "")
            + ". Check --project / --session."
        )
    print(f"  {len(data['all_subjects'])} subject(s), "
          f"{len(data['job_status'])} job records")

    task_summary = compute_task_summary(data['job_status'], data['all_subjects'])
    all_tasks    = ordered_tasks_from_summary(task_summary)

    # Check results CSV — explicit path, or auto-discover in work_dir
    check_df: Optional[pd.DataFrame] = None
    if check_results_path:
        if not os.path.isfile(check_results_path):
            print(f"  Warning: check-results file not found: {check_results_path}")
        else:
            check_df = pd.read_csv(check_results_path)
            print(f"  Loaded check-results: {len(check_df)} rows")
    else:
        work_dir = data['metadata'].get('work_dir', '')
        if work_dir:
            candidates = sorted(
                glob.glob(os.path.join(work_dir, 'check_results_*.csv')),
                reverse=True,
            )
            if candidates:
                check_df = pd.read_csv(candidates[0])
                print(f"  Auto-detected check-results: {candidates[0]}")

    print("Rendering heatmap...")
    heatmap_b64 = create_heatmap_png(data['job_status'], data['all_subjects'], all_tasks)

    history_heatmap_b64: Optional[str] = None
    if len(data['all_runs']) > 1:
        print(f"Rendering run history ({len(data['all_runs'])} runs)...")
        history_heatmap_b64 = create_history_heatmap_png(
            data['all_runs'], data['all_subjects'], all_tasks
        )

    check_heatmap_b64: Optional[str] = None
    if check_df is not None and not check_df.empty:
        print("Rendering check-results heatmap...")
        check_heatmap_b64 = create_check_heatmap_png(check_df, data['all_subjects'])

    html_content = render_html(
        metadata=data['metadata'],
        task_summary=task_summary,
        heatmap_b64=heatmap_b64,
        history_heatmap_b64=history_heatmap_b64,
        failed_jobs=data['failed_jobs'],
        check_df=check_df,
        check_heatmap_b64=check_heatmap_b64,
        wrapper_scripts=data['wrapper_scripts'],
        project_name=project_name,
        session=session,
    )

    if not output_path:
        ts      = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_dir  = os.path.dirname(os.path.abspath(db_path))
        output_path = os.path.join(db_dir, f"pipeline_report_{project_name}_{ts}.html")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Report saved: {output_path}")
    return output_path
