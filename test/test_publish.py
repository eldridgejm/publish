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
    collection = publish.discover(example_1)
    build_results = publish.build(collection)

    # when
    publish.publish(build_results, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert (outdir / "homeworks" / "02-intro" / "build" / "solution.pdf").exists()
