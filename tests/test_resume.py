"""
test_resume.py

Tests for:
  - OutputChecker (output_checker.py)
      - required_files check (pass / fail / size fail)
      - count_check (pass / too few / too many / within tolerance)
      - mixed checks on one task
      - get_completed_subjects / get_pending_subjects
      - warn_missing_configs
      - check_all (multi-task × multi-subject)
      - print_terminal_summary  (stdout capture)
      - save_csv
      - load_checks_config  (file resolution helper)

  - DAGExecutor.execute() resume mode (dag.py)
      - completed subjects are skipped per task
      - all-complete task is skipped entirely
      - task with no checks config still runs normally
      - DAG dependency order preserved under resume
        (post_fc waits for preprocess even when recon is skipped)
"""

import os
import pytest
import warnings
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from tests.conftest import MOCK_CONFIG, MOCK_PROJECT_CONFIG

CONFIG_PATH = "neuro_pipeline.pipeline.utils.config_utils.config"

# ---------------------------------------------------------------------------
# Minimal checks YAML used across all OutputChecker tests
# ---------------------------------------------------------------------------

MOCK_CHECKS = {
    "rest_fmriprep_preprocess": {
        "output_path": "{work_dir}/fmriprep/",
        "required_files": [
            {"pattern": "sub-{subject}*.html", "min_size_kb": 1},
        ],
    },
    "afni_volume": {
        "output_path": "{work_dir}/afni/{prefix}{subject}/T1",
        "required_files": [
            {"pattern": "QC_anatSS.{prefix}{subject}.jpg"},  # no size check
        ],
    },
    "recon_bids": {
        "output_path": "{work_dir}/BIDS/sub-{subject}/ses-{session}/",
        "count_check": {
            "anat": {
                "pattern": "anat/*.nii.gz",
                "expected_count": 1,
                "tolerance": 0,
            },
            "func": {
                "pattern": "func/*rest*.nii.gz",
                "expected_count": 2,
                "tolerance": 1,
            },
        },
    },
    "mixed_task": {
        "output_path": "{work_dir}/mixed/{subject}",
        "required_files": [
            {"pattern": "report.html", "min_size_kb": 10},
        ],
        "count_check": {
            "nii": {
                "pattern": "*.nii.gz",
                "expected_count": 2,
                "tolerance": 0,
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def checks_yaml(tmp_path):
    """Write MOCK_CHECKS to a real YAML file; return path string."""
    p = tmp_path / "test_checks.yaml"
    with open(p, "w") as f:
        yaml.dump(MOCK_CHECKS, f)
    return str(p)


@pytest.fixture
def checker(checks_yaml, tmp_path):
    """Return an OutputChecker pointed at tmp_path as work_dir."""
    from neuro_pipeline.pipeline.utils.output_checker import OutputChecker
    return OutputChecker(
        config_path=checks_yaml,
        work_dir=str(tmp_path),
        prefix="sub-",
        session="01",
    )


def _make_file(path: Path, size_kb: float = 0) -> None:
    """Create a file with at least size_kb kilobytes of content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * max(1, int(size_kb * 1024)))


# ===========================================================================
# OutputChecker — required_files
# ===========================================================================

class TestRequiredFilesCheck:

    def test_pass_when_file_exists_no_size_check(self, checker, tmp_path):
        """Pattern matches existing file; no min_size_kb → PASS."""
        subject = "001"
        out_dir = tmp_path / "afni" / f"sub-{subject}" / "T1"
        _make_file(out_dir / f"QC_anatSS.sub-{subject}.jpg", size_kb=0.1)

        rows = checker.check_subject("afni_volume", subject)
        assert len(rows) == 1
        assert rows[0]["status"] == "PASS"

    def test_fail_when_file_missing(self, checker, tmp_path):
        """No file on disk → FAIL."""
        rows = checker.check_subject("afni_volume", "999")
        assert len(rows) == 1
        assert rows[0]["status"].startswith("FAIL")

    def test_pass_when_file_meets_size_threshold(self, checker, tmp_path):
        subject = "002"
        out_dir = tmp_path / "fmriprep"
        _make_file(out_dir / f"sub-{subject}_report.html", size_kb=2)

        rows = checker.check_subject("rest_fmriprep_preprocess", subject)
        assert rows[0]["status"] == "PASS"

    def test_fail_when_file_too_small(self, checker, tmp_path):
        """File exists but below min_size_kb → FAIL."""
        subject = "003"
        out_dir = tmp_path / "fmriprep"
        # write a file that is definitely < 1 KB
        _make_file(out_dir / f"sub-{subject}_report.html", size_kb=0.1)

        rows = checker.check_subject("rest_fmriprep_preprocess", subject)
        assert rows[0]["status"].startswith("FAIL")
        assert "too small" in rows[0]["status"]

    def test_plain_string_pattern_accepted(self, checks_yaml, tmp_path):
        """required_files entries can be plain strings (no min_size_kb)."""
        checks = {
            "simple_task": {
                "output_path": "{work_dir}/simple",
                "required_files": ["result.txt"],   # plain string
            }
        }
        p = tmp_path / "simple_checks.yaml"
        with open(p, "w") as f:
            yaml.dump(checks, f)

        from neuro_pipeline.pipeline.utils.output_checker import OutputChecker
        c = OutputChecker(str(p), str(tmp_path), "sub-", "01")

        # file missing → FAIL
        rows = c.check_subject("simple_task", "001")
        assert rows[0]["status"].startswith("FAIL")

        # create the file → PASS
        _make_file(tmp_path / "simple" / "result.txt")
        rows = c.check_subject("simple_task", "001")
        assert rows[0]["status"] == "PASS"


# ===========================================================================
# OutputChecker — count_check
# ===========================================================================

class TestCountCheck:

    def _bids_dir(self, tmp_path, subject, session="01"):
        return tmp_path / "BIDS" / f"sub-{subject}" / f"ses-{session}"

    def test_pass_exact_count(self, checker, tmp_path):
        """Exactly expected_count files → PASS."""
        subject = "001"
        base = self._bids_dir(tmp_path, subject)
        _make_file(base / "anat" / "sub-001_T1w.nii.gz")
        # func: expected 2 ± 1, give exactly 2
        _make_file(base / "func" / "sub-001_task-rest_run-1_bold.nii.gz")
        _make_file(base / "func" / "sub-001_task-rest_run-2_bold.nii.gz")

        rows = checker.check_subject("recon_bids", subject)
        statuses = {r["check_type"]: r["status"] for r in rows}
        assert statuses["count_check:anat"] == "PASS"
        assert statuses["count_check:func"] == "PASS"

    def test_pass_within_tolerance(self, checker, tmp_path):
        """1 func file when expected=2 tolerance=1 → PASS."""
        subject = "002"
        base = self._bids_dir(tmp_path, subject)
        _make_file(base / "anat" / "sub-002_T1w.nii.gz")
        _make_file(base / "func" / "sub-002_task-rest_bold.nii.gz")  # only 1

        rows = checker.check_subject("recon_bids", subject)
        func_row = next(r for r in rows if r["check_type"] == "count_check:func")
        assert func_row["status"] == "PASS"

    def test_fail_too_few(self, checker, tmp_path):
        """0 anat files when expected=1 tolerance=0 → FAIL."""
        subject = "003"
        base = self._bids_dir(tmp_path, subject)
        base.mkdir(parents=True, exist_ok=True)  # dir exists, but no files

        rows = checker.check_subject("recon_bids", subject)
        anat_row = next(r for r in rows if r["check_type"] == "count_check:anat")
        assert "too few" in anat_row["status"]

    def test_fail_too_many(self, checker, tmp_path):
        """3 func files when expected=2 tolerance=1 → FAIL (exceeds)."""
        subject = "004"
        base = self._bids_dir(tmp_path, subject)
        _make_file(base / "anat" / "sub-004_T1w.nii.gz")
        for i in range(3):
            _make_file(base / "func" / f"sub-004_task-rest_run-{i}_bold.nii.gz")

        rows = checker.check_subject("recon_bids", subject)
        func_row = next(r for r in rows if r["check_type"] == "count_check:func")
        assert "too many" in func_row["status"]


# ===========================================================================
# OutputChecker — mixed required_files + count_check
# ===========================================================================

class TestMixedChecks:

    def test_all_pass(self, checker, tmp_path):
        subject = "001"
        base = tmp_path / "mixed" / subject
        _make_file(base / "report.html", size_kb=20)
        _make_file(base / "scan1.nii.gz")
        _make_file(base / "scan2.nii.gz")

        rows = checker.check_subject("mixed_task", subject)
        assert all(r["status"] == "PASS" for r in rows)

    def test_partial_fail(self, checker, tmp_path):
        subject = "002"
        base = tmp_path / "mixed" / subject
        # report present and large enough
        _make_file(base / "report.html", size_kb=20)
        # only 1 nii when expected=2 tolerance=0 → count fail

        _make_file(base / "only_one.nii.gz")

        rows = checker.check_subject("mixed_task", subject)
        statuses = [r["status"] for r in rows]
        assert "PASS" in statuses          # report passes
        assert any(s.startswith("FAIL") for s in statuses)  # count fails


# ===========================================================================
# OutputChecker — completed / pending subjects
# ===========================================================================

class TestCompletedPendingSubjects:

    def _make_passing_fmriprep(self, tmp_path, subject):
        """Create the output file that makes rest_fmriprep_preprocess pass."""
        out_dir = tmp_path / "fmriprep"
        _make_file(out_dir / f"sub-{subject}_report.html", size_kb=2)

    def test_completed_subjects_all_pass(self, checker, tmp_path):
        for sub in ["001", "002"]:
            self._make_passing_fmriprep(tmp_path, sub)

        completed = checker.get_completed_subjects(
            "rest_fmriprep_preprocess", ["001", "002", "003"]
        )
        assert set(completed) == {"001", "002"}

    def test_pending_subjects_are_complement(self, checker, tmp_path):
        self._make_passing_fmriprep(tmp_path, "001")

        pending = checker.get_pending_subjects(
            "rest_fmriprep_preprocess", ["001", "002", "003"]
        )
        assert set(pending) == {"002", "003"}

    def test_all_complete_returns_empty_pending(self, checker, tmp_path):
        for sub in ["001", "002"]:
            self._make_passing_fmriprep(tmp_path, sub)

        pending = checker.get_pending_subjects(
            "rest_fmriprep_preprocess", ["001", "002"]
        )
        assert pending == []

    def test_none_complete_returns_all_pending(self, checker):
        pending = checker.get_pending_subjects(
            "rest_fmriprep_preprocess", ["001", "002"]
        )
        assert set(pending) == {"001", "002"}

    def test_unconfigured_task_returns_no_completed(self, checker):
        """Task not in yaml → completed list is empty (safe default)."""
        completed = checker.get_completed_subjects("nonexistent_task", ["001"])
        assert completed == []


# ===========================================================================
# OutputChecker — warn_missing_configs
# ===========================================================================

class TestWarnMissingConfigs:

    def test_warns_for_unknown_task(self, checker):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            missing = checker.warn_missing_configs(["rest_fmriprep_preprocess", "ghost_task"])
        assert "ghost_task" in missing
        assert any("ghost_task" in str(warning.message) for warning in w)

    def test_no_warning_for_known_tasks(self, checker):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            missing = checker.warn_missing_configs(["rest_fmriprep_preprocess", "afni_volume"])
        assert missing == []
        assert len(w) == 0

    def test_returns_list_of_missing_names(self, checker):
        missing = checker.warn_missing_configs(["a", "b", "rest_fmriprep_preprocess"])
        assert set(missing) == {"a", "b"}


# ===========================================================================
# OutputChecker — check_all
# ===========================================================================

class TestCheckAll:

    def test_returns_dataframe_with_correct_columns(self, checker):
        import pandas as pd
        df = checker.check_all(["rest_fmriprep_preprocess"], ["001"])
        assert isinstance(df, pd.DataFrame)
        for col in ["task", "subject", "session", "check_type", "status"]:
            assert col in df.columns

    def test_empty_dataframe_when_no_tasks_configured(self, checker):
        import pandas as pd
        df = checker.check_all(["ghost_task"], ["001"])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_rows_per_subject_per_check(self, checker, tmp_path):
        """Two subjects × one check each = 2 rows."""
        df = checker.check_all(["rest_fmriprep_preprocess"], ["001", "002"])
        assert len(df) == 2
        assert set(df["subject"].tolist()) == {"001", "002"}

    def test_skips_unconfigured_tasks_silently(self, checker):
        """Tasks not in config are silently skipped in check_all."""
        df = checker.check_all(["ghost_task", "rest_fmriprep_preprocess"], ["001"])
        assert all(df["task"] == "rest_fmriprep_preprocess")


# ===========================================================================
# OutputChecker — print_terminal_summary
# ===========================================================================

class TestPrintTerminalSummary:

    def test_prints_all_passed(self, checker, capsys):
        import pandas as pd
        df = pd.DataFrame([
            {"task": "rest_fmriprep_preprocess", "subject": "001",
             "session": "01", "check_type": "required_files",
             "pattern": "*.html", "expected": "exists", "actual": 1,
             "status": "PASS"},
        ])
        checker.print_terminal_summary(df)
        out = capsys.readouterr().out
        assert "All checks passed" in out

    def test_prints_failing_subjects_only(self, checker, capsys):
        import pandas as pd
        df = pd.DataFrame([
            {"task": "rest_fmriprep_preprocess", "subject": "001",
             "session": "01", "check_type": "required_files",
             "pattern": "*.html", "expected": "exists", "actual": 0,
             "status": "FAIL – file not found"},
            {"task": "rest_fmriprep_preprocess", "subject": "002",
             "session": "01", "check_type": "required_files",
             "pattern": "*.html", "expected": "exists", "actual": 1,
             "status": "PASS"},
        ])
        checker.print_terminal_summary(df)
        out = capsys.readouterr().out
        # 001 is bad, 002 is fine — terminal should mention 001 but not 002
        assert "001" in out
        assert "002" not in out

    def test_empty_dataframe(self, checker, capsys):
        import pandas as pd
        checker.print_terminal_summary(pd.DataFrame())
        out = capsys.readouterr().out
        assert "No checks were run" in out


# ===========================================================================
# OutputChecker — save_csv
# ===========================================================================

class TestSaveCsv:

    def test_creates_csv_in_work_dir(self, checker, tmp_path):
        import pandas as pd
        df = pd.DataFrame([{"task": "t", "subject": "001", "status": "PASS"}])
        path = checker.save_csv(df, str(tmp_path))
        assert Path(path).exists()
        assert path.endswith(".csv")

    def test_csv_contains_correct_data(self, checker, tmp_path):
        import pandas as pd
        df = pd.DataFrame([{"task": "rest_fmriprep_preprocess", "subject": "001", "status": "PASS"}])
        path = checker.save_csv(df, str(tmp_path))
        loaded = pd.read_csv(path)
        assert loaded.iloc[0]["task"] == "rest_fmriprep_preprocess"
        assert loaded.iloc[0]["status"] == "PASS"

    def test_filename_contains_timestamp(self, checker, tmp_path):
        import pandas as pd
        path = checker.save_csv(pd.DataFrame(), str(tmp_path))
        assert "check_results_" in Path(path).name


# ===========================================================================
# load_checks_config helper
# ===========================================================================

class TestLoadChecksConfig:

    def test_returns_path_when_file_exists(self, tmp_path):
        f = tmp_path / "myproject_checks.yaml"
        f.write_text("---")
        from neuro_pipeline.pipeline.utils.output_checker import load_checks_config
        result = load_checks_config("myproject", checks_dir=str(tmp_path))
        assert result == str(f)

    def test_raises_when_file_missing(self, tmp_path):
        from neuro_pipeline.pipeline.utils.output_checker import load_checks_config
        with pytest.raises(FileNotFoundError, match="myproject_checks.yaml"):
            load_checks_config("myproject", checks_dir=str(tmp_path))


# ===========================================================================
# DAGExecutor.execute() — resume mode
# ===========================================================================

def make_executor():
    with patch(CONFIG_PATH, MOCK_CONFIG):
        from neuro_pipeline.pipeline.dag import DAGExecutor
        ex = DAGExecutor(MOCK_CONFIG)
        ex.project_config = MOCK_PROJECT_CONFIG
        return ex


class TestDAGExecutorResume:
    """
    Tests for resume behaviour inside DAGExecutor.execute().
    _execute_single_task is mocked so no real sbatch calls are made.
    OutputChecker is mocked to control which subjects appear "completed".
    """

    SUBJECTS = ["001", "002", "003"]

    def _run_execute(self, requested_tasks, completed_map,
                     rest_deps=None, dwi_deps=None,
                     checks_config_path="fake_checks.yaml"):
        """
        Run dag_executor.execute() with:
          - _execute_single_task mocked to return a predictable job_id
          - OutputChecker.get_pending_subjects mocked via completed_map
            {task_name: [completed_subject, ...]}
        Returns (executor, all_job_ids, mock_execute).
        """
        executor = make_executor()

        # Mock _execute_single_task to return a single fake job id per task
        mock_execute = MagicMock(side_effect=lambda node, **kwargs: [f"job_{node.name}"])

        def fake_pending(task_name, subjects):
            done = set(completed_map.get(task_name, []))
            return [s for s in subjects if s not in done]

        mock_checker = MagicMock()
        mock_checker.get_pending_subjects.side_effect = fake_pending
        mock_checker.warn_missing_configs.return_value = []

        with patch(CONFIG_PATH, MOCK_CONFIG), \
             patch.object(executor, "_execute_single_task", mock_execute), \
             patch(
                 "neuro_pipeline.pipeline.dag.OutputChecker",
                 return_value=mock_checker,
             ):
            all_job_ids, _ = executor.execute(
                requested_tasks=requested_tasks,
                input_dir="/input",
                output_dir="/output",
                work_dir="/work",
                container_dir="/containers",
                dry_run=False,
                context={"subjects": self.SUBJECTS},
                option_env={"session": "01"},
                project_config=MOCK_PROJECT_CONFIG,
                rest_dependencies=rest_deps,
                dwi_dependencies=dwi_deps,
                resume=True,
                checks_config_path=checks_config_path,
            )

        return executor, all_job_ids, mock_execute, mock_checker

    def test_no_resume_submits_all_subjects(self):
        """Without --resume every task is submitted with the full subject list."""
        executor = make_executor()
        mock_execute = MagicMock(return_value=["job_1"])

        with patch(CONFIG_PATH, MOCK_CONFIG), \
             patch.object(executor, "_execute_single_task", mock_execute):
            executor.execute(
                requested_tasks=["rest_fmriprep_preprocess"],
                input_dir="/in", output_dir="/out", work_dir="/work",
                container_dir="/c", dry_run=False,
                context={"subjects": self.SUBJECTS},
                option_env={"session": "01"},
                project_config=MOCK_PROJECT_CONFIG,
                resume=False,
            )

        _, kwargs = mock_execute.call_args
        submitted = kwargs["subjects"].split(",")
        assert set(submitted) == set(self.SUBJECTS)

    def test_resume_skips_completed_subjects(self):
        """Completed subjects are removed from the submitted subject list."""
        # 001 already done, 002 and 003 still needed
        _, all_job_ids, mock_execute, _ = self._run_execute(
            requested_tasks=["rest_fmriprep_preprocess"],
            completed_map={"rest_fmriprep_preprocess": ["001"]},
        )

        _, kwargs = mock_execute.call_args
        submitted = set(kwargs["subjects"].split(","))
        assert "001" not in submitted
        assert {"002", "003"}.issubset(submitted)

    def test_resume_skips_task_entirely_when_all_complete(self):
        """If all subjects are done for a task, _execute_single_task is never called for it."""
        _, all_job_ids, mock_execute, _ = self._run_execute(
            requested_tasks=["rest_fmriprep_preprocess"],
            completed_map={"rest_fmriprep_preprocess": self.SUBJECTS},
        )

        assert all_job_ids["rest_fmriprep_preprocess"] == []
        mock_execute.assert_not_called()

    def test_resume_partially_complete_task_still_submits(self):
        """At least one pending subject → job is still submitted."""
        _, all_job_ids, mock_execute, _ = self._run_execute(
            requested_tasks=["rest_fmriprep_preprocess"],
            completed_map={"rest_fmriprep_preprocess": ["001", "002"]},  # 003 pending
        )

        mock_execute.assert_called_once()
        assert all_job_ids["rest_fmriprep_preprocess"] != []

    def test_resume_respects_dag_dependency_order(self):
        """
        Scenario: recon_bids complete, preprocess + post_fc pending.
        post_fc must still receive wait_jobs from preprocess job id.
        """
        rest_deps = [("rest_fmriprep_post_fc", ["rest_fmriprep_preprocess"])]

        _, all_job_ids, mock_execute, _ = self._run_execute(
            requested_tasks=["recon_bids", "rest_fmriprep_preprocess", "rest_fmriprep_post_fc"],
            completed_map={"recon_bids": self.SUBJECTS},  # recon fully done
            rest_deps=rest_deps,
        )

        # recon skipped
        assert all_job_ids["recon_bids"] == []

        # preprocess submitted
        assert all_job_ids["rest_fmriprep_preprocess"] != []

        # post_fc submitted with wait_jobs containing preprocess job id
        calls = mock_execute.call_args_list
        post_fc_call = next(
            (c for c in calls if c[1]["node"].name == "rest_fmriprep_post_fc"), None
        )
        assert post_fc_call is not None
        wait_jobs = post_fc_call[1]["wait_jobs"]
        assert any("rest_fmriprep_preprocess" in j for j in wait_jobs)

    def test_resume_task_with_no_checks_config_runs_normally(self):
        """
        If a task has no entry in the checks YAML, warn_missing_configs fires
        but the task should still be submitted with all subjects.
        """
        _, all_job_ids, mock_execute, mock_checker = self._run_execute(
            requested_tasks=["rest_fmriprep_preprocess"],
            # mock_checker.get_pending_subjects returns all subjects (nothing done)
            completed_map={},
        )

        mock_execute.assert_called_once()
        _, kwargs = mock_execute.call_args
        submitted = set(kwargs["subjects"].split(","))
        assert submitted == set(self.SUBJECTS)

    def test_resume_false_does_not_instantiate_checker(self):
        """When resume=False, OutputChecker should never be imported/instantiated."""
        executor = make_executor()
        mock_execute = MagicMock(return_value=["job_1"])

        with patch(CONFIG_PATH, MOCK_CONFIG), \
             patch.object(executor, "_execute_single_task", mock_execute), \
             patch("neuro_pipeline.pipeline.dag.OutputChecker") as mock_cls:
            executor.execute(
                requested_tasks=["rest_fmriprep_preprocess"],
                input_dir="/in", output_dir="/out", work_dir="/work",
                container_dir="/c", dry_run=False,
                context={"subjects": self.SUBJECTS},
                option_env={"session": "01"},
                project_config=MOCK_PROJECT_CONFIG,
                resume=False,
            )

        mock_cls.assert_not_called()

    def test_dry_run_skips_resume_filtering(self):
        """
        dry_run=True + resume=True: resume filtering is bypassed,
        all subjects included in the (notional) submission.
        """
        executor = make_executor()
        mock_execute = MagicMock(return_value=["dry_run_job"])
        mock_checker = MagicMock()
        mock_checker.warn_missing_configs.return_value = []

        with patch(CONFIG_PATH, MOCK_CONFIG), \
             patch.object(executor, "_execute_single_task", mock_execute), \
             patch("neuro_pipeline.pipeline.dag.OutputChecker", return_value=mock_checker):
            executor.execute(
                requested_tasks=["rest_fmriprep_preprocess"],
                input_dir="/in", output_dir="/out", work_dir="/work",
                container_dir="/c", dry_run=True,
                context={"subjects": self.SUBJECTS},
                option_env={"session": "01"},
                project_config=MOCK_PROJECT_CONFIG,
                resume=True,
                checks_config_path="fake.yaml",
            )

        # get_pending_subjects should never be called in dry_run mode
        mock_checker.get_pending_subjects.assert_not_called()
