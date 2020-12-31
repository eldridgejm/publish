import json
import argparse
import collections
import datetime
import pathlib

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


def _effective_release_time(loc):
    if loc.artifact.release_time is None:
        sooner = loc.publication.release_time
    elif loc.publication.release_time is None:
        sooner = loc.artifact.release_time
    else:
        sooner = min(loc.artifact.release_time, loc.publication.release_time)

    if sooner is None:
        sooner = datetime.datetime.now()

    return sooner


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


def cli(argv=None):
    pass


def release_calendar(cwd, date_context, show_published=False, skip_directories=None):
    universe = discover(
        cwd, date_context=date_context, skip_directories=skip_directories
    )

    times = [(loc, _effective_release_time(loc)) for loc in _all_artifacts(universe)]
    sorted_times = sorted(times, key=lambda x: x[1])

    now = datetime.datetime.now()

    for loc, time in sorted_times:
        if time > now or show_published:

            if time > now:
                color = _warning
            else:
                color = _success

            print(color(str(time)), end="")
            print(
                "\t",
                loc.collection_key,
                "/",
                loc.publication_key,
                "/",
                loc.artifact_key,
            )


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path", default=pathlib.Path.cwd(), nargs="?", type=pathlib.Path
    )
    parser.add_argument(
        "--start-of-week-one",
        type=datetime.date.fromisoformat,
        default=None,
        help="the start of week one. used for smart dates in publication files.",
    )
    parser.add_argument(
        "--skip-directories",
        type=str,
        nargs="+",
        help="directories that will be ignored during discovery",
    )
    parser.add_argument(
        "--show-published", action="store_true", default=False,
    )

    args = parser.parse_args()

    date_context = DateContext(start_of_week_one=args.start_of_week_one)
    release_calendar(
        args.path,
        date_context,
        skip_directories=args.skip_directories,
        show_published=args.show_published,
    )
