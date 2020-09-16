import datetime
import pathlib
import textwrap

from pytest import raises

import publish


EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"
EXAMPLE_2_DIRECTORY = pathlib.Path(__file__).parent / "example_2"
EXAMPLE_3_DIRECTORY = pathlib.Path(__file__).parent / "example_3"


def test_discover_finds_collections():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections.keys() == {"homeworks"}


def test_discover_finds_publications():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
    }


def test_discover_finds_singletons():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.singletons.keys() == {
        "textbook",
    }


def test_discover_reads_publication_metadata():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "Homework 01"
    )


def test_discover_loads_artifacts():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution"]
        .recipe
        == "make solution"
    )


def test_discover_loads_dates_as_dates():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert isinstance(
        universe.collections["homeworks"]
        .publications["01-intro"]
        .metadata['due'], datetime.datetime
    )

    assert isinstance(
        universe.collections["homeworks"]
        .publications["01-intro"]
        .metadata['released'], datetime.date
    )


def test_discover_validates_collection_schema():
    # when run on a malformed collection.yaml
    with raises(publish.SchemaError):
        publish.discover(EXAMPLE_2_DIRECTORY)


def test_discover_validates_publication_schema():
    with raises(publish.SchemaError):
        publish.discover(EXAMPLE_3_DIRECTORY)
