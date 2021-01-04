import json
import argparse
import collections
import datetime
import pathlib
import typing

import yaml

from . import serialize, discover, DateContext


ArtifactLocation = collections.namedtuple(
    "ArtifactLocation",
    [
        "artifact_key",
        "artifact",
        "publication_key",
        "publication",
        "collection_key",
        "collection",
    ],
)


def _all_artifacts(universe):
    for collection_key, collection in universe.collections.items():
        for publication_key, publication in collection.publications.items():
            for artifact_key, artifact in publication.artifacts.items():
                yield ArtifactLocation(
                    artifact_key,
                    artifact,
                    publication_key,
                    publication,
                    collection_key,
                    collection,
                )


class _Never:
    def __lt__(self, other):
        if not isinstance(other, (datetime.date, _Never)):
            return NotImplemented
        return False

    def __gt__(self, other):
        if not isinstance(other, (datetime.date, _Never)):
            return NotImplemented
        return True


class ReleaseInfo(typing.NamedTuple):
    # the sooner of the publication release time and the artifact release time;
    # if both are None, so is this
    effective_release_time: datetime.datetime

    # the smaller of the publication ready and artifact ready
    ready: bool


def _release_info(loc):

    if loc.artifact.release_time is None:
        ert = loc.publication.release_time
    elif loc.publication.release_time is None:
        ert = loc.artifact.release_time
    else:
        ert = min(loc.publication.release_time, loc.artifact.release_time)

    ready = min(loc.artifact.ready, loc.publication.ready)

    return ReleaseInfo(ert, ready)


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


def _purple(message):
    return "\u001b[35m" + message + "\u001b[0m"


def cli(argv=None):
    pass


def _rpad(s, total_len):
    difference = total_len - len(s)
    return s + (" " * difference)


def _lpad(s, total_len):
    difference = total_len - len(s)
    return (" " * difference) + s


def _days_between(date_x, date_y):
    return (date_x - date_y).days


def release_schedule(args):
    universe = discover(
        args.path, skip_directories=args.skip_directories, template_vars=args.vars
    )

    # get the release info for every artifact
    info = [(loc, _release_info(loc)) for loc in _all_artifacts(universe)]

    without_release_time = [x for x in info if x[1].effective_release_time is None]
    with_release_time = [x for x in info if x[1].effective_release_time is not None]

    if not args.show_not_ready:
        with_release_time = [x for x in with_release_time if x[1].ready]

    # sort in order of release time
    sorted_releases = sorted(
        with_release_time, key=lambda x: x[1].effective_release_time
    )

    by_date = collections.defaultdict(lambda: [])
    for time in sorted_releases:
        date = time[1].effective_release_time.date()
        by_date[date].append(time)

    first_date = datetime.date.today()
    last_date = sorted_releases[-1][1].effective_release_time.date()

    date_cursor = first_date
    while date_cursor <= last_date:
        releases = by_date[date_cursor]

        if date_cursor.weekday() == 0 and not args.skip_empty_days:
            print()
            print(9 * " ", _body("----------"))
            print()

        if date_cursor == datetime.date.today():
            header = "today"
        else:
            header = ""

        if releases or not args.skip_empty_days:
            print(_header(_lpad(header, 9)), end=" ")
            print(date_cursor.strftime("%a %b %d").lower())

        if date_cursor not in by_date:
            date_cursor += datetime.timedelta(days=1)
            continue

        for loc, (ert, ready) in by_date[date_cursor]:

            suffix = ''
            missing = not (loc.artifact.workdir / loc.artifact.file).exists()

            if not ready:
                color = _error
                suffix = '(not ready)'
            elif missing:
                suffix = '(missing)'
                color = _purple
            elif ert > datetime.datetime.now():
                color = _warning
                suffix = '(waiting)'
            else:
                color = _success
                suffix = '(released)'

            if ert.date() == date_cursor:
                print(21 * " ", end="")

                print(
                    str(ert.time()),
                    _body("::"),
                    color(loc.collection_key),
                    _body("/"),
                    color(loc.publication_key),
                    _body("/"),
                    color(loc.artifact_key),
                    end="",
                )

                print(f" {suffix}")

        date_cursor += datetime.timedelta(days=1)


def _arg_vars_file(s):
    try:
        name, path = s.split(":")
    except ValueError:
        raise argparse.ArgumentTypeError(
            'Vars file argument must be of form "name:path"'
        )

    with open(path) as fileobj:
        values = yaml.load(fileobj, Loader=yaml.Loader)

    return {name: values}


def _configure_release_schedule_cli(subparsers):
    release_parser = subparsers.add_parser("release-schedule")

    release_parser.set_defaults(cmd=release_schedule)

    release_parser.add_argument(
        "path", default=pathlib.Path.cwd(), nargs="?", type=pathlib.Path
    )
    release_parser.add_argument(
        "--skip-directories",
        type=str,
        nargs="+",
        help="directories that will be ignored during discovery",
    )
    release_parser.add_argument(
        "--show-not-ready", action="store_true", default=False,
    )
    release_parser.add_argument(
        "--skip-empty-days", action="store_true", default=False,
    )
    release_parser.add_argument(
        "--vars",
        type=_arg_vars_file,
        default=None,
        help="A yaml file whose contents will be available in discovery as template variables.",
    )


def cli():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    _configure_release_schedule_cli(subparsers)

    args = parser.parse_args()

    args.cmd(args)
