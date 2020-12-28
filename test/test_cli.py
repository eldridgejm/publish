from publish import cli

import shutil
import pathlib

from pytest import fixture


@fixture
def make_input_directory(tmpdir):
    def make_input_directory(example):
        input_path = pathlib.Path(tmpdir) / "input"
        example_path = pathlib.Path(__file__).parent / example
        shutil.copytree(example_path, input_path)
        return input_path

    return make_input_directory


@fixture
def output_directory(tmpdir):
    output_path = pathlib.Path(tmpdir) / "output"
    output_path.mkdir()
    return output_path


def test_publish_simple_example(make_input_directory, output_directory):
    # given
    input_directory = make_input_directory("example_1")

    # when
    cli([str(input_directory), str(output_directory)])

    # then
    assert (output_directory / "homeworks" / "01-intro" / "homework.pdf").exists()


def test_publish_with_example_depending_on_week_start_date(make_input_directory, output_directory):
    # given
    input_directory = make_input_directory("example_8")

    # when
    cli([str(input_directory), str(output_directory), '--start-of-week-one', '2020-01-04', '--ignore-release-time'])

    # then
    assert (output_directory / "lectures" / "01-intro").exists()
