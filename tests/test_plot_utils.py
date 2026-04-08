"""
test_plot_utils.py

Unit tests for the four Plotly chart factory functions in
neuro_pipeline.interface.utils.plot_utils.

All functions follow the same contract:
  - Accept a DataFrame
  - Always return a plotly.graph_objects.Figure (never raise)
  - Return a Figure with an annotation when data is missing or invalid
"""

import pytest
import pandas as pd
from plotly.graph_objects import Figure


def _is_figure(obj):
    return isinstance(obj, Figure)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def job_status_df():
    return pd.DataFrame([
        {"subject": "001", "task_name": "rest_prep",   "status": "SUCCESS", "start_time": "2025-01-06", "duration_hours": 2.5},
        {"subject": "002", "task_name": "rest_prep",   "status": "FAILED",  "start_time": "2025-01-07", "duration_hours": 0.3},
        {"subject": "003", "task_name": "volume", "status": "SUCCESS", "start_time": "2025-01-13", "duration_hours": 1.8},
        {"subject": "004", "task_name": "volume", "status": "RUNNING", "start_time": "2025-01-14", "duration_hours": 0.5},
    ])


@pytest.fixture
def command_outputs_df():
    return pd.DataFrame([
        {"subject": "001", "task_name": "rest_prep", "exit_code": 0},
        {"subject": "002", "task_name": "rest_prep", "exit_code": 1},
        {"subject": "003", "task_name": "rest_prep", "exit_code": 0},
        {"subject": "004", "task_name": "rest_prep", "exit_code": 2},
    ])


# ---------------------------------------------------------------------------
# create_timeline_chart
# ---------------------------------------------------------------------------

class TestCreateTimelineChart:

    def test_returns_figure_for_valid_data(self, job_status_df):
        from neuro_pipeline.interface.utils.plot_utils import create_timeline_chart
        fig = create_timeline_chart(job_status_df)
        assert _is_figure(fig)

    def test_returns_figure_for_empty_df(self):
        from neuro_pipeline.interface.utils.plot_utils import create_timeline_chart
        fig = create_timeline_chart(pd.DataFrame())
        assert _is_figure(fig)

    def test_returns_figure_when_start_time_missing(self):
        from neuro_pipeline.interface.utils.plot_utils import create_timeline_chart
        df = pd.DataFrame([{"subject": "001", "status": "SUCCESS"}])
        fig = create_timeline_chart(df)
        assert _is_figure(fig)

    def test_returns_figure_for_invalid_dates(self):
        from neuro_pipeline.interface.utils.plot_utils import create_timeline_chart
        df = pd.DataFrame([{"start_time": "not-a-date"}, {"start_time": "also-bad"}])
        fig = create_timeline_chart(df)
        assert _is_figure(fig)

    def test_has_at_least_one_trace_for_valid_data(self, job_status_df):
        from neuro_pipeline.interface.utils.plot_utils import create_timeline_chart
        fig = create_timeline_chart(job_status_df)
        assert len(fig.data) >= 1

    def test_single_date_does_not_crash(self):
        from neuro_pipeline.interface.utils.plot_utils import create_timeline_chart
        df = pd.DataFrame([{"start_time": "2025-03-01", "status": "SUCCESS"}])
        fig = create_timeline_chart(df)
        assert _is_figure(fig)


# ---------------------------------------------------------------------------
# create_status_donut
# ---------------------------------------------------------------------------

class TestCreateStatusDonut:

    def test_returns_figure_for_valid_data(self, job_status_df):
        from neuro_pipeline.interface.utils.plot_utils import create_status_donut
        fig = create_status_donut(job_status_df)
        assert _is_figure(fig)

    def test_returns_figure_for_empty_df(self):
        from neuro_pipeline.interface.utils.plot_utils import create_status_donut
        fig = create_status_donut(pd.DataFrame())
        assert _is_figure(fig)

    def test_returns_figure_when_status_missing(self):
        from neuro_pipeline.interface.utils.plot_utils import create_status_donut
        df = pd.DataFrame([{"subject": "001"}])
        fig = create_status_donut(df)
        assert _is_figure(fig)

    def test_has_pie_trace_for_valid_data(self, job_status_df):
        from neuro_pipeline.interface.utils.plot_utils import create_status_donut
        fig = create_status_donut(job_status_df)
        assert len(fig.data) >= 1
        assert fig.data[0].type == "pie"

    def test_all_same_status(self):
        from neuro_pipeline.interface.utils.plot_utils import create_status_donut
        df = pd.DataFrame([{"status": "SUCCESS"}] * 5)
        fig = create_status_donut(df)
        assert _is_figure(fig)


# ---------------------------------------------------------------------------
# create_duration_radar
# ---------------------------------------------------------------------------

class TestCreateDurationRadar:

    def test_returns_figure_for_valid_data(self, job_status_df):
        from neuro_pipeline.interface.utils.plot_utils import create_duration_radar
        fig = create_duration_radar(job_status_df)
        assert _is_figure(fig)

    def test_returns_figure_for_empty_df(self):
        from neuro_pipeline.interface.utils.plot_utils import create_duration_radar
        fig = create_duration_radar(pd.DataFrame())
        assert _is_figure(fig)

    def test_returns_figure_when_columns_missing(self):
        from neuro_pipeline.interface.utils.plot_utils import create_duration_radar
        df = pd.DataFrame([{"subject": "001", "status": "SUCCESS"}])
        fig = create_duration_radar(df)
        assert _is_figure(fig)

    def test_returns_figure_when_all_durations_zero(self):
        from neuro_pipeline.interface.utils.plot_utils import create_duration_radar
        df = pd.DataFrame([
            {"task_name": "task_a", "duration_hours": 0},
            {"task_name": "task_b", "duration_hours": 0},
        ])
        fig = create_duration_radar(df)
        assert _is_figure(fig)

    def test_single_task_does_not_crash(self):
        from neuro_pipeline.interface.utils.plot_utils import create_duration_radar
        df = pd.DataFrame([{"task_name": "only_task", "duration_hours": 3.0}])
        fig = create_duration_radar(df)
        assert _is_figure(fig)


# ---------------------------------------------------------------------------
# create_exit_code_bar
# ---------------------------------------------------------------------------

class TestCreateExitCodeBar:

    def test_returns_figure_for_valid_data(self, command_outputs_df):
        from neuro_pipeline.interface.utils.plot_utils import create_exit_code_bar
        fig = create_exit_code_bar(command_outputs_df)
        assert _is_figure(fig)

    def test_returns_figure_for_empty_df(self):
        from neuro_pipeline.interface.utils.plot_utils import create_exit_code_bar
        fig = create_exit_code_bar(pd.DataFrame())
        assert _is_figure(fig)

    def test_returns_figure_when_exit_code_missing(self):
        from neuro_pipeline.interface.utils.plot_utils import create_exit_code_bar
        df = pd.DataFrame([{"subject": "001"}])
        fig = create_exit_code_bar(df)
        assert _is_figure(fig)

    def test_has_bar_trace_for_valid_data(self, command_outputs_df):
        from neuro_pipeline.interface.utils.plot_utils import create_exit_code_bar
        fig = create_exit_code_bar(command_outputs_df)
        assert len(fig.data) >= 1
        assert fig.data[0].type == "bar"

    def test_all_success_codes(self):
        from neuro_pipeline.interface.utils.plot_utils import create_exit_code_bar
        df = pd.DataFrame([{"exit_code": 0}] * 10)
        fig = create_exit_code_bar(df)
        assert _is_figure(fig)
