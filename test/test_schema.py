import pathlib
import datetime
from textwrap import dedent

from pytest import fixture, raises

import publish


@fixture
def write_file(tmpdir):
    tmpdir = pathlib.Path(tmpdir)

    def inner(filename, contents):
        path = tmpdir / filename
        with path.open("w") as fileobj:
            fileobj.write(contents)
        return path

    return inner


EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"


# read_collection_file
# -----------------------------------------------------------------------------


def test_read_collection_example(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
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
    assert collection.required_artifacts == ["homework", "solution"]
    assert collection.optional_artifacts == ["template"]
    assert collection.metadata_schema["name"]["type"] == "string"


def test_read_collection_validates_fields(write_file):
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
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
    with raises(publish.SchemaError):
        collection = publish.read_collection_file(path)


def test_read_collection_requires_required_artifacts(write_file):
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
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
    with raises(publish.SchemaError):
        collection = publish.read_collection_file(path)


def test_read_collection_doesnt_require_optional_artifacts(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
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
    assert collection.optional_artifacts == []


def test_read_collection_doesnt_require_metadata_schema(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            required_artifacts:
                - foo
                - bar
            """
        ),
    )

    # when
    collection = publish.read_collection_file(path)

    # then
    assert collection.metadata_schema is None


def test_read_collection_raises_on_invalid_metadata_schema(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
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
    with raises(publish.SchemaError):
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

def test_read_publication_with_relative_release_date_before(write_file):
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


def test_read_publication_with_relative_release_time_multiple_days(write_file):
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


def test_read_publication_with_invalid_relative_date_raises(write_file):
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
    with raises(publish.SchemaError):
        publication = publish.read_publication_file(path)


def test_read_publication_with_invalid_relative_date_variable_reference_raises(write_file):
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
    with raises(publish.SchemaError):
        publication = publish.read_publication_file(path)



def test_read_publication_with_absolute_release_time(write_file):
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
    assert publication.artifacts['solution'].release_time == expected


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
            "homework": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
        },
    )

    collection = publish.Collection(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        publications={},
        allow_unspecified_artifacts=False,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when / then
    with raises(publish.PublicationError):
        collection.validate(publication)


def test_validate_publication_does_not_allow_extra_artifacts(write_file):
    # given
    publication = publish.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
            "extra": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    collection = publish.Collection(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        publications={},
        allow_unspecified_artifacts=False,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when / then
    with raises(publish.PublicationError):
        collection.validate(publication)


def test_validate_publication_allow_unspecified_artifacts(write_file):
    # given
    publication = publish.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
            "extra": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    collection = publish.Collection(
        required_artifacts=[],
        optional_artifacts=[],
        publications={},
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    collection.validate(publication)


def test_validate_publication_validates_metadata(write_file):
    # given
    publication = publish.Publication(
        metadata={
            "thisisclearlywrong": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    collection = publish.Collection(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        publications={},
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    with raises(publish.PublicationError):
        collection.validate(publication)


def test_validate_publication_requires_metadata_if_schema_provided(write_file):
    # given
    publication = publish.Publication(
        metadata={},
        artifacts={
            "homework": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    collection = publish.Collection(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        publications={},
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    with raises(publish.PublicationError):
        collection.validate(publication)


def test_validate_publication_doesnt_require_metadata_if_schema_not_provided(
    write_file,
):
    # given
    publication = publish.Publication(
        metadata={},
        artifacts={
            "homework": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    collection = publish.Collection(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        publications={},
        allow_unspecified_artifacts=True,
        metadata_schema={},
    )

    # when
    collection.validate(publication)


def test_validate_publication_accepts_metadata_if_schema_not_provided(write_file):
    # given
    publication = publish.Publication(
        metadata={"name": "foo"},
        artifacts={
            "homework": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": publish.Artifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    collection = publish.Collection(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        publications={},
        allow_unspecified_artifacts=True,
        metadata_schema=None,
    )

    # when
    collection.validate(publication)

    # then
    assert publication.metadata["name"] == "foo"
