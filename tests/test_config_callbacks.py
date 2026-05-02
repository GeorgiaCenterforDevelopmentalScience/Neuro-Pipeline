import os
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

import dash_bootstrap_components as dbc

_CB_MOD = "neuro_pipeline.interface.callbacks.config_callbacks"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_triggered(component_id):
    ctx = MagicMock()
    ctx.triggered = [{"prop_id": f"{component_id}.n_clicks", "value": 1}]
    return ctx


def _get_alert_color(component):
    assert isinstance(component, dbc.Alert), f"Expected Alert, got {type(component)}"
    return component.color


# ---------------------------------------------------------------------------
# _save_file / _load_file unit tests
# ---------------------------------------------------------------------------

class TestSaveAndLoadFile:

    def test_save_creates_file(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import _save_file
        dest = tmp_path / "out" / "test.yaml"
        result = _save_file(str(dest), "key: value")
        assert _get_alert_color(result) == "success"
        assert dest.exists()
        assert dest.read_text() == "key: value"

    def test_save_returns_error_on_bad_path(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import _save_file
        # Use an existing file as if it were a directory
        existing_file = tmp_path / "blockfile.txt"
        existing_file.write_text("x")
        result = _save_file(str(existing_file / "sub" / "c.yaml"), "key: value")
        assert _get_alert_color(result) == "danger"

    def test_save_warns_on_empty_path(self):
        from neuro_pipeline.interface.callbacks.config_callbacks import _save_file
        result = _save_file("", "key: value")
        assert _get_alert_color(result) == "warning"

    def test_save_warns_on_none_path(self):
        from neuro_pipeline.interface.callbacks.config_callbacks import _save_file
        result = _save_file(None, "key: value")
        assert _get_alert_color(result) == "warning"

    def test_load_reads_existing_file(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import _load_file
        f = tmp_path / "test.yaml"
        f.write_text("hello: world")
        content, err = _load_file(str(f))
        assert err is None
        assert content == "hello: world"

    def test_load_returns_error_for_missing_file(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import _load_file
        _, err = _load_file(str(tmp_path / "nonexistent.yaml"))
        assert err is not None
        assert "not found" in err.lower()

    def test_load_returns_error_for_empty_path(self):
        from neuro_pipeline.interface.callbacks.config_callbacks import _load_file
        _, err = _load_file("")
        assert err is not None


# ---------------------------------------------------------------------------
# generate_project_config integration
# ---------------------------------------------------------------------------

class TestGenerateTemplate:

    def test_generates_yaml_file(self, tmp_path):
        from neuro_pipeline.pipeline.utils.generate_project_config import generate_project_config
        out_dir = tmp_path / "project_config"
        generate_project_config("myproject", str(out_dir))
        config_file = out_dir / "myproject_config.yaml"
        assert config_file.exists()
        data = yaml.safe_load(config_file.read_text())
        assert "tasks" in data
        assert "prefix" in data

    def test_generated_yaml_is_loadable(self, tmp_path):
        from neuro_pipeline.pipeline.utils.generate_project_config import generate_project_config
        from neuro_pipeline.interface.callbacks.config_callbacks import _load_file
        out_dir = tmp_path / "project_config"
        generate_project_config("testproj", str(out_dir))
        content, err = _load_file(str(out_dir / "testproj_config.yaml"))
        assert err is None
        assert "testproj" in content

    def test_callback_generates_and_shows_success(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import generate_new_config_callback
        config_root = tmp_path / "config"

        with patch(f"{_CB_MOD}._CONFIG_DIR", config_root):
            result = generate_new_config_callback(1, "demo")

        assert _get_alert_color(result) == "success"
        assert (config_root / "project_config" / "demo_config.yaml").exists()

    def test_callback_warns_on_missing_project_name(self):
        from neuro_pipeline.interface.callbacks.config_callbacks import generate_new_config_callback
        result = generate_new_config_callback(1, "")
        assert _get_alert_color(result) == "warning"

    def test_callback_warns_on_none_project_name(self):
        from neuro_pipeline.interface.callbacks.config_callbacks import generate_new_config_callback
        result = generate_new_config_callback(1, None)
        assert _get_alert_color(result) == "warning"


# ---------------------------------------------------------------------------
# load_config_callback
# ---------------------------------------------------------------------------

class TestLoadConfigCallback:

    def test_loads_existing_file_into_editor(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import load_config_callback
        config_root = tmp_path / "config"
        yaml_file = config_root / "project_config" / "test_config.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text("prefix: sub-\ntasks: {}")

        with patch(f"{_CB_MOD}._CONFIG_DIR", config_root):
            result = load_config_callback(1, "test")

        assert "prefix: sub-" in result

    def test_returns_error_comment_for_missing_file(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import load_config_callback
        with patch(f"{_CB_MOD}._CONFIG_DIR", tmp_path / "config"):
            result = load_config_callback(1, "missing")
        assert result.startswith("# ")

    def test_returns_error_comment_for_no_project_name(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import load_config_callback
        with patch(f"{_CB_MOD}._CONFIG_DIR", tmp_path / "config"):
            result = load_config_callback(1, "")
        assert result.startswith("# ")

    def test_returns_empty_string_on_initial_call(self, tmp_path):
        from neuro_pipeline.interface.callbacks.config_callbacks import load_config_callback
        with patch(f"{_CB_MOD}._CONFIG_DIR", tmp_path / "config"):
            result = load_config_callback(None, "test")
        assert result == ""


# ---------------------------------------------------------------------------
# save_config_callback
# ---------------------------------------------------------------------------

class TestSaveConfigCallback:

    def _call_save(self, tmp_path, yaml_content, project_name, trigger="save-config-btn"):
        from neuro_pipeline.interface.callbacks.config_callbacks import save_config_callback
        mock_ctx = _make_triggered(trigger)
        with patch(f"{_CB_MOD}._CONFIG_DIR", tmp_path / "config"), \
             patch(f"{_CB_MOD}.callback_context", mock_ctx):
            return save_config_callback(1, None, project_name, yaml_content)

    def test_saves_valid_yaml(self, tmp_path):
        content = "prefix: sub-\ntasks: {}"
        result = self._call_save(tmp_path, content, "save_test")
        assert _get_alert_color(result) == "success"
        saved = (tmp_path / "config" / "project_config" / "save_test_config.yaml").read_text()
        assert "prefix" in saved

    def test_warns_on_empty_editor(self, tmp_path):
        result = self._call_save(tmp_path, "", "x")
        assert _get_alert_color(result) == "warning"

    def test_warns_on_none_content(self, tmp_path):
        result = self._call_save(tmp_path, None, "x")
        assert _get_alert_color(result) == "warning"

    def test_warns_on_missing_project_name(self, tmp_path):
        result = self._call_save(tmp_path, "key: value", "")
        assert _get_alert_color(result) == "warning"

    def test_errors_on_invalid_yaml(self, tmp_path):
        result = self._call_save(tmp_path, "key: [unclosed", "x")
        assert _get_alert_color(result) == "danger"

    def test_validate_does_not_write_file(self, tmp_path):
        result = self._call_save(tmp_path, "key: value", "nowrite", trigger="validate-config-btn")
        assert _get_alert_color(result) == "success"
        assert not (tmp_path / "config" / "project_config" / "nowrite_config.yaml").exists()

    def test_roundtrip_generate_load_save(self, tmp_path):
        """Full workflow: generate template → load → save under new project name."""
        from neuro_pipeline.pipeline.utils.generate_project_config import generate_project_config
        from neuro_pipeline.interface.callbacks.config_callbacks import load_config_callback, save_config_callback

        config_root = tmp_path / "config"
        generate_project_config("roundtrip", str(config_root / "project_config"))

        with patch(f"{_CB_MOD}._CONFIG_DIR", config_root):
            editor_content = load_config_callback(1, "roundtrip")

        assert "roundtrip" in editor_content
        assert not editor_content.startswith("# ")

        mock_ctx = _make_triggered("save-config-btn")
        with patch(f"{_CB_MOD}._CONFIG_DIR", config_root), \
             patch(f"{_CB_MOD}.callback_context", mock_ctx):
            save_result = save_config_callback(1, None, "roundtrip_copy", editor_content)

        assert _get_alert_color(save_result) == "success"
        saved_file = config_root / "project_config" / "roundtrip_copy_config.yaml"
        saved_data = yaml.safe_load(saved_file.read_text())
        assert saved_data["prefix"] == "sub-"
        assert "tasks" in saved_data
