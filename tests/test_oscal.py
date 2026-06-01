"""Tests for the OSCAL 1.1.2-shaped catalog export."""

from __future__ import annotations

from regrails.oscal import build_catalog


def test_catalog_top_level_shape() -> None:
    c = build_catalog()
    assert set(c.keys()) == {"catalog"}
    cat = c["catalog"]
    assert cat["metadata"]["oscal-version"] == "1.1.2"
    assert cat["metadata"]["title"]
    assert len(cat["uuid"]) == 36


def test_thirty_seven_controls() -> None:
    cat = build_catalog()["catalog"]
    controls = [ctl for g in cat["groups"] for ctl in g["controls"]]
    assert len(controls) == 37


def test_two_framework_groups() -> None:
    cat = build_catalog()["catalog"]
    assert {g["title"] for g in cat["groups"]} == {"FERPA", "Title IV"}


def test_every_control_has_reference_statement_framework() -> None:
    cat = build_catalog()["catalog"]
    for g in cat["groups"]:
        for ctl in g["controls"]:
            assert any(lk["rel"] == "reference" and lk["href"] for lk in ctl["links"])
            assert any(p["name"] == "statement" and p["prose"] for p in ctl["parts"])
            assert any(p["name"] == "framework" for p in ctl["props"])


def test_back_matter_binds_eight_section_hashes() -> None:
    cat = build_catalog()["catalog"]
    resources = cat["back-matter"]["resources"]
    assert len(resources) == 8
    for r in resources:
        h = r["rlinks"][0]["hashes"][0]
        assert h["algorithm"] == "SHA-256"
        assert len(h["value"]) == 64


def test_uuids_are_deterministic() -> None:
    assert build_catalog()["catalog"]["uuid"] == build_catalog()["catalog"]["uuid"]
