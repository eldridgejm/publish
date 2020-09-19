import pathlib
from pytest import fixture


@fixture
def write_file(tmpdir):
    tmpdir = pathlib.Path(tmpdir)

    def inner(filename, contents):
        path = tmpdir / filename
        with path.open("w") as fileobj:
            fileobj.write(contents)
        return path

    return inner
