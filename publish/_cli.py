import argparse
import datetime
import pathlib
import textwrap

import yaml


from ._discover import DiscoverCallbacks, discover
from ._build import BuildCallbacks, build
from ._filter import FilterCallbacks, filter_nodes
from ._publish import PublishCallbacks, publish
from ._serialize import serialize
from .types import UnbuiltArtifact, DateContext


# cli
# --------------------------------------------------------------------------------------


def _arg_directory(s):
    path = pathlib.Path(s)
    if not path.is_dir():
        raise argparse.ArgumentTypeError("Not a directory.")
    return path


def _arg_output_directory(s):
    path = pathlib.Path(s)

    if not path.exists():
        path.mkdir(parents=True)
        return path

    return _arg_directory(path)


def _arg_vars_file(s):
    try:
        name, path = s.split(":")
    except ValueError:
        raise argparse.ArgumentTypeError(
            'Vars file argument must be of form "name:path"'
        )
    return name, path


def cli(argv=None):
    """The command line interface.

    Parameters
    ----------
    argv : List[str]
        A list of command line arguments. If None, the arguments will be read from the
        command line passed to the process by the shell.
    now : Callable[[], datetime.datetime]
        A callable producing the current datetime. This is useful when testing, as it
        allows you to inject a fixed, known time.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("input_directory", type=_arg_directory)
    parser.add_argument("output_directory", type=_arg_output_directory)
    parser.add_argument(
        "--skip-directories",
        type=str,
        nargs="+",
        help="directories that will be ignored during discovery",
    )
    parser.add_argument(
        "--ignore-release-time",
        action="store_true",
        help="if provided, all artifacts will be built and published regardless of release time",
    )
    parser.add_argument(
        "--artifact-filter",
        type=str,
        default=None,
        help="artifacts will be built and published only if their key matches this string",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="let stdout and stderr through when building artifacts",
    )
    parser.add_argument(
        "--start-of-week-one",
        type=datetime.date.fromisoformat,
        default=None,
        help="the start of week one. used for smart dates in publication files.",
    )
    parser.add_argument(
        "--now", default=None, help="run as if this is the current time"
    )
    parser.add_argument(
        "--vars",
        type=_arg_vars_file,
        default=None,
        help="A yaml file whose contents will be available in discovery as template variables.",
    )

    args = parser.parse_args(argv)

    if args.now is None:
        now = datetime.datetime.now
    else:
        try:
            n_days = int(args.now)
            _now = datetime.datetime.now() + datetime.timedelta(days=n_days)
        except ValueError:
            _now = datetime.datetime.fromisoformat(args.now)

        def now():
            return _now

    date_context = DateContext()
    if args.start_of_week_one is not None:
        date_context = date_context._replace(start_of_week_one=args.start_of_week_one)

    if args.vars is None:
        template_vars = None
    else:
        name, path = args.vars
        with open(path) as fileobj:
            values = yaml.load(fileobj, Loader=yaml.Loader)
        template_vars = {name: values}

    # construct callbacks for printing information to the screen. start with
    # helper functions for formatting terminal output

    def _header(message):
        return "\u001b[1m" + message + "\u001b[0m"

    def _normal(message):
        return message

    def _body(message):
        return "\u001b[2m" + message + "\u001b[0m"

    def _warning(message):
        return "\u001b[33m" + message + "\u001b[0m"

    def _success(message):
        return "\u001b[32m" + message + "\u001b[0m"

    def _error(message):
        return "\u001b[31m" + message + "\u001b[0m"

    # the callbacks

    class CLIDiscoverCallbacks(DiscoverCallbacks):
        def on_publication(self, path):
            publication_name = str(path.parent)
            print(f"{_normal(publication_name)}")

        def on_skip(self, path):
            relpath = path.relative_to(args.input_directory)
            print(_warning(f"Skipping directory {relpath}"))

    class CLIBuildCallbacks(BuildCallbacks):
        def on_build(self, key, node):
            if isinstance(node, UnbuiltArtifact):
                relative_workdir = node.workdir.relative_to(
                    args.input_directory.absolute()
                )
                path = relative_workdir / key
                msg = _normal(str(path))
                print(msg, end="")

        def on_too_soon(self, node):
            msg = (
                f"   Release time {node.release_time} has not yet been reached. "
                "Skipping."
            )
            if isinstance(node, UnbuiltArtifact):
                print(_warning(msg))

            else:
                for key, artifact in node.artifacts.items():
                    relative_workdir = artifact.workdir.relative_to(
                        args.input_directory.absolute()
                    )
                    path = relative_workdir / key
                    print(str(path) + " " + _warning(msg))

        def on_missing(self, node):
            print(_warning(" file missing, but missing_ok=True"))

        def on_not_ready(self, node):
            msg = f"not ready → skipping"

            if isinstance(node, UnbuiltArtifact):
                print(_warning(f" {msg}"))

            else:
                for key, artifact in node.artifacts.items():
                    relative_workdir = artifact.workdir.relative_to(
                        args.input_directory.absolute()
                    )
                    path = relative_workdir / key
                    print(str(path) + " " + _warning(msg))

        def on_success(self, output):
            print(_success("   build was successful ✓"))

    class CLIFilterCallbacks(FilterCallbacks):
        def on_miss(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_warning(f"\tRemoving {key}"))

        def on_hit(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_success(f"\tKeeping {key}"))

    class CLIPublishCallbacks(PublishCallbacks):
        def on_copy(self, src, dst):
            src = src.relative_to(args.input_directory.absolute())
            dst = dst.relative_to(args.output_directory)
            msg = f"<input_directory>/{src} to <output_directory>/{dst}."
            print(_normal(msg))

    # begin the discover -> build -> publish process

    print()
    print(_header("Discovered publications:"))

    discovered = discover(
        args.input_directory,
        skip_directories=args.skip_directories,
        date_context=date_context,
        template_vars=template_vars,
        callbacks=CLIDiscoverCallbacks(),
    )

    if args.artifact_filter is not None:
        # filter out artifacts whose keys do not match this string

        def keep(k, v):
            if not isinstance(v, UnbuiltArtifact):
                return True
            else:
                return k == args.artifact_filter

        discovered = filter_nodes(
            discovered, keep, remove_empty_nodes=True, callbacks=CLIFilterCallbacks()
        )

    print()
    print(_header("Building:"))

    built = build(
        discovered,
        callbacks=CLIBuildCallbacks(),
        ignore_release_time=args.ignore_release_time,
        verbose=args.verbose,
        now=now,
    )

    print()
    print(_header("Copying:"))
    published = publish(built, args.output_directory, callbacks=CLIPublishCallbacks())

    # serialize the results
    with (args.output_directory / "published.json").open("w") as fileobj:
        fileobj.write(serialize(published))
