import pathlib
import datetime

from pytest import raises

import publish


EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"


# validate_publication
# -----------------------------------------------------------------------------


def test_validate_publication_checks_required_artifacts():
    # given
    publication = publish.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
        },
    )

    schema = publish.Schema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=False,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when / then
    with raises(publish.ValidationError):
        publish.validate(publication, against=schema)


def test_validate_publication_does_not_allow_extra_artifacts(write_file):
    # given
    publication = publish.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
            "extra": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = publish.Schema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=False,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when / then
    with raises(publish.ValidationError):
        publish.validate(publication, against=schema)


def test_validate_publication_allow_unspecified_artifacts(write_file):
    # given
    publication = publish.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
            "extra": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = publish.Schema(
        required_artifacts=[],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    publish.validate(publication, against=schema)


def test_validate_publication_validates_metadata(write_file):
    # given
    publication = publish.Publication(
        metadata={
            "thisisclearlywrong": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = publish.Schema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    with raises(publish.ValidationError):
        publish.validate(publication, against=schema)


def test_validate_publication_requires_metadata_if_schema_provided(write_file):
    # given
    publication = publish.Publication(
        metadata={},
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = publish.Schema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    with raises(publish.ValidationError):
        publish.validate(publication, against=schema)


def test_validate_publication_doesnt_require_metadata_if_schema_not_provided(
    write_file,
):
    # given
    publication = publish.Publication(
        metadata={},
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = publish.Schema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={},
    )

    # when
    publish.validate(publication, against=schema)


def test_validate_publication_accepts_metadata_if_schema_not_provided(write_file):
    # given
    publication = publish.Publication(
        metadata={"name": "foo"},
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = publish.Schema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema=None,
    )

    # when
    publish.validate(publication, against=schema)

    # then
    assert publication.metadata["name"] == "foo"
