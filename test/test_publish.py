import pathlib
import shutil

from pytest import fixture

import publish

EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"


@fixture
def example_1(tmpdir):
    path = pathlib.Path(tmpdir) / "example_1"
    shutil.copytree(EXAMPLE_1_DIRECTORY, path)
    return path


@fixture
def outdir(tmpdir):
    outdir = pathlib.Path(tmpdir) / "out"
    outdir.mkdir()
    return outdir


def test_publish(example_1, outdir):
    # given
    discovered = publish.discover(example_1)
    builts = publish.build(discovered)

    # when
    published = publish.publish(builts, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert (outdir / "homeworks" / "02-python" / "build" / "solution.pdf").exists()

    assert (
        "homework"
        in published.collections["homeworks"]
        .publications["01-intro"]
        .artifacts
    )


def test_only_publish_if_released(example_1, outdir):
    # given
    discovered = publish.discover(example_1)
    built = publish.build(discovered)
    publication = built.collections["homeworks"].publications["02-python"]
    new = publication.artifacts["solution"]._replace(is_released=False)
    publication.artifacts["solution"] = new

    # when
    published = publish.publish(built, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "build" / "solution.pdf").exists()

    assert (
        "solution"
        not in published.collections["homeworks"]
        .publications["02-python"]
        .artifacts
    )
