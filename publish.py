"""
publish
=======

A tool to build and publish certain artifacts at certain times.

`publish` was desgined specifically for the automatic publication of course
materials, such as homeworks, lecture slides, etc.


Terminology
-----------

An **artifact** is a file -- usually one that is generated by some build process.

A **publication** is a coherent group of one or more artifacts and their metadata.

A **collection** is a group of publications which all satisfy the same **schema**.

A **schema** is a set of constraints on a publication's artifacts and metadata.


This establishes a **collection -> publication -> artifact hierarchy**: each
artifact belongs to exactly one publication, and each publication belongs to
exactly one collection.

An example of such a hierarchy is the following: all homeworks in a course form
a collection. Each publication within the collection is an individual
homework. Each publication may have several artifacts, such as the PDF of the
problem set, the PDF of the solutions, and a .zip containing the homework's
data.

An artifact may have a **release time**, before which it will not be built or published.

Discovering, Building, and Publishing
-------------------------------------

When run as a script, this package follows a three step process of discovering,
building, and publishing artifacts. 

In the **discovery** step, the script constructs a collection -> publication ->
artifact hierarchy by recursively searching an input directory for artifacts.

In the **build** step, the script builds every artifact whose release time has passed.

In the **publish** step, the script copies every released artifact to an output
directory. 


Discovery
~~~~~~~~~

In the discovery step, the **input directory** is recursively searched for collections,
publications, and artifacts.

A collection is defined by creating a file named ``collections.yaml`` in a directory.
The contents of the file describe the artifacts and metadata that are required
of each of the publications within the collection. For instance: 

.. code-block:: yaml

    # <input_directory>/homeworks/collection.yaml

    schema:
        required_artifacts:
            - homework.pdf
            - solution.pdf

        optional_artifacts:
            - template.zip

        metadata_schema:
            name: 
                type: string
            due:
                type: datetime
            released:
                type: date

The file above specifies that publications must have ``homework.pdf`` and
``solution.pdf`` artifacts, and may or may not have a ``template.zip``
artifact. The publications must also have *name*, *due*, and *released* fields
in their metadata with the listed types. The metadata specification is given in a form
recognizable by the *cerberus* Python package.


A publication and its artifacts are defined by creating a ``publish.yaml`` file
in the directory containing the publication. For instance, the file below
describes how and when to build two artifacts named ``homework.pdf`` and ``solution.pdf``,
along with metadata:

.. code-block:: yaml

    # <input_directory>/homeworks/01-intro/publish.yaml

    metadata:
        name: Homework 01
        due: 2020-09-04 23:59:00
        released: 2020-09-01

    artifacts:
        homework.pdf:
            recipe: make homework
        solution.pdf:
            file: ./build/solution.pdf
            recipe: make solution
            release_time: 1 day after metadata.due

The ``file`` field tells *publish* where the file will appear when the recipe
is run.  is omitted, its value is assumed to be the artifact's key -- for
instance, ``homework.pdf``'s ``file`` field is simply ``homework.pdf``.

The ``release_time`` field provides the artifact's release time. It can be a
specific datetime in ISO 8601 format, like ``2020-09-18 17:00:00``, or a
*relative* date of the form "<number> days after metadata.<field>", in which
case the date will be calculated relative to the metadata field.  The field it
refers to must be a datetime.

The file hierarchy determines which publications belong to which collections.
If a publication file is placed in a directory that is a descendent of a
directory containing a collection file, the publication will be placed in that
collection and its contents will be validated against the collection's schema.
Publications which are not under a directory containing a ``collection.yaml``
are placed into a "default" collection with no schema. They may contain any
number of artifacts and metadata keys.

Collections, publications, and artifacts all have **keys** which locate them
within the hierarchy. These keys are inferred from their position in the
filesystem. For example, a collection file placed at
``<input_directory>/homeworks/collection.yaml`` will create a collection keyed
"homeworks". A publication within the collection at
``<input_directory>/homeworks/01-intro/publish.yaml`` will be keyed "01-intro".
The keys of the artifacts are simply their keys within the ``publish.yaml``
file.


Building
~~~~~~~~

Once all collections, publications, and artifacts have been discovered, the
script moves to the build phase.

Artifacts are built by running the command given in the artifact's `recipe`
field within the directory containing the artifact's ``publication.yaml`` file.
Different artifacts should have "orthogonal" build processes so that the order
in which the artifacts are built is inconsequential.

If an error occurs during any build the entire process is halted and the
program returns without continuing on to the publish phase. An error is
considered to occur if the build process returns a nonzero error code, or if
the artifact file is missing after the recipe is run.


Publishing
~~~~~~~~~~

In the publish phase, all artifacts whose release date has passed are copied to
an **output directory**. Additionally, a JSON file containing information about
the collection -> publication -> artifact hierarchy is placed at the root of
the output directory.

Artifacts are copied to a location within the output directory according to the
following "formula":

.. code-block:: text

    <output_directory>/<collection_key>/<publication_key>/<artifact_key>

For instance, an artifact keyed ``homework.pdf`` in the ``01-intro`` publication
of the ``homeworks`` collection will be copied to::

    <output_directory>/homeworks/01-intro/homework.pdf

An artifact which has not been released will not be copied, even if the
artifact file exists.

*publish* will create a JSON file named ``<output_directory>/published.json``.
This file contains nested dictionaries describing the structure of the
collection -> publication -> artifact hierarchy.

For example, the below code will load the JSON file and print the path of a published
artifact relative to the output directory, as well as a publication's metadata.

.. code-block:: python

    >>> import json
    >>> d = json.load(open('published.json'))
    >>> print(d['collections']['homeworks']['publications']['01-intro']['artifacts']['homework.pdf']['path'])
    homeworks/01-intro/homework.pdf
    >>> print(d['collections']['homeworks']['publications']['01-intro']['metadata']['due'])
    2020-09-10 23:59:00

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
# we will construct a type hierarchy without inheritance.
#
# at the bottom of the hierarchy are artifact types. we'll create three: one
# for unbuilt artifacts, one for built but unpublished artifacts, and another
# for published artifacts.
#
# at progressively higher levels are Publications, Collections, and the Universe.
# these three types are "internal nodes" of the hierarchy, as they each have children:
# a universe contains collections, a collection contains publications, and a publication
# contains artifacts. internal nodes will all have the following methods:
#
#   _deep_asdict()
#       recursively convert the object to a dictionary
#
#   _children()
#       return the children of the internal node
#
#   _replace_children(new_children)
#       replace the children of the internal node, returning a new node instance
#
# these methods enable working with internal nodes in a generic way. for instance, we
# can write a single publish() function that can accept as input a universe, collection,
# publication, or artifact.


class UnbuiltArtifact(typing.NamedTuple):
    """The inputs needed to build an artifact."""

    #: the working directory used to build the artifact
    workdir: pathlib.Path

    #: the path to the file that will be produced by the build, relative to the workdir
    file: str

    #: the command used to build the artifact. if None, no command is necessary
    recipe: str = None

    #: time the artifact should be made public. if None, it is always available
    release_time: datetime.datetime = None


class BuiltArtifact(typing.NamedTuple):
    """The results of building an artifact."""

    # the working directory used to build the artifact
    workdir: pathlib.Path

    # the path to the file that is the result of the build, relative to the workdir
    file: str

    # whether or not the artifact is released
    is_released: bool

    # the stdout of the build. if None, the build didn't happen
    proc: subprocess.CompletedProcess


class PublishedArtifact(typing.NamedTuple):
    """A published artifact."""

    # the path to the file relative to the publication root
    path: str


class Publication(typing.NamedTuple):
    """A publication."""

    # a dictionary of metadata
    metadata: typing.Mapping[str, typing.Any]

    # a dictionary of artifacts
    artifacts: typing.Mapping[str, UnbuiltArtifact]

    def _deep_asdict(self):
        """A dictionary representation of the publication and its children."""
        return {
            "metadata": self.metadata,
            "artifacts": {k: a._asdict() for (k, a) in self.artifacts.items()},
        }

    @property
    def _children(self):
        return self.artifacts

    def _replace_children(self, new_children):
        return self._replace(artifacts=new_children)


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

    @property
    def _children(self):
        return self.publications

    def _replace_children(self, new_children):
        return self._replace(publications=new_children)


class Universe(typing.NamedTuple):
    """Container of all collections."""

    collections: typing.Mapping[str, Collection]

    @property
    def _children(self):
        return self.collections

    def _replace_children(self, new_children):
        return self._replace(collections=new_children)

    def _deep_asdict(self):
        """A dictionary representation of the universe and its children."""
        return {
            "collections": {k: p._deep_asdict() for (k, p) in self.collections.items()},
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
                    "file": {"type": "string", "default": None, "nullable": True},
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

        # if no file is provided, use the key
        if definition["file"] is None:
            definition["file"] = key

        artifacts[key] = UnbuiltArtifact(workdir=path.parent.absolute(), **definition)

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

    return Universe(collections)


# filter_artifacts()
# --------------------------------------------------------------------------------------


class FilterCallbacks:
    def on_hit(self, x):
        """On an artifact match."""

    def on_miss(self, x):
        """On an artifact miss."""


def filter_nodes(parent, predicate, callbacks=None):
    # bottom up -- by the time the predicate is applied to publication, its artifacts
    # have been filtered

    if isinstance(parent, (UnbuiltArtifact, BuiltArtifact, PublishedArtifact)):
        return parent

    new_children = {}
    for child_key, child in parent._children.items():
        new_child = filter_nodes(child, predicate)
        is_artifact = isinstance(
            new_child, (UnbuiltArtifact, BuiltArtifact, PublishedArtifact)
        )
        if is_artifact or new_child._children:
            new_children[child_key] = new_child

    new_children = {k: v for (k, v) in new_children.items() if predicate(k, v)}

    return parent._replace_children(new_children)


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


def _build_artifact(
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
    BuiltArtifact
        A summary of the build results.

    """
    output = BuiltArtifact(
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

        kwargs = {
            "cwd": artifact.workdir,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        proc = run(artifact.recipe, shell=True, **kwargs)

        if proc.returncode:
            msg = "There was a problem while building the artifact: "
            msg += "\n{proc.stderr.decode()}"
            raise BuildError(msg)

    filepath = artifact.workdir / artifact.file
    if not exists(filepath):
        raise BuildError(f"Artifact file {filepath} does not exist.")

    output = output._replace(is_released=True, proc=proc)
    callbacks.on_success(output)
    return output


def build(
    parent,
    *,
    ignore_release_time=False,
    now=datetime.datetime.now,
    run=subprocess.run,
    exists=pathlib.Path.exists,
    callbacks=BuildCallbacks(),
):
    kwargs = dict(
        ignore_release_time=ignore_release_time,
        now=now,
        run=run,
        exists=exists,
        callbacks=callbacks,
    )

    if isinstance(parent, UnbuiltArtifact):
        return _build_artifact(parent, **kwargs)

    new_children = {}
    for child_key, child in parent._children.items():
        new_children[child_key] = build(child, **kwargs)
    return parent._replace_children(new_children)


# publishing
# --------------------------------------------------------------------------------------


def _publish_artifact(built_artifact, outdir, filename):

    if not built_artifact.is_released:
        return PublishedArtifact(None)

    # actually copy the artifact
    full_dst = outdir / filename
    full_dst.parent.mkdir(parents=True, exist_ok=True)
    full_src = built_artifact.workdir / built_artifact.file
    shutil.copy(full_src, full_dst)

    return PublishedArtifact(path=full_dst.relative_to(outdir))


def publish(parent, outdir, prefix=""):
    if isinstance(parent, BuiltArtifact):
        return _publish_artifact(parent, outdir, prefix)

    new_children = {}
    for child_key, child in parent._children.items():
        new_prefix = pathlib.Path(prefix) / child_key
        new_children[child_key] = publish(child, outdir, new_prefix)
    new_parent = parent._replace_children(new_children)

    def keep_non_null_artifacts(k, v):
        if not isinstance(v, BuiltArtifact):
            return True
        else:
            return v.path is not None

    return filter_nodes(new_parent, keep_non_null_artifacts)


# serialization
# --------------------------------------------------------------------------------------


def serialize(node):
    def converter(o):
        return str(o)

    dct = node._deep_asdict()

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
                publication_dct["artifacts"][artifact_key] = PublishedArtifact(
                    **artifact_path
                )
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
    parser.add_argument(
        "--skip-directories",
        type=str,
        nargs="+",
        help="directories that will be ignored during discovery",
    )
    parser.add_argument(
        "--ignore-release-time",
        action="store_true",
        default=False,
        help="if provided, all artifacts will be built and published regardless of release time",
    )
    parser.add_argument(
        "--artifact-filter",
        type=str,
        default=None,
        help="artifacts will be built and published only if their key matches this string",
    )
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
            print(
                _warning(
                    f"\tRelease time {artifact.release_time} has not yet been reached. Skipping."
                )
            )

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

        def keep(k, v):
            if not isinstance(v, UnbuiltArtifact):
                return True
            else:
                return k == args.artifact_filter

        discovered = filter_nodes(discovered, keep, callbacks=CLIFilterCallbacks())

    built = build(
        discovered,
        callbacks=CLIBuildCallbacks(),
        ignore_release_time=args.ignore_release_time,
    )

    published = publish(built, args.output_directory)

    j = serialize(published)
    d = json.loads(j)

    print(d["collections"]["homeworks"]["publications"]["01-intro"]["metadata"]["due"])

    with (args.output_directory / "published.json").open("w") as fileobj:
        fileobj.write(serialize(published))


if __name__ == "__main__":
    cli()
