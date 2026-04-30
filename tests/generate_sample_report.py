"""
generate_sample_report.py

Renders report_html.py with realistic mock data so you can visually inspect
the output in a browser. Not a pytest test — run directly:

    python tests/generate_sample_report.py
    python tests/generate_sample_report.py --out /tmp/my_report.html
"""

import argparse
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from neuro_pipeline.pipeline.utils.report_html import render_html

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

SUBJECTS = [f"{i:03d}" for i in range(1, 21)]
TASKS = ["recon", "volume", "rest_preprocess", "rest_post",
         "dwi_preprocess", "dwi_post", "cards_preprocess"]

METADATA = {
    "execution_id":    20260401120000,
    "execution_time":  "2026-04-01 12:00:00",
    "command_line":    "neuropipe run --subjects subjects.txt --input /data/BIDS "
                       "--output /data/processed --work /data/work --project GCDS --session 01 "
                       "--bids-prep rest,dwi --staged-prep cards",
    "project_name":    "GCDS",
    "session":         "01",
    "input_dir":       "/data/BIDS",
    "output_dir":      "/data/processed/GCDS",
    "work_dir":        "/data/work/GCDS",
    "status":          "COMPLETED",
    "total_jobs":      len(SUBJECTS) * len(TASKS),
}

def _make_job_status():
    import random
    random.seed(42)
    rows = []
    for subj in SUBJECTS:
        for task in TASKS:
            if task in ("dwi_preprocess", "dwi_post") and int(subj) > 17:
                continue  # simulate some subjects not run on dwi
            status = "FAILED" if (int(subj) % 7 == 0 and task == "rest_preprocess") else "SUCCESS"
            dur = round(random.uniform(0.5, 4.0), 2) if status == "SUCCESS" else None
            rows.append({
                "subject":        subj,
                "task_name":      task,
                "session":        "01",
                "status":         status,
                "duration_hours": dur,
                "start_time":     f"2026-04-01 1{int(subj) % 10}:00:00",
                "end_time":       f"2026-04-01 1{int(subj) % 10}:30:00" if dur else None,
                "error_msg":      "OOM: killed by SLURM" if status == "FAILED" else None,
                "exit_code":      1 if status == "FAILED" else 0,
                "node_name":      f"node{(int(subj) % 4) + 1:02d}",
            })
    return rows


def _make_task_summary(job_status):
    from collections import defaultdict
    by_task = defaultdict(list)
    for j in job_status:
        by_task[j["task_name"]].append(j)

    rows = []
    for task in TASKS:
        jobs = by_task[task]
        ok     = sum(1 for j in jobs if j["status"] == "SUCCESS")
        failed = sum(1 for j in jobs if j["status"] == "FAILED")
        not_run = len(SUBJECTS) - len(jobs)
        durs = [j["duration_hours"] for j in jobs if j["status"] == "SUCCESS" and j["duration_hours"]]
        if len(durs) >= 2:
            import statistics
            dur_str = f"{statistics.mean(durs):.1f}h ± {statistics.stdev(durs):.1f}h"
        elif len(durs) == 1:
            dur_str = f"{durs[0]:.1f}h"
        else:
            dur_str = "—"
        rows.append({
            "task": task, "total": len(SUBJECTS),
            "ok": ok, "failed": failed, "not_run": not_run,
            "dur": dur_str, "last": "2026-04-01",
        })
    return rows


def _make_failed_jobs(job_status):
    return [
        {
            "subject":    j["subject"],
            "task_name":  j["task_name"],
            "session":    j["session"],
            "start_time": j["start_time"],
            "exit_code":  j["exit_code"],
            "error_msg":  j["error_msg"],
            "stderr":     "ERROR: fmriprep crashed\n  File proc.py, line 42\n  MemoryError",
            "stdout":     "Running preprocessing...\nLoading data...\n[killed]",
        }
        for j in job_status if j["status"] == "FAILED"
    ]


def _make_all_runs(job_status):
    return [
        {
            "label": "2026-04-01 08:00",
            "tasks": "recon,volume,rest_preprocess",
            "jobs": [j for j in job_status if j["task_name"] in ("recon", "volume")][:10],
        },
        {
            "label": "2026-04-01 12:00",
            "tasks": "rest_preprocess,rest_post,dwi_preprocess,cards_preprocess",
            "jobs": [j for j in job_status if j["task_name"] not in ("recon", "volume")][:15],
        },
    ]


def _make_check_df():
    rows = []
    check_types = [("file_count", "*.nii.gz", 1), ("file_exists", "*desc-brain_mask*", 1)]
    for subj in SUBJECTS:
        for task in ("rest_preprocess", "dwi_preprocess", "cards_preprocess"):
            for check_type, pattern, expected in check_types:
                actual = expected if int(subj) % 7 != 0 else 0
                rows.append({
                    "task":       task,
                    "subject":    subj,
                    "session":    "01",
                    "check_type": check_type,
                    "pattern":    pattern,
                    "expected":   expected,
                    "actual":     actual,
                    "status":     "PASS" if actual == expected else "FAIL",
                })
    return pd.DataFrame(rows)


def _make_wrapper_scripts():
    return [
        {
            "task_name":       task,
            "submission_time": "2026-04-01 08:00:00",
            "slurm_cmd":       f"sbatch --job-name={task} --array=1-20%15 wrapper_{task}.sh",
            "env_modules":     "ml Python/3.11.3\nml AFNI/24.3.06",
            "global_python":   ". /home/user/venv/bin/activate",
            "global_env_vars": f"export SESSION=01\nexport TASK={task}",
            "execute_cmd":     f"bash scripts/{task}.sh $SUBJECT $SESSION",
        }
        for task in TASKS
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="sample_report.html",
                        help="Output HTML path (default: sample_report.html)")
    args = parser.parse_args()

    job_status   = _make_job_status()
    task_summary = _make_task_summary(job_status)
    failed_jobs  = _make_failed_jobs(job_status)
    all_runs     = _make_all_runs(job_status)
    check_df     = _make_check_df()
    wrapper_scripts = _make_wrapper_scripts()

    html = render_html(
        metadata=METADATA,
        task_summary=task_summary,
        job_status=job_status,
        all_subjects=SUBJECTS,
        all_tasks=TASKS,
        all_runs=all_runs,
        failed_jobs=failed_jobs,
        check_df=check_df,
        wrapper_scripts=wrapper_scripts,
        project_name="GCDS",
        session="01",
    )

    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"Report written to: {out.resolve()}")


if __name__ == "__main__":
    main()
