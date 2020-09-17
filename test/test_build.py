import datetime
import shutil
import pathlib
from unittest.mock import Mock

from pytest import raises, fixture

import publish

# good example; simple
EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"


@fixture
def example_1(tmpdir):
    path = pathlib.Path(tmpdir) / "example_1"
    shutil.copytree(EXAMPLE_1_DIRECTORY, path)
    return path


def test_build_artifact_integration(example_1):
    # given
    collections = publish.discover(example_1)
    artifact = collections["homeworks"].publications["01-intro"].artifacts["solution"]

    # when
    result = publish.build_artifact(artifact)

    # then
    assert (example_1 / "homeworks" / "01-intro" / "solution.pdf").exists()
    assert result.workdir == artifact.workdir
    assert result.file == artifact.file
    assert result.is_released == True


def test_build_artifact_when_release_time_is_in_future():
    # given
    artifact = publish.ArtifactInputs(
        workdir=pathlib.Path.cwd(),
        file="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    now = Mock(return_value=datetime.datetime(2020, 1, 1, 0, 0, 0))

    # when
    result = publish.build_artifact(artifact, run=run, now=now)

    # then
    assert not result.is_released
    assert not run.called


def test_build_artifact_when_release_time_is_in_future_ignore_release_time():
    # given
    artifact = publish.ArtifactInputs(
        workdir=pathlib.Path.cwd(),
        file="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    now = Mock(return_value=datetime.datetime(2020, 1, 1, 0, 0, 0))
    exists = Mock(return_value=True)

    # when
    result = publish.build_artifact(
        artifact, run=run, now=now, exists=exists, ignore_release_time=True
    )

    # then
    assert result.is_released
    assert run.called


def test_build_artifact_when_recipe_is_none():
    # given
    artifact = publish.ArtifactInputs(workdir=pathlib.Path.cwd(), file="foo.pdf", recipe=None)

    run = Mock()
    exists = Mock(return_value=True)

    # when
    result = publish.build_artifact(artifact, run=run, exists=exists)

    # then
    assert result.is_released
    assert not run.called


def test_build_artifact_when_recipe_is_none_raises_if_no_file():
    # given
    artifact = publish.ArtifactInputs(workdir=pathlib.Path.cwd(), file="foo.pdf", recipe=None)

    run = Mock()
    exists = Mock(return_value=False)

    # when
    with raises(publish.BuildError):
        result = publish.build_artifact(artifact, run=run, exists=exists)


def test_build_artifact_raises_if_no_file():
    # given
    artifact = publish.ArtifactInputs(
        workdir=pathlib.Path.cwd(), file="foo.pdf", recipe="touch bar"
    )

    run = Mock()
    exists = Mock(return_value=False)

    # when
    with raises(publish.BuildError):
        result = publish.build_artifact(artifact, run=run, exists=exists)


def test_build_collection(example_1):
    # given
    collections = publish.discover(example_1)

    # when
    built_collection = publish.build(collections)

    # then
    assert (example_1 / "homeworks" / "01-intro" / "solution.pdf").exists()
    build_result = (
        built_collection["homeworks"].publications["01-intro"].artifacts["solution"]
    )
    assert build_result.is_released
    assert (
        built_collection["homeworks"]
        .publications["01-intro"]
        .artifacts["solution"]
        .is_released
    )

    # check that a deep copy is made
    del collections["homeworks"]
    assert "homeworks" in built_collection
