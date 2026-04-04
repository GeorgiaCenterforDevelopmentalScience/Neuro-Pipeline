"""
test_dag_visualization.py

Tests for build_dag_elements() in analysis_control.py.
Verifies that the correct Cytoscape nodes and edges are generated
for different pipeline selections.
"""

import pytest
from neuro_pipeline.interface.components.analysis_control import build_dag_elements


def node_ids(elements):
    return {e["data"]["id"] for e in elements if "source" not in e["data"]}

def edge_pairs(elements):
    return {(e["data"]["source"], e["data"]["target"])
            for e in elements if "source" in e["data"]}


class TestBuildDagElementsEmpty:

    def test_no_selection_returns_empty(self):
        elements = build_dag_elements(
            prep_option="none", intermed_value="none",
            bids_prep=[], bids_post=[],
            staged_prep=[], staged_post=[],
            mriqc_option="none",
        )
        assert elements == []


class TestPrepNodes:

    def test_unzip_only(self):
        elements = build_dag_elements(
            "unzip", "none", [], [], [], [], "none"
        )
        assert "unzip" in node_ids(elements)
        assert "recon_bids" not in node_ids(elements)

    def test_recon_only(self):
        elements = build_dag_elements(
            "recon", "none", [], [], [], [], "none"
        )
        assert "recon_bids" in node_ids(elements)
        assert "unzip" not in node_ids(elements)

    def test_unzip_recon_creates_edge(self):
        elements = build_dag_elements(
            "unzip_recon", "none", [], [], [], [], "none"
        )
        ids = node_ids(elements)
        assert "unzip" in ids
        assert "recon_bids" in ids
        assert ("unzip", "recon_bids") in edge_pairs(elements)


class TestIntermedNodes:

    def test_intermed_node_created(self):
        elements = build_dag_elements(
            "recon", "afni_volume", [], [], [], [], "none"
        )
        assert "intermed" in node_ids(elements)

    def test_recon_to_intermed_edge(self):
        elements = build_dag_elements(
            "recon", "afni_volume", [], [], [], [], "none"
        )
        assert ("recon_bids", "intermed") in edge_pairs(elements)

    def test_no_intermed_node_when_none(self):
        elements = build_dag_elements(
            "recon", "none", [], [], [], [], "none"
        )
        assert "intermed" not in node_ids(elements)


class TestBIDSPipelines:

    def test_bids_prep_node_created(self):
        elements = build_dag_elements(
            "recon", "none", ["rest"], [], [], [], "none"
        )
        assert "bids_prep_rest" in node_ids(elements)

    def test_recon_to_bids_prep_edge(self):
        elements = build_dag_elements(
            "recon", "none", ["rest"], [], [], [], "none"
        )
        assert ("recon_bids", "bids_prep_rest") in edge_pairs(elements)

    def test_bids_post_node_created(self):
        elements = build_dag_elements(
            "recon", "none", [], ["rest"], [], [], "none"
        )
        assert "bids_post_rest" in node_ids(elements)

    def test_bids_prep_to_post_edge_when_both_selected(self):
        elements = build_dag_elements(
            "recon", "none", ["rest"], ["rest"], [], [], "none"
        )
        assert ("bids_prep_rest", "bids_post_rest") in edge_pairs(elements)

    def test_bids_post_no_prep_edge_when_prep_not_selected(self):
        elements = build_dag_elements(
            "recon", "none", [], ["rest"], [], [], "none"
        )
        assert ("bids_prep_rest", "bids_post_rest") not in edge_pairs(elements)


class TestStagedPipelines:

    def test_staged_prep_node_created(self):
        elements = build_dag_elements(
            "none", "none", [], [], ["cards"], [], "none"
        )
        assert "staged_prep_cards" in node_ids(elements)

    def test_intermed_to_staged_prep_edge(self):
        elements = build_dag_elements(
            "recon", "afni_volume", [], [], ["cards"], [], "none"
        )
        assert ("intermed", "staged_prep_cards") in edge_pairs(elements)

    def test_staged_prep_no_intermed_edge_when_intermed_absent(self):
        elements = build_dag_elements(
            "none", "none", [], [], ["cards"], [], "none"
        )
        assert "intermed" not in node_ids(elements)
        assert all(e["data"].get("target") != "staged_prep_cards"
                   or e["data"].get("source") != "intermed"
                   for e in elements if "source" in e["data"])

    def test_staged_prep_to_post_edge(self):
        elements = build_dag_elements(
            "none", "none", [], [], ["cards"], ["cards"], "none"
        )
        assert ("staged_prep_cards", "staged_post_cards") in edge_pairs(elements)


class TestMRIQCNodes:

    def test_mriqc_individual_node(self):
        elements = build_dag_elements(
            "recon", "none", [], [], [], [], "individual"
        )
        assert "mriqc_indiv" in node_ids(elements)

    def test_recon_to_mriqc_individual_edge(self):
        elements = build_dag_elements(
            "recon", "none", [], [], [], [], "individual"
        )
        assert ("recon_bids", "mriqc_indiv") in edge_pairs(elements)

    def test_mriqc_group_only(self):
        elements = build_dag_elements(
            "recon", "none", [], [], [], [], "group"
        )
        ids = node_ids(elements)
        assert "mriqc_group" in ids
        assert "mriqc_indiv" not in ids

    def test_mriqc_all_creates_chain(self):
        elements = build_dag_elements(
            "recon", "none", [], [], [], [], "all"
        )
        ids = node_ids(elements)
        assert "mriqc_indiv" in ids
        assert "mriqc_group" in ids
        assert ("mriqc_indiv", "mriqc_group") in edge_pairs(elements)


class TestFullPipelineSelection:

    def test_full_pipeline_has_all_expected_nodes(self):
        elements = build_dag_elements(
            prep_option="unzip_recon",
            intermed_value="afni_volume",
            bids_prep=["rest"],
            bids_post=["rest"],
            staged_prep=["cards"],
            staged_post=["cards"],
            mriqc_option="all",
        )
        ids = node_ids(elements)
        assert "unzip" in ids
        assert "recon_bids" in ids
        assert "intermed" in ids
        assert "bids_prep_rest" in ids
        assert "bids_post_rest" in ids
        assert "staged_prep_cards" in ids
        assert "staged_post_cards" in ids
        assert "mriqc_indiv" in ids
        assert "mriqc_group" in ids

    def test_full_pipeline_edge_count_reasonable(self):
        elements = build_dag_elements(
            "unzip_recon", "afni_volume",
            ["rest"], ["rest"], ["cards"], ["cards"], "all",
        )
        edges = edge_pairs(elements)
        assert len(edges) >= 6
