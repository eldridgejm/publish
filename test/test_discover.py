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
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections.keys() == {"homeworks", "default"}


def test_discover_finds_publications():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
    }


def test_discover_finds_singletons_and_places_them_in_default_collection():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections["default"].publications.keys() == {
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
        .artifacts["solution.pdf"]
        .recipe
        == "touch solution.pdf"
    )


def test_discover_loads_dates_as_dates():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["due"],
        datetime.datetime,
    )

    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["released"],
        datetime.date,
    )


def test_discover_validates_collection_schema():
    # when run on a malformed collection.yaml
    with raises(publish.InvalidFileError):
        publish.discover(EXAMPLE_2_DIRECTORY)


def test_discover_validates_publication_schema():
    with raises(publish.InvalidFileError):
        publish.discover(EXAMPLE_3_DIRECTORY)


def test_dicover_raises_when_nested_collections_discovered():
    with raises(publish.InvalidFileError):
        publish.discover(EXAMPLE_4_DIRECTORY)


def test_discover_uses_relative_paths_as_keys():
    # when
    universe = publish.discover(EXAMPLE_5_DIRECTORY)

    # then
    assert "foo/bar" in universe.collections
    assert "baz/bazinga" in universe.collections["foo/bar"].publications


def test_discover_skip_directories():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY, skip_directories={"textbook"})

    # then
    assert "textbook" not in universe.collections["default"]


def test_discover_without_file_uses_key():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["homework.pdf"]
        .file
        == "homework.pdf"
    )


def test_discover_filter_artifacts():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)
    universe = publish.filter_artifacts(universe, "solution.pdf")

    # then
    assert (
        "homework.pdf"
        not in universe.collections["homeworks"].publications["01-intro"].artifacts
    )
    assert (
        "solution.pdf"
        in universe.collections["homeworks"].publications["01-intro"].artifacts
    )
