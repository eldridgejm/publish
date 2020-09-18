"""
publish
=======

A tool to build and publish artifacts.


Terminology
-----------

An **artifact** is a file -- usually one that is generated by some build process.

A **publication** is a coherent group of one or more artifacts and their metadata.

A **schema** is a set of constraints on a publication's artifacts and metadata.

A **collection** is a group of publications which all satisfy the same **schema**.

This establishes a **collection -> publication -> artifact hierarchy**: each
artifact belongs to exactly one publication, and each publication belongs to
exactly one collection.

An example of such a hierarchy is the following: all homeworks in a course form
a collection. Each publication within the collection is an individual
homework. Each publication may have several artifacts, such as the PDF of the
problem set, the PDF of the solutions, and a .zip containing the homework's
data.

Artifacts may be given release times before which they should not be built or
published.  The core job of this package is to discover, build, and publish all
artifacts whose release time has passed.


Discovering, Building, and Publishing
-------------------------------------

When run as a script, this package follows a three step process of discovering,
building, and publishing artifacts. It takes as its main arguments an input
directory and an output directory.

In the discovery step, the script builds a collection -> publication ->
artifact hierarchy by recursively searching the input directory for
artifacts -- more on this below. In the process, each collection and publication is
given a key inferred from its position with respect to the input directory.

In the build step, the script builds every artifact that was found in the
previous step, provided that the artifact's release_time has passed.

In the publish step, the script copies every artifact whose release_time has
passed to the output directory. The directory structure of the output directory is
made to mimic the directory structure of the input directory, so that an artifact
built at `<input>/homeworks/01-intro/build/homework.pdf` will be copied to
`<output>/homeworks/01-intro/build/homework.pdf`.


Collection and Publication Files
--------------------------------

This package adopts the following convention for defining a collection ->
publication -> artifact hierarchy via the filesystem.

A publication and its artifacts are defined in a `publish.yaml` file. For
instance, the file below describes how and when to build two artifacts named
"homework" and "solution".

    # publish.yaml

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

Collections are defined in a `collection.yaml` file. The file provides a schema used
to validate any publications that will be placed within the collection. For example:

    schema:
        required_artifacts:
            - homework
            - solution

        optional_artifacts:
            - template

        metadata_schema:
            name: 
                type: string
            due:
                type: datetime
            released:
                type: date

This package builds a collection -> publication -> artifact hierarchy by
recursively searching a directory tree. If a `collection.yaml` file is found,
all publications found in descendant directories are validated with respect to
the collection's schema and placed within the collection. If there is no
`collection.yaml` above a publication, it is placed within a "default"
collection and no schema validation is performed.

"""

from collections import deque, namedtuple, defaultdict
from textwrap import dedent
import argparse
import copy
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import typing
import yaml
import cerberus

# constants
# --------------------------------------------------------------------------------------

# the file used to define a collection
COLLECTION_FILE = "collection.yaml"

# the file used to define a publication and its artifacts
PUBLICATION_FILE = "publish.yaml"


# exceptions
# --------------------------------------------------------------------------------------


class Error(Exception):
    """Generic error."""


class SchemaError(Error):
    """Publication does not satisfy schema."""


class InvalidFileError(Error):
    """A configuration file is not valid."""

    def __init__(self, msg, path):
        self.path = path
        self.msg = msg

    def __str__(self):
        return f"Error reading {self.path}: {self.msg}"


class BuildError(Error):
    """Problem while building the artifact."""


# types
# --------------------------------------------------------------------------------------


class ArtifactInputs(typing.NamedTuple):
    """The inputs needed to build an artifact."""

    # the working directory used to build the artifact
    workdir: pathlib.Path

    # the path to the file that is the result of the build, relative to the workdir
    file: str

    # the command used to build the artifact. if None, no command is necessary
    recipe: str = None

    # time the artifact should be made public. if None, it is always available
    release_time: datetime.datetime = None


class ArtifactOutputs(typing.NamedTuple):
    """The results of building an artifact."""

    # the working directory used to build the artifact
    workdir: pathlib.Path

    # the path to the file that is the result of the build, relative to the workdir
    file: str

    # whether or not the artifact is released
    is_released: bool

    # the stdout of the build. if None, the build didn't happen
    proc: subprocess.CompletedProcess


class Publication(typing.NamedTuple):
    """A publication."""

    # a dictionary of metadata
    metadata: typing.Mapping[str, typing.Any]

    # a dictionary of artifacts
    artifacts: typing.Mapping[str, ArtifactInputs]

    def _deep_asdict(self):
        """A dictionary representation of the publication and its children."""
        metadata = self.metadata
        artifacts = {}

        for k, a in self.artifacts.items():
            try:
                artifacts[k] = a._asdict()
            except AttributeError:
                artifacts[k] = str(a)

        return {"metadata": metadata, "artifacts": artifacts}


class Collection(typing.NamedTuple):
    """A collection."""

    # the schema that publications should follow
    schema: "Schema"

    # a dictionary of publications
    publications: typing.Mapping[str, Publication]

    def _deep_asdict(self):
        """A dictionary representation of the collection and its children."""
        return {
            "schema": self.schema._asdict(),
            "publications": {
                k: p._deep_asdict() for (k, p) in self.publications.items()
            },
        }


class Schema(typing.NamedTuple):
    """Rules governing publications.

    Attributes
    ----------
    required_artifacts : Collection[str]
        Names of artifacts that publications must contain.
    optional_artifacts : Collection[str]
        Names of artifacts that publication are permitted to contain. Default: empty
        list.
    allow_unspecified_artifacts : bool
        Is it permissible for a publication to have unknown artifacts? Default: False.
    metadata_schema : dict
        A dictionary describing a schema used to validate publication metadata. In the
        style of cerberus. If None, no validation will be performed. Default: None.

    """

    required_artifacts: typing.Collection[str]
    optional_artifacts: typing.Collection[str] = None
    metadata_schema: typing.Mapping[str, typing.Mapping] = None
    allow_unspecified_artifacts: bool = False


# validation
# --------------------------------------------------------------------------------------


def validate(publication, against):
    """Make sure that a publication fits within the collection.

    Check's the publication's metadata dictionary against
    collection.metadata_schema. Verifies that all required artifacts are provided,
    and that no unknown artifacts are given (unless
    collection.allow_unspecified_artifacts == True).

    Parameters
    ----------
    publication : Publication
        A fully-specified publication.

    Raises
    ------
    SchemaError
        If the publication does not satisfy the collection's constraints.

    """
    schema = against

    # make an iterable default for optional artifacts
    if schema.optional_artifacts is None:
        schema = schema._replace(optional_artifacts={})

    # if there is a metadata schema, enforce it
    if schema.metadata_schema is not None:
        validator = cerberus.Validator(schema.metadata_schema, require_all=True)
        validated = validator.validated(publication.metadata)
        if validated is None:
            raise SchemaError(f"Invalid metadata. {validator.errors}")

    # ensure that all required artifacts are present
    required = set(schema.required_artifacts)
    optional = set(schema.optional_artifacts)
    provided = set(publication.artifacts)
    extra = provided - (required | optional)

    if required - provided:
        raise SchemaError(f"Required artifacts omitted: {required - provided}.")

    if extra and not schema.allow_unspecified_artifacts:
        raise SchemaError(f"Unknown artifacts provided: {provided - optional}.")


# utilities
# --------------------------------------------------------------------------------------


def _all_publications(collections):
    PublicationLocation = namedtuple(
        "PublicationLocation",
        ["collection_key", "collection", "publication_key", "publication"],
    )
    for collection_key, collection in collections.items():
        for publication_key, publication in collection.publications.items():
            yield PublicationLocation(
                collection_key, collection, publication_key, publication,
            )


def _all_artifacts(collections):
    ArtifactLocation = namedtuple(
        "ArtifactLocation",
        [
            "collection_key",
            "collection",
            "publication_key",
            "publication",
            "artifact_key",
            "artifact",
        ],
    )
    for x in _all_publications(collections):
        for artifact_key, artifact in x.publication.artifacts.items():
            yield ArtifactLocation(
                x.collection_key,
                x.collection,
                x.publication_key,
                x.publication,
                artifact_key,
                artifact,
            )


# discovery
# --------------------------------------------------------------------------------------


def read_collection_file(path):
    """Read a Collection from a yaml file.

    The file should have one key, "schema", whose value is a dictionary with
    the following keys/values:

    - required_artifacts
        A list of artifacts names that are required
    - optional_artifacts [optional]
        A list of artifacts that are optional. If not provided, the default value of []
        (empty list) will be used.
    - metadata_schema [optional]
        A dictionary describing a schema for validating publication metadata.  The
        dictionary should deserialize to something recognized by the cerberus package.
        If not provided, the default value of None will be used.
    - allow_unspecified_artifacts [optional]
        Whether or not to allow unspecified artifacts in the publications.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.

    Returns
    -------
    Collection
        The collection object with no attached publications.

    """
    with path.open() as fileobj:
        contents = yaml.load(fileobj, Loader=yaml.Loader)

    # define the structure of the collections file. we require only the
    # 'required_artifacts' field.
    validator = cerberus.Validator(
        {
            "schema": {
                "schema": {
                    "required_artifacts": {
                        "type": "list",
                        "schema": {"type": "string"},
                        "required": True,
                    },
                    "optional_artifacts": {
                        "type": "list",
                        "schema": {"type": "string"},
                        "default": [],
                    },
                    "metadata_schema": {
                        "type": "dict",
                        "required": False,
                        "nullable": True,
                        "default": None,
                    },
                    "allow_unspecified_artifacts": {
                        "type": "boolean",
                        "default": False,
                    },
                },
            }
        },
        require_all=True,
    )

    # validate and normalize
    validated_contents = validator.validated(contents)

    if validated_contents is None:
        raise InvalidFileError(str(validator.errors), path)

    # make sure that the metadata schema is valid
    if validated_contents["schema"]["metadata_schema"] is not None:
        try:
            cerberus.Validator(validated_contents["schema"]["metadata_schema"])
        except Exception as exc:
            raise InvalidFileError("Invalid metadata schema.", path)

    schema = Schema(**validated_contents["schema"])
    return Collection(schema=schema, publications={})


def _parse_release_time(s, metadata):
    """Convert a string like '1 day after metadata.due' to a datetime.
    
    Parameters
    ----------
    s
        A time, maybe in the format of a string, but also possibly None or a datetime.
        If it isn't a string, the function does nothing.
    metadata : dict
        The metadata dictionary used to look up the reference date.

    Returns
    -------
    datetime.datetime or None
        The release time.

    Raises
    ------
    SchemaError
        If the relative date string format is incorrect.

    """
    if not isinstance(s, str):
        return s

    short_match = re.match(r"metadata\.(\w+)$", s)
    long_match = re.match(r"(\d) day[s]{0,1} (after|before) metadata\.(\w+)$", s)

    if short_match:
        [variable] = short_match.groups()
        factor = 1
        days = 0
    elif long_match:
        days, before_or_after, variable = long_match.groups()
        factor = -1 if before_or_after == "before" else 1
    else:
        raise ValueError("Invalid relative date string.")

    if variable not in metadata or not isinstance(
        metadata[variable], datetime.datetime
    ):
        raise ValueError(f"Invalid reference variable '{variable}'. Not a datetime.")

    delta = datetime.timedelta(days=factor * int(days))
    return metadata[variable] + delta


def read_publication_file(path):
    """Read a Publication from a yaml file.

    The file should have a "metadata" key whose value is a dictionary obeying
    collection.metadata_schema. It should also have an "artifacts" key whose value is a
    dictionary mapping artifact names to artifact definitions.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.

    Returns
    -------
    Publication
        The publication.

    """
    with path.open() as fileobj:
        contents = yaml.load(fileobj, Loader=yaml.Loader)

    # we'll just do a quick check of the file structure first. validating the metadata
    # schema and checking that the right artifacts are provided will be done later
    schema = {
        "metadata": {"type": "dict", "required": False, "default": {}},
        "artifacts": {
            "required": True,
            "valuesrules": {
                "schema": {
                    "file": {"type": "string"},
                    "recipe": {"type": "string", "default": None, "nullable": True},
                    "release_time": {
                        "type": ["datetime", "string"],
                        "default": None,
                        "nullable": True,
                    },
                }
            },
        },
    }

    # validate and normalize the contents
    validator = cerberus.Validator(schema, require_all=True)
    validated = validator.validated(contents)

    if validated is None:
        raise InvalidFileError(str(validator.errors), path)

    metadata = validated["metadata"]

    # convert each artifact to an Artifact object
    artifacts = {}
    for key, definition in validated["artifacts"].items():
        # handle relative release times
        try:
            definition["release_time"] = _parse_release_time(
                definition["release_time"], metadata
            )
        except ValueError as exc:
            raise InvalidFileError(str(exc), path)
        artifacts[key] = ArtifactInputs(workdir=path.parent.absolute(), **definition)

    return Publication(metadata=metadata, artifacts=artifacts)


# discovery: discover()
# --------------------------------------------------------------------------------------


class DiscoverCallbacks:
    def on_collection(self, path):
        """When a collection is discovered."""

    def on_publication(self, path):
        """When a publication is discovered."""

    def on_skip(self, path):
        """When a directory is skipped."""


# represents a node in the BFS used in discover()
_BFSNode = namedtuple("Node", "path parent_collection parent_collection_path")


def _discover_bfs(
    initial_node, make_collection, make_publication, skip_directories, callbacks
):
    """Execute a BFS to find collections/publications in the filesystem."""

    queue = deque([initial_node])
    while queue:
        # the current directory, parent collection, and it's path
        (path, parent_collection, parent_collection_path) = node = queue.popleft()

        is_collection = (node.path / COLLECTION_FILE).is_file()
        is_publication = (node.path / PUBLICATION_FILE).is_file()

        if is_collection and is_publication:
            raise InvalidFileError(
                "Cannot be both a publication and a collection.", path
            )

        if is_collection:
            collection = make_collection(node)

            # now that we're in a new collection, the parent has changed
            parent_collection = collection
            parent_collection_path = path

        if is_publication:
            make_publication(node)

        for subpath in path.iterdir():

            if subpath.name in skip_directories:
                callbacks.on_skip(subpath)
                continue

            if subpath.is_dir():
                node = _BFSNode(
                    path=subpath,
                    parent_collection=parent_collection,
                    parent_collection_path=parent_collection_path,
                )
                queue.append(node)


def discover(
    root: pathlib.Path,
    default_collection=None,
    skip_directories=None,
    callbacks=DiscoverCallbacks(),
):
    """Discover the collections and publications in the filesystem."""
    if skip_directories is None:
        skip_directories = set()

    # the collection publications are added to if they belong to no other collection
    if default_collection is None:
        default_schema = Schema(
            required_artifacts=[],
            metadata_schema=None,
            allow_unspecified_artifacts=True,
        )
        default_collection = Collection(schema=default_schema, publications={})

    # by default, we have just the default collection; we'll discover more
    collections = {"default": default_collection}

    # we will run a BFS to discover the collection -> publication -> archive
    # hierarchy. each BFS node will be a triple of the current directory, the
    # parent collection, and the path to the parent collection's directory
    initial_node = _BFSNode(
        path=root, parent_collection=default_collection, parent_collection_path=root,
    )

    # to simplify the code, our BFS function will outsource the creation and validation
    # of our new collection/publication to the below callbacks functions

    def make_collection(node: _BFSNode):
        """Called when a new collection is discovered. Creates/returns collection."""
        path, parent_collection, parent_collection_path = node

        # ensure no nested collections
        if parent_collection is not default_collection:
            raise InvalidFileError("Nested collection found.", path)

        # create the collection
        collection_file = path / COLLECTION_FILE
        new_collection = read_collection_file(collection_file)

        # add it to the rest of the collections
        key = str(path.relative_to(root))
        collections[key] = new_collection

        # callback
        callbacks.on_collection(collection_file)

        # return the new collection
        return collections[key]

    def make_publication(node: _BFSNode):
        """Called when a  new publication is discovered."""
        path, parent_collection, parent_collection_path = node

        # read the publication file
        publication_file = path / PUBLICATION_FILE
        publication = read_publication_file(publication_file)

        # validate its contents against parent collection's schema
        try:
            validate(publication, against=parent_collection.schema)
        except SchemaError as exc:
            raise InvalidFileError(str(exc), publication_file)

        # add the publication to the parent collection
        key = str(path.relative_to(parent_collection_path))
        parent_collection.publications[key] = publication

        # callbacks
        callbacks.on_publication(publication_file)

    # run the BFS; this will populate the `collections` dictionary
    _discover_bfs(
        initial_node, make_collection, make_publication, skip_directories, callbacks
    )

    return collections


# filter_artifacts()
# --------------------------------------------------------------------------------------


class FilterCallbacks:
    def on_hit(self, x):
        """On an artifact match."""

    def on_miss(self, x):
        """On an artifact miss."""


def filter_artifacts(collections, predicate, callbacks=FilterCallbacks()):

    if isinstance(predicate, str):
        pattern = predicate

        def predicate(x):
            return x == pattern

    # find all artifacts matching the filter
    matched = []
    for x in _all_artifacts(collections):
        if predicate(x.artifact_key):
            matched.append(x)
            callbacks.on_hit(x)
        else:
            callbacks.on_miss(x)

    remaining = {}

    for match in matched:
        # if the collection doesn't exist, create it
        if match.collection_key not in remaining:
            collection = match.collection._replace(publications={})
            remaining[match.collection_key] = collection
        else:
            collection = remaining[match.collection_key]

        # if the publication doesn't exist, create it
        if match.publication_key not in collection.publications:
            publication = match.publication._replace(artifacts={})
            collection.publications[match.publication_key] = publication
        else:
            publication = collection.publications[match.publication_key]

        # add the artifact
        if match.artifact_key not in publication.artifacts:
            publication.artifacts[match.artifact_key] = match.artifact

    return remaining


# building
# --------------------------------------------------------------------------------------


class BuildCallbacks:
    """Callbacks used by build()"""

    def on_collection(self, collection_key, collection):
        """Called when building a collection."""

    def on_publication(self, publication_key, publication):
        """Called when building a publication."""

    def on_artifact(self, artifact_key, artifact):
        """Called when building an artifact."""

    def on_too_soon(self, artifact):
        """Called when it is too soon to release the artifact."""

    def on_build(self, artifact):
        """Called when artifact is being built."""

    def on_success(self, build_result):
        """Called when the build succeeded."""


def build_artifact(
    artifact,
    *,
    ignore_release_time=False,
    now=datetime.datetime.now,
    run=subprocess.run,
    exists=pathlib.Path.exists,
    callbacks=BuildCallbacks(),
):
    """Build an artifact using its recipe.

    Parameters
    ----------
    artifact : Artifact
        The artifact to build.
    ignore_release_time : bool
        If True, the release time of the artifact will be ignored, and it will
        be built anyways. Default: False.

    Returns
    -------
    ArtifactOutputs
        A summary of the build results.

    """
    output = ArtifactOutputs(
        workdir=artifact.workdir, file=artifact.file, is_released=False, proc=None
    )

    if (
        not ignore_release_time
        and artifact.release_time is not None
        and artifact.release_time > now()
    ):
        callbacks.on_too_soon(artifact)
        return output

    if artifact.recipe is None:
        proc = None
    else:
        callbacks.on_build(artifact)
        proc = run(
            artifact.recipe,
            shell=True,
            cwd=artifact.workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if proc.returncode:
            raise BuildError(
                f"There was a problem while building the artifact: \n{proc.stderr.decode()}"
            )

    filepath = artifact.workdir / artifact.file
    if not exists(filepath):
        raise BuildError(f"Artifact file {filepath} does not exist.")

    output = output._replace(is_released=True, proc=proc)
    callbacks.on_success(output)
    return output


def build_publication(
    publication, *, ignore_release_time=False, callbacks=BuildCallbacks()
):
    outputs = {}
    for artifact_key, artifact in publication.artifacts.items():
        callbacks.on_artifact(artifact_key, artifact)
        outputs[artifact_key] = build_artifact(
            artifact, ignore_release_time=ignore_release_time, callbacks=callbacks
        )
    return publication._replace(artifacts=outputs)


def build_collection(
    collection, *, ignore_release_time=False, callbacks=BuildCallbacks()
):
    outputs = {}
    for publication_key, publication in collection.publications.items():
        callbacks.on_publication(publication_key, publication)
        outputs[publication_key] = build_publication(
            publication, ignore_release_time=ignore_release_time, callbacks=callbacks
        )
    return collection._replace(publications=outputs)


def build(collections, ignore_release_time=False, callbacks=BuildCallbacks()):
    outputs = {}
    for collection_key, collection in collections.items():
        callbacks.on_collection(collection_key, collection)
        outputs[collection_key] = build_collection(
            collection, ignore_release_time=ignore_release_time, callbacks=callbacks
        )
    return outputs


def _build(parent):
    new_children = {}
    for child_key, child in children(parent):
        callback(child_key, child)
        new_children[child_key] = _build(child)
    return replace_children(parent, outputs)


def _children(parent):
    if isinstance(parent, dict):
        return parent.items()
    elif isinstance(parent, Collection):
        return parent.publications.items()
    elif isinstance(parent, Publication):
        return parent.artifacts.items()


def _replace_children(parent, new_children):
    if isinstance(parent, dict):
        return new_children
    elif isinstance(parent, Collection):
        return parent._replace(publications=new_children)
    elif isinstance(parent, Publication):
        return parent._replace(artifacts=new_children)


# publishing
# --------------------------------------------------------------------------------------


def publish(collections, outdir):
    """Copy all of the build results to a destination directory.

    An artifact's destination is determined using the following "formula":

        <collection_key>/<publication_key>/artifact.file

    Since the collection key and publication key can contain slashes, the
    path may be of an arbitrary depth.

    """
    published_collections = copy.deepcopy(collections)
    unreleased = set()

    for x in _all_artifacts(published_collections):
        # if it wasn't released, we shouldn't publish it
        if not x.artifact.is_released:
            unreleased.add((x.collection_key, x.publication_key, x.artifact_key))
            continue

        # actually copy the artifact
        relative_dst = (
            pathlib.Path(x.collection_key) / x.publication_key / x.artifact.file
        )
        full_dst = outdir / relative_dst
        full_dst.parent.mkdir(parents=True, exist_ok=True)
        full_src = x.artifact.workdir / x.artifact.file
        shutil.copy(full_src, full_dst)

        # update the result
        x.publication.artifacts[x.artifact_key] = relative_dst

    # remove all unreleased artifacts
    for (collection_key, publication_key, artifact_key) in unreleased:
        collection = published_collections[collection_key]
        publication = collection.publications[publication_key]
        del publication.artifacts[artifact_key]

    return published_collections


# serialization
# --------------------------------------------------------------------------------------


def serialize(published):
    def converter(o):
        return str(o)

    dct = {}
    for collection_key, collection in published.items():
        dct[collection_key] = collection._deep_asdict()

    return json.dumps(dct, default=converter, indent=4)


def _convert_to_time(s):
    converters = [datetime.date.fromisoformat, datetime.datetime.fromisoformat]
    for converter in converters:
        try:
            return converter(s)
        except ValueError:
            continue
    else:
        raise ValueError("Not a time.")


def deserialize(s):
    def hook(pairs):
        d = {}
        for k, v in pairs:
            if isinstance(v, str):
                try:
                    d[k] = _convert_to_time(v)
                except ValueError:
                    d[k] = v
            else:
                d[k] = v
        return d

    dct = json.loads(s, object_pairs_hook=hook)
    for collection_key, collection_dct in dct.items():
        publications = {}
        for publication_key, publication_dct in collection_dct["publications"].items():
            for artifact_key, artifact_path in publication_dct["artifacts"].items():
                publication_dct["artifacts"][artifact_key] = pathlib.Path(artifact_path)
            publications[publication_key] = Publication(**publication_dct)
        schema = Schema(**collection_dct["schema"])
        dct[collection_key] = Collection(publications=publications, schema=schema)
    return dct


# cli
# --------------------------------------------------------------------------------------


def _arg_directory(s):
    path = pathlib.Path(s)
    if not path.is_dir():
        raise argparse.ArgumentTypeError("Not a directory.")
    return path


def cli(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("input_directory", type=_arg_directory)
    parser.add_argument("output_directory", type=_arg_directory)
    parser.add_argument("--skip-directories", type=str, nargs="+")
    parser.add_argument("--ignore-release-time", action="store_true", default=False)
    parser.add_argument("--artifact-filter", type=str, default=None)
    parser.add_argument("--manifest", type=str, default=None)
    args = parser.parse_args(argv)

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

    class CLIDiscoverCallbacks(DiscoverCallbacks):
        def on_collection(self, path):
            relpath = path.parent.relative_to(args.input_directory)
            print(_header(f"Discovered collection in {relpath}"))

        def on_publication(self, path):
            relpath = path.parent.relative_to(args.input_directory)
            print(_header(f"Discovered publication in {relpath}"))

        def on_skip(self, path):
            relpath = path.relative_to(args.input_directory)
            print(_warning(f"Skipping directory {relpath}"))

    class CLIBuildCallbacks(BuildCallbacks):
        def __init__(self):
            self.current_collection_key = None
            self.current_publication_key = None

        def on_collection(self, collection_key, collection):
            self.current_collection_key = collection_key

        def on_publication(self, publication_key, publication):
            self.current_publication_key = publication_key

        def on_artifact(self, artifact_key, artifact):
            path = f"{self.current_collection_key}:{self.current_publication_key}:{artifact_key}"
            msg = f"Building artifact {path}"
            print(_header(msg))

        def on_build(self, artifact):
            print(_body(f'\tExecuting "{artifact.recipe}"'))

        def on_too_soon(self, artifact):
            print(_warning(f"\tRelease time {artifact.release_time} has not yet been reached. Skipping."))

        def on_success(self, output):
            print(_success("\tBuild was successful"))

    class CLIFilterCallbacks(FilterCallbacks):
        def on_miss(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_warning(f"\tRemoving {key}"))

        def on_hit(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_success(f"\tKeeping {key}"))

    discovered = discover(
        args.input_directory,
        skip_directories=args.skip_directories,
        callbacks=CLIDiscoverCallbacks(),
    )

    if args.artifact_filter is not None:
        discovered = filter_artifacts(
            discovered, args.artifact_filter, callbacks=CLIFilterCallbacks()
        )

    built = build(
        discovered,
        callbacks=CLIBuildCallbacks(),
        ignore_release_time=args.ignore_release_time,
    )

    published = publish(built, args.output_directory)

    with (args.output_directory / "published.json").open("w") as fileobj:
        fileobj.write(serialize(published))


if __name__ == "__main__":
    cli()
