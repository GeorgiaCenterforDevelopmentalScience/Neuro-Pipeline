"""
test_ui_layout.py

Smoke tests for the Dash layout components.
These tests verify that layout functions return components without crashing
and that required component IDs are present in the rendered tree.
No browser or Selenium required.
"""

import pytest
from dash import html, dcc
import dash_bootstrap_components as dbc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_ids(component, ids=None):
    """Recursively collect all component IDs from a Dash component tree."""
    if ids is None:
        ids = set()

    if hasattr(component, "id") and component.id is not None:
        ids.add(component.id)

    children = getattr(component, "children", None)
    if children is None:
        return ids

    if isinstance(children, (list, tuple)):
        for child in children:
            collect_ids(child, ids)
    elif hasattr(children, "id") or hasattr(children, "children"):
        collect_ids(children, ids)

    return ids


# ---------------------------------------------------------------------------
# Job Monitor layout
# ---------------------------------------------------------------------------

class TestJobMonitorLayout:

    @pytest.fixture(autouse=True)
    def layout(self):
        from neuro_pipeline.interface.components.job_monitor import create_job_monitor_layout
        self.component = create_job_monitor_layout()
        self.ids = collect_ids(self.component)

    def test_returns_container(self):
        assert isinstance(self.component, dbc.Container)

    def test_database_config_ids_present(self):
        for expected_id in ("db-path", "work-dir-input"):
            assert expected_id in self.ids, f"Missing component id: {expected_id}"

    def test_merge_logs_ids_present(self):
        assert "merge-logs-btn" in self.ids
        assert "merge-logs-result" in self.ids

    def test_output_check_ids_present(self):
        for expected_id in (
            "check-project-name",
            "check-subjects",
            "check-task-filter",
            "check-session",
            "check-prefix",
            "run-output-check-btn",
            "export-check-csv-btn",
            "output-check-result",
        ):
            assert expected_id in self.ids, f"Missing component id: {expected_id}"

    def test_query_config_ids_present(self):
        for expected_id in (
            "query-type",
            "subject-filter",
            "session-filter",
            "task-filter",
            "status-filter",
            "date-range",
            "execute-sql-query-btn",
            "export-csv-btn",
            "export-status",
        ):
            assert expected_id in self.ids, f"Missing component id: {expected_id}"

    def test_results_display_ids_present(self):
        assert "sql-query-results" in self.ids
        assert "sql-query-charts" in self.ids

    def test_generate_report_ids_present(self):
        for expected_id in (
            "report-project",
            "report-session",
            "report-check-results",
            "report-output-path",
            "generate-report-btn",
            "generate-report-result",
        ):
            assert expected_id in self.ids, f"Missing component id: {expected_id}"

    def test_wrapper_inspector_ids_present(self):
        for expected_id in (
            "wrapper-task-filter",
            "wrapper-job-id",
            "load-wrapper-btn",
            "wrapper-inspect-result",
        ):
            assert expected_id in self.ids, f"Missing component id: {expected_id}"


# ---------------------------------------------------------------------------
# Analysis Control layout
# ---------------------------------------------------------------------------

class TestAnalysisControlLayout:

    def test_returns_component(self):
        from neuro_pipeline.interface.components.analysis_control import create_analysis_control_layout
        component = create_analysis_control_layout()
        assert component is not None

    def test_does_not_crash(self):
        from neuro_pipeline.interface.components.analysis_control import create_analysis_control_layout
        # Should not raise
        create_analysis_control_layout()


# ---------------------------------------------------------------------------
# App routing callback
# ---------------------------------------------------------------------------

class TestAppRouting:

    @pytest.fixture(autouse=True)
    def display_page(self):
        # Import after app is constructed (callbacks registered)
        import neuro_pipeline.interface.app as app_module
        self._display_page = app_module.display_page

    def test_root_returns_analysis_control(self):
        component, _ = self._display_page("/")
        assert component is not None

    def test_analysis_control_route(self):
        component, _ = self._display_page("/analysis-control")
        assert component is not None

    def test_job_monitor_route_returns_container(self):
        component, _ = self._display_page("/job-monitor")
        assert isinstance(component, dbc.Container)
        assert "db-path" in collect_ids(component)

    def test_project_config_route(self):
        component, _ = self._display_page("/project-config")
        assert component is not None

    def test_unknown_route_returns_default(self):
        component, _ = self._display_page("/nonexistent-page")
        assert component is not None
