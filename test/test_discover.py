import datetime
import pathlib
from textwrap import dedent

from pytest import raises, fixture

import publish


# good example; simple
EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"

# bad: bad collection file
EXAMPLE_2_DIRECTORY = pathlib.Path(__file__).parent / "example_2"

# bad: mismatched publication metadata
EXAMPLE_3_DIRECTORY = pathlib.Path(__file__).parent / "example_3"

# bad: nested collections
EXAMPLE_4_DIRECTORY = pathlib.Path(__file__).parent / "example_4"

# good: relative paths as keys
EXAMPLE_5_DIRECTORY = pathlib.Path(__file__).parent / "example_5"

# bad: publication metadata doesn't match schema
EXAMPLE_6_DIRECTORY = pathlib.Path(__file__).parent / "example_6"


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
        "03-not_ready",
        "04-publication_not_released",
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


def test_discover_reads_ready():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        not universe.collections["homeworks"]
        .publications["03-not_ready"]
        .artifacts["homework.pdf"]
        .ready
    )


def test_discover_validates_collection_schema():
    # when run on a malformed collection.yaml
    with raises(publish.DiscoveryError):
        publish.discover(EXAMPLE_2_DIRECTORY)


def test_discover_validates_publication_schema():
    with raises(publish.DiscoveryError):
        publish.discover(EXAMPLE_3_DIRECTORY)


def test_discover_validates_publication_metadata_schema():
    with raises(publish.DiscoveryError):
        publish.discover(EXAMPLE_6_DIRECTORY)


def test_dicover_raises_when_nested_collections_discovered():
    with raises(publish.DiscoveryError):
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


def test_filter_artifacts():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    def keep(k, v):
        if not isinstance(v, publish.UnbuiltArtifact):
            return True

        return k == "solution.pdf"

    universe = publish.filter_nodes(universe, keep)

    # then
    assert (
        "homework.pdf"
        not in universe.collections["homeworks"].publications["01-intro"].artifacts
    )
    assert (
        "solution.pdf"
        in universe.collections["homeworks"].publications["01-intro"].artifacts
    )


def test_filter_artifacts_removes_nodes_without_children():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    def keep(k, v):
        if not isinstance(v, publish.UnbuiltArtifact):
            return True

        return k not in {"solution.pdf", "homework.pdf"}

    universe = publish.filter_nodes(universe, keep, remove_empty_nodes=True)

    # then
    assert "homeworks" not in universe.collections


def test_filter_artifacts_preserves_nodes_without_children_by_default():
    # when
    universe = publish.discover(EXAMPLE_1_DIRECTORY)

    def keep(k, v):
        if not isinstance(v, publish.UnbuiltArtifact):
            return True

        return k not in {"solution.pdf", "homework.pdf"}

    universe = publish.filter_nodes(universe, keep)

    # then
    assert "homeworks" in universe.collections


# read_collection_file
# -----------------------------------------------------------------------------


def test_read_collection_example(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            schema:
                required_artifacts:
                    - homework
                    - solution

                optional_artifacts:
                    - template

                metadata_schema:
                    name: 
                        type: string
                    due:
                        type: date
            """
        ),
    )

    # when
    collection = publish.read_collection_file(path)

    # then
    assert collection.schema.required_artifacts == ["homework", "solution"]
    assert collection.schema.optional_artifacts == ["template"]
    assert collection.schema.metadata_schema["name"]["type"] == "string"


def test_read_collection_validates_fields(write_file):
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            schema:
                # this ain't right..., should be a list of str
                required_artifacts: 42

                optional_artifacts:
                    - template

                metadata_schema:
                    name: 
                        type: string
                    due:
                        type: date
            """
        ),
    )

    # then
    with raises(publish.DiscoveryError):
        collection = publish.read_collection_file(path)


def test_read_collection_requires_required_artifacts(write_file):
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            schema:
                # this ain't right..., should have required_artifacts...

                optional_artifacts:
                    - template

                metadata_schema:
                    name: 
                        type: string
                    due:
                        type: date
            """
        ),
    )

    # then
    with raises(publish.DiscoveryError):
        collection = publish.read_collection_file(path)


def test_read_collection_doesnt_require_optional_artifacts(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            schema:
                required_artifacts:
                    - foo
                    - bar

                metadata_schema:
                    name: 
                        type: string
                    due:
                        type: date
            """
        ),
    )

    # when
    collection = publish.read_collection_file(path)

    # then
    assert collection.schema.optional_artifacts == []


def test_read_collection_doesnt_require_metadata_schema(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            schema:
                required_artifacts:
                    - foo
                    - bar
            """
        ),
    )

    # when
    collection = publish.read_collection_file(path)

    # then
    assert collection.schema.metadata_schema is None


def test_read_collection_raises_on_invalid_metadata_schema(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            schema:
                required_artifacts:
                    - foo
                    - bar

                metadata_schema:
                    foo: 1
                    bar: 2
            """
        ),
    )

    # when then
    with raises(publish.DiscoveryError):
        collection = publish.read_collection_file(path)


# read_publication_file
# -----------------------------------------------------------------------------


def test_read_publication_example(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    assert publication.metadata["name"] == "Homework 01"
    assert isinstance(publication.metadata["due"], datetime.datetime)
    assert isinstance(publication.metadata["released"], datetime.date)
    assert publication.artifacts["homework"].recipe == "make homework"


def test_read_publication_without_release_time(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    assert publication.release_time is None


def test_read_publication_with_relative_release_time(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            release_time: 1 day after metadata.due

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(days=1)
    assert publication.release_time == expected


def test_read_artifact_with_relative_release_time(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"]
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_relative_release_date_raises(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: metadata.released
            """
        ),
    )

    # then
    with raises(publish.DiscoveryError):
        publication = publish.read_publication_file(path)


def test_read_artifact_with_relative_release_time_after(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 1 day after metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(days=1)
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_relative_release_time_after_hours(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 3 hours after metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(hours=3)
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_relative_release_time_after_large(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 11 days after metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(days=11)
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_relative_release_time_after_large_hours(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 1000 hours after metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(hours=1000)
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_relative_release_date_before(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 3 days before metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] - datetime.timedelta(days=3)
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_relative_release_date_before_hours(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 3 hours before metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] - datetime.timedelta(hours=3)
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_relative_release_time_multiple_days(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 3 days after metadata.due
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(days=3)
    assert publication.artifacts["solution"].release_time == expected


def test_read_artifact_with_invalid_relative_date_raises(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: -1 days after metadata.due
            """
        ),
    )

    # when
    with raises(publish.DiscoveryError):
        publication = publish.read_publication_file(path)


def test_read_artifact_with_invalid_relative_date_variable_reference_raises(
    write_file,
):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 1 days after metadata.foo
            """
        ),
    )

    # when
    with raises(publish.DiscoveryError):
        publication = publish.read_publication_file(path)


def test_read_artifact_with_absolute_release_time(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 2020-01-02 23:59:00
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = datetime.datetime(2020, 1, 2, 23, 59, 0)
    assert publication.artifacts["solution"].release_time == expected


# relative metadata
# --------------------------------------------------------------------------------------

def test_read_artifact_with_relative_dates_in_metadata(write_file):
    # given
    path = write_file(
        "publish.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-10 23:59:00
                released: 7 days before due

            artifacts:
                homework:
                    file: ./homework.pdf
                    recipe: make homework
                solution:
                    file: ./solution.pdf
                    recipe: make solution
                    release_time: 2020-01-02 23:59:00
            """
        ),
    )

    # when
    publication = publish.read_publication_file(path)

    # then
    expected = datetime.datetime(2020, 9, 3, 23, 59, 0)
    # assert publication.metadata["released"] == expected
