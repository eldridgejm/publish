import datetime
import pathlib
import textwrap

from pytest import raises

import publish


# good example; simple
EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"

# bad collection file
EXAMPLE_2_DIRECTORY = pathlib.Path(__file__).parent / "example_2"

# mismatched publication metadata
EXAMPLE_3_DIRECTORY = pathlib.Path(__file__).parent / "example_3"

# nested collections
EXAMPLE_4_DIRECTORY = pathlib.Path(__file__).parent / "example_4"

# relative paths as keys
EXAMPLE_5_DIRECTORY = pathlib.Path(__file__).parent / "example_5"


def test_discover_finds_collections():
    # when
    collections = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert collections.keys() == {"homeworks", "default"}


def test_discover_finds_publications():
    # when
    collections = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
    }


def test_discover_finds_singletons_and_places_them_in_default_collection():
    # when
    collections = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert collections["default"].publications.keys() == {
        "textbook",
    }


def test_discover_reads_publication_metadata():
    # when
    collections = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        collections["homeworks"].publications["01-intro"].metadata["name"]
        == "Homework 01"
    )


def test_discover_loads_artifacts():
    # when
    collections = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        collections["homeworks"].publications["01-intro"].artifacts["solution"].recipe
        == "touch solution.pdf"
    )


def test_discover_loads_dates_as_dates():
    # when
    collections = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert isinstance(
        collections["homeworks"].publications["01-intro"].metadata["due"],
        datetime.datetime,
    )

    assert isinstance(
        collections["homeworks"].publications["01-intro"].metadata["released"],
        datetime.date,
    )


def test_discover_validates_collection_schema():
    # when run on a malformed collection.yaml
    with raises(publish.SchemaError):
        publish.discover(EXAMPLE_2_DIRECTORY)


def test_discover_validates_publication_schema():
    with raises(publish.SchemaError):
        publish.discover(EXAMPLE_3_DIRECTORY)


def test_dicover_raises_when_nested_collections_discovered():
    with raises(publish.SchemaError):
        publish.discover(EXAMPLE_4_DIRECTORY)


def test_discover_uses_relative_paths_as_keys():
    # when
    collections = publish.discover(EXAMPLE_5_DIRECTORY)

    # then
    assert "foo/bar" in collections
    assert "baz/bazinga" in collections["foo/bar"].publications


def test_discover_ignore_directories():
    # when
    collections = publish.discover(EXAMPLE_1_DIRECTORY, ignore={"textbook"})

    # then
    assert "textbook" not in collections
