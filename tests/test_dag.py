"""
test_dag.py

Tests for pipeline/dag.py

Covers:
- DAGExecutor.build_dag          dependency graph construction
- DAGExecutor._topological_sort  correct order + circular-dependency detection
- mriqc_group must follow mriqc_individual
- rest_fmriprep_post_fc must follow rest_fmriprep_preprocess
- task_afni _preprocess depends on afni_ structural task when both requested
- TaskRegistry.expand_tasks      various CLI option combinations
"""

import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import MOCK_CONFIG, MOCK_PROJECT_CONFIG


CONFIG_PATH = "neuro_pipeline.pipeline.utils.config_utils.config"

# ---------------------------------------------------------------------------
# Helper: build a DAGExecutor with the mock config and project config
# ---------------------------------------------------------------------------

def make_executor():
    with patch(CONFIG_PATH, MOCK_CONFIG):
        from neuro_pipeline.pipeline.dag import DAGExecutor
        executor = DAGExecutor(MOCK_CONFIG)
        executor.project_config = MOCK_PROJECT_CONFIG
        return executor


# ===========================================================================
# Topological sort — pure graph logic
# ===========================================================================

class TestTopologicalSort:

    def test_single_node_no_deps(self):
        executor = make_executor()
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.dag import TaskNode
            executor.nodes = {"unzip": TaskNode("unzip", {}, dependencies=set())}
            result = executor._topological_sort()
        assert result == ["unzip"]

    def test_linear_chain(self):
        """A → B → C  must produce [A, B, C]"""
        executor = make_executor()
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.dag import TaskNode
            executor.nodes = {
                "A": TaskNode("A", {}, dependencies=set()),
                "B": TaskNode("B", {}, dependencies={"A"}),
                "C": TaskNode("C", {}, dependencies={"B"}),
            }
            result = executor._topological_sort()
        assert result.index("A") < result.index("B") < result.index("C")

    def test_circular_dependency_raises(self):
        executor = make_executor()
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.dag import TaskNode
            executor.nodes = {
                "X": TaskNode("X", {}, dependencies={"Y"}),
                "Y": TaskNode("Y", {}, dependencies={"X"}),
            }
            with pytest.raises(ValueError, match="Circular dependency"):
                executor._topological_sort()

    def test_diamond_dependency(self):
        """
              root
             /    \\
           left  right
             \\    /
              leaf
        All orderings must have root first and leaf last.
        """
        executor = make_executor()
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.dag import TaskNode
            executor.nodes = {
                "root":  TaskNode("root",  {}, dependencies=set()),
                "left":  TaskNode("left",  {}, dependencies={"root"}),
                "right": TaskNode("right", {}, dependencies={"root"}),
                "leaf":  TaskNode("leaf",  {}, dependencies={"left", "right"}),
            }
            result = executor._topological_sort()
        assert result[0] == "root"
        assert result[-1] == "leaf"


# ===========================================================================
# build_dag — dependency wiring for real tasks
# ===========================================================================

class TestBuildDAG:

    def _build(self, tasks, rest_deps=None, dwi_deps=None):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            executor = make_executor()
            order = executor.build_dag(tasks, rest_deps, dwi_deps)
            return executor, order

    # --- prep chain ---------------------------------------------------------

    def test_unzip_has_no_deps(self):
        executor, order = self._build(["unzip"])
        assert executor.nodes["unzip"].dependencies == set()

    def test_recon_bids_depends_on_unzip_when_both_requested(self):
        executor, order = self._build(["unzip", "recon_bids"])
        assert "unzip" in executor.nodes["recon_bids"].dependencies
        assert order.index("unzip") < order.index("recon_bids")

    def test_recon_bids_no_dep_when_unzip_not_requested(self):
        """If user only asks for recon_bids, no unzip dep should be wired."""
        executor, order = self._build(["recon_bids"])
        assert "unzip" not in executor.nodes["recon_bids"].dependencies

    # --- mriqc group / individual -------------------------------------------

    def test_mriqc_group_follows_individual_when_both_requested(self):
        executor, order = self._build(["mriqc_individual", "mriqc_group"])
        assert "mriqc_individual" in executor.nodes["mriqc_group"].dependencies
        assert order.index("mriqc_individual") < order.index("mriqc_group")

    def test_mriqc_group_alone_has_no_individual_dep(self):
        executor, order = self._build(["mriqc_group"])
        assert "mriqc_individual" not in executor.nodes["mriqc_group"].dependencies

    # --- rest pipeline -------------------------------------------------------

    def test_rest_post_fc_depends_on_preprocess(self):
        rest_deps = [("rest_fmriprep_post_fc", ["rest_fmriprep_preprocess"])]
        executor, order = self._build(
            ["rest_fmriprep_preprocess", "rest_fmriprep_post_fc"],
            rest_deps=rest_deps,
        )
        assert "rest_fmriprep_preprocess" in executor.nodes["rest_fmriprep_post_fc"].dependencies
        assert order.index("rest_fmriprep_preprocess") < order.index("rest_fmriprep_post_fc")

    # --- DWI pipeline -------------------------------------------------------

    def test_dwi_post_depends_on_dwi_preprocess(self):
        dwi_deps = [("dwi_post", ["dwi_preprocess"])]
        executor, order = self._build(
            ["dwi_preprocess", "dwi_post"],
            dwi_deps=dwi_deps,
        )
        assert "dwi_preprocess" in executor.nodes["dwi_post"].dependencies
        assert order.index("dwi_preprocess") < order.index("dwi_post")

    def test_dwi_preprocess_no_dep_when_dwi_post_not_requested(self):
        """dwi_preprocess alone should have no dwi_post dependency wired."""
        executor, order = self._build(["dwi_preprocess"])
        assert "dwi_post" not in executor.nodes["dwi_preprocess"].dependencies

    def test_dwi_preprocess_depends_on_recon_bids_when_both_requested(self):
        executor, order = self._build(["recon_bids", "dwi_preprocess"])
        assert "recon_bids" in executor.nodes["dwi_preprocess"].dependencies
        assert order.index("recon_bids") < order.index("dwi_preprocess")

    def test_dwi_deps_independent_from_rest_deps(self):
        """DWI and rest dependencies must not interfere with each other."""
        rest_deps = [("rest_fmriprep_post_fc", ["rest_fmriprep_preprocess"])]
        dwi_deps = [("dwi_post", ["dwi_preprocess"])]
        executor, order = self._build(
            ["rest_fmriprep_preprocess", "rest_fmriprep_post_fc", "dwi_preprocess", "dwi_post"],
            rest_deps=rest_deps,
            dwi_deps=dwi_deps,
        )
        assert "rest_fmriprep_preprocess" in executor.nodes["rest_fmriprep_post_fc"].dependencies
        assert "dwi_preprocess" in executor.nodes["dwi_post"].dependencies
        assert order.index("rest_fmriprep_preprocess") < order.index("rest_fmriprep_post_fc")
        assert order.index("dwi_preprocess") < order.index("dwi_post")

    # --- task_afni + structural ----------------------------------------------

    def test_cards_preprocess_depends_on_afni_volume_when_both_requested(self):
        executor, order = self._build(["afni_volume", "cards_preprocess"])
        assert "afni_volume" in executor.nodes["cards_preprocess"].dependencies
        assert order.index("afni_volume") < order.index("cards_preprocess")

    def test_cards_preprocess_no_structural_dep_when_not_requested(self):
        executor, order = self._build(["cards_preprocess"])
        assert "afni_volume" not in executor.nodes.get("cards_preprocess", MagicMock()).dependencies

    # --- execution order is complete ----------------------------------------

    def test_all_requested_tasks_appear_in_order(self):
        tasks = ["unzip", "recon_bids", "mriqc_individual", "mriqc_group"]
        executor, order = self._build(tasks)
        for t in tasks:
            assert t in order


# ===========================================================================
# TaskRegistry.expand_tasks — CLI option → task list
# ===========================================================================

class TestTaskRegistry:

    def _registry(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.dag import TaskRegistry
            return TaskRegistry()

    # --- prep ---------------------------------------------------------------

    def test_prep_unzip(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import PrepChoice
            r = self._registry()
            tasks = r.expand_tasks(prep=PrepChoice.unzip)
        assert tasks == ["unzip"]

    def test_prep_recon(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import PrepChoice
            r = self._registry()
            tasks = r.expand_tasks(prep=PrepChoice.recon)
        assert tasks == ["recon_bids"]

    def test_prep_unzip_recon_expands_to_both(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import PrepChoice
            r = self._registry()
            tasks = r.expand_tasks(prep=PrepChoice.unzip_recon)
        assert "unzip" in tasks
        assert "recon_bids" in tasks

    # --- structural ---------------------------------------------------------

    def test_structural_volume(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import StructuralChoice
            r = self._registry()
            tasks = r.expand_tasks(structural=StructuralChoice.volume)
        assert "afni_volume" in tasks

    # --- mriqc --------------------------------------------------------------

    def test_mriqc_individual(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import MRIQCChoice
            r = self._registry()
            tasks = r.expand_tasks(mriqc=MRIQCChoice.individual)
        assert tasks == ["mriqc_individual"]

    def test_mriqc_group(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import MRIQCChoice
            r = self._registry()
            tasks = r.expand_tasks(mriqc=MRIQCChoice.group)
        assert tasks == ["mriqc_group"]

    def test_mriqc_all_expands_to_both(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import MRIQCChoice
            r = self._registry()
            tasks = r.expand_tasks(mriqc=MRIQCChoice.all)
        assert "mriqc_individual" in tasks
        assert "mriqc_group" in tasks

    # --- rest ---------------------------------------------------------------

    def test_rest_prep_fmriprep(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import RestPrepChoice
            r = self._registry()
            tasks = r.expand_tasks(rest_prep=RestPrepChoice.fmriprep)
        assert "rest_fmriprep_preprocess" in tasks

    def test_rest_post_xcpd(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import RestPostChoice
            r = self._registry()
            tasks = r.expand_tasks(rest_post=RestPostChoice.xcpd)
        assert "rest_fmriprep_post_fc" in tasks

    def test_rest_prep_and_post_together(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import RestPrepChoice, RestPostChoice
            r = self._registry()
            tasks = r.expand_tasks(
                rest_prep=RestPrepChoice.fmriprep,
                rest_post=RestPostChoice.xcpd,
            )
        assert "rest_fmriprep_preprocess" in tasks
        assert "rest_fmriprep_post_fc" in tasks

    # --- task_prep (the key CLI flow) ---------------------------------------

    def test_task_prep_cards(self):
        """--task-prep cards  should include cards_preprocess in the plan."""
        with patch(CONFIG_PATH, MOCK_CONFIG):
            r = self._registry()
            tasks = r.expand_tasks(task_prep=["cards_preprocess"])
        assert "cards_preprocess" in tasks

    def test_task_prep_multiple(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            r = self._registry()
            tasks = r.expand_tasks(task_prep=["cards_preprocess", "kidvid_preprocess"])
        assert "cards_preprocess" in tasks
        assert "kidvid_preprocess" in tasks

    # --- no tasks -----------------------------------------------------------

    def test_no_options_returns_empty(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            r = self._registry()
            tasks = r.expand_tasks()
        assert tasks == []

    # --- DWI ----------------------------------------------------------------

    def test_dwi_prep_qsiprep(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import DwiPrepChoice
            r = self._registry()
            tasks = r.expand_tasks(dwi_prep=DwiPrepChoice.qsiprep)
        assert "dwi_preprocess" in tasks

    def test_dwi_post_qsirecon(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import DwiPostChoice
            r = self._registry()
            tasks = r.expand_tasks(dwi_post=DwiPostChoice.qsirecon)
        assert "dwi_post" in tasks

    def test_dwi_prep_and_post_together(self):
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import DwiPrepChoice, DwiPostChoice
            r = self._registry()
            tasks = r.expand_tasks(
                dwi_prep=DwiPrepChoice.qsiprep,
                dwi_post=DwiPostChoice.qsirecon,
            )
        assert "dwi_preprocess" in tasks
        assert "dwi_post" in tasks

    def test_dwi_post_without_prep_still_expands(self):
        """dwi_post can be requested alone; dependency enforcement is DAG's job."""
        with patch(CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.utils.config_utils import DwiPostChoice
            r = self._registry()
            tasks = r.expand_tasks(dwi_post=DwiPostChoice.qsirecon)
        assert "dwi_post" in tasks
        assert "dwi_preprocess" not in tasks