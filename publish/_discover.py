import typing
import datetime
import pathlib
import re
from collections import namedtuple, deque

import cerberus
import yaml

from .types import (
    UnbuiltArtifact,
    Publication,
    Collection,
    Universe,
    Schema,
    DateContext,
)
from .exceptions import ValidationError, DiscoveryError
from ._validate import validate, _PublicationValidator
from ._smartdates import resolve_smart_dates
from . import constants


# read_collection_file
# --------------------------------------------------------------------------------------


def read_collection_file(path):
    """Read a :class:`Collection` from a yaml file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.

    Returns
    -------
    Collection
        The collection object with no attached publications.

    Notes
    -----
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
        Default: False.

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
        raise DiscoveryError(str(validator.errors), path)

    # make sure that the metadata schema is valid
    if validated_contents["schema"]["metadata_schema"] is not None:
        try:
            cerberus.Validator(validated_contents["schema"]["metadata_schema"])
        except Exception as exc:
            raise DiscoveryError("Invalid metadata schema.", path)

    schema = Schema(**validated_contents["schema"])
    return Collection(schema=schema, publications={})


# read_publication_file
# --------------------------------------------------------------------------------------


def _resolve_smart_dates_in_metadata(metadata, metadata_schema, path, date_context):
    def _is_smart_date(k):
        try:
            return metadata_schema[k]["type"] in {"smartdate", "smartdatetime"}
        except Exception:
            return False

    smart_dates = {k: v for k, v in metadata.items() if _is_smart_date(k)}
    universe = {k: v for k, v in metadata.items() if not _is_smart_date(k)}

    try:
        resolved = resolve_smart_dates(smart_dates, universe, date_context)
    except ValidationError as exc:
        raise DiscoveryError(str(exc), path)

    result = metadata.copy()
    for key, value in resolved.items():
        result[key] = value

    return result


def _resolve_smart_dates_in_release_time(release_time, metadata, path, date_context):
    # the release time can be None, or a datetime object
    if not isinstance(release_time, str):
        return release_time

    smart_dates = {"release_time": release_time}
    # we prepend "metadata." to every key, because the release_time has to reference
    # things in metadata this way
    universe = {"metadata." + k: v for k, v in metadata.items()}

    try:
        resolved = resolve_smart_dates(smart_dates, universe, date_context)[
            "release_time"
        ]
    except ValidationError as exc:
        raise DiscoveryError(str(exc), path)

    if not isinstance(resolved, datetime.datetime):
        raise DiscoveryError("release_time is not a datetime.", path)

    return resolved


def read_publication_file(path, schema=None, date_context=None):
    """Read a :class:`Publication` from a yaml file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    schema : Optional[Schema]
        A schema for validating the publication. Default: None, in which case the
        publication's metadata are not validated.
    date_context : Optional[DateContext]
        A context used to evaluate smart dates. If None, no context is provided.

    Returns
    -------
    Publication
        The publication.

    Raises
    ------
    DiscoveryError
        If the publication file's contents are invalid.

    Notes
    -----

    The file should have a "metadata" key whose value is a dictionary
    of metadata. It should also have an "artifacts" key whose value is a
    dictionary mapping artifact names to artifact definitions.

    Optionally, the file can have a "release_time" key providing a time at
    which the publication should be considered released. It may also have
    a "ready" key; if this is False, the publication will not be considered
    released.

    If the ``schema`` argument is not provided, only very basic validation is
    performed by this function. Namely, the metadata schema and
    required/optional artifacts are not enforced. See the :func:`validate`
    function for validating these aspects of the publication. If the schema is
    provided, :func:`validate` is called as a convenience.


    """
    if date_context is None:
        date_context = DateContext()

    with path.open() as fileobj:
        contents = yaml.load(fileobj, Loader=yaml.Loader)

    # we'll just do a quick check of the file structure first. validating the metadata
    # schema and checking that the right artifacts are provided will be done later
    quick_schema = {
        "ready": {"type": "boolean", "default": True, "nullable": True},
        "release_time": {
            "type": ["datetime", "string"],
            "default": None,
            "nullable": True,
        },
        "metadata": {"type": "dict", "required": False, "default": {}},
        "artifacts": {
            "required": True,
            "valuesrules": {
                "schema": {
                    "file": {"type": "string", "default": None, "nullable": True},
                    "recipe": {"type": "string", "default": None, "nullable": True},
                    "ready": {"type": "boolean", "default": True, "nullable": True},
                    "missing_ok": {"type": "boolean", "default": False},
                    "release_time": {
                        "type": "smartdatetime",
                        "default": None,
                        "nullable": True,
                    },
                }
            },
        },
    }

    # validate and normalize the contents
    validator = _PublicationValidator(quick_schema, require_all=True)
    validated = validator.validated(contents)

    if validated is None:
        raise DiscoveryError(str(validator.errors), path)

    metadata = validated["metadata"]

    if hasattr(schema, "metadata_schema"):
        metadata = _resolve_smart_dates_in_metadata(
            metadata, schema.metadata_schema, path, date_context
        )

    # convert each artifact to an Artifact object
    artifacts = {}
    for key, definition in validated["artifacts"].items():
        # handle relative release times
        definition["release_time"] = _resolve_smart_dates_in_release_time(
            definition["release_time"], metadata, path, date_context
        )

        # if no file is provided, use the key
        if definition["file"] is None:
            definition["file"] = key

        artifacts[key] = UnbuiltArtifact(workdir=path.parent.absolute(), **definition)

    # handle publication release time
    release_time = _resolve_smart_dates_in_release_time(
        validated["release_time"], metadata, path, date_context
    )

    publication = Publication(
        metadata=metadata,
        artifacts=artifacts,
        ready=validated["ready"],
        release_time=release_time,
    )

    if schema is not None:
        try:
            validate(publication, against=schema)
        except ValidationError as exc:
            raise DiscoveryError(str(exc), path)

    return publication


# discovery: discover()
# --------------------------------------------------------------------------------------


class DiscoverCallbacks:
    """Callbacks used in :func:`discover`. Defaults do nothing."""

    def on_collection(self, path):
        """When a collection is discovered.

        Parameters
        ----------
        path : pathlib.Path
            The path of the collection file.

        """

    def on_publication(self, path):
        """When a publication is discovered.

        Parameters
        ----------
        path : pathlib.Path
            The path of the publication file.

        """

    def on_skip(self, path):
        """When a directory is skipped.

        Parameters
        ----------
        path : pathlib.Path
            The path of the directory to be skipped.

        """


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

        is_collection = (node.path / constants.COLLECTION_FILE).is_file()
        is_publication = (node.path / constants.PUBLICATION_FILE).is_file()

        if is_collection and is_publication:
            raise DiscoveryError("Cannot be both a publication and a collection.", path)

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
    input_directory: pathlib.Path,
    skip_directories: typing.Optional[typing.Collection[str]] = None,
    callbacks: typing.Optional[DiscoverCallbacks] = None,
) -> Universe:
    """Discover the collections and publications in the filesystem.

    Parameters
    ----------
    input_directory
        The path to the directory that will be recursively searched.
    skip_directories
        A collection of directory names that should be skipped if discovered.
        If None, no directories will be skipped.
    callbacks : Optional[DiscoverCallbacks]
        Callbacks to be invoked during the discovery. If omitted, no callbacks
        are executed. See :class:`DiscoverCallbacks` for the possible callbacks
        and their arguments.

    Returns
    -------
    Universe
        The collections and the nested publications and artifacts, contained in
        a :class:`Universe` instance.

    """
    if skip_directories is None:
        skip_directories = set()

    if callbacks is None:
        callbacks = DiscoverCallbacks()

    # the collection publications are added to if they belong to no other collection
    default_schema = Schema(
        required_artifacts=[], metadata_schema=None, allow_unspecified_artifacts=True,
    )
    default_collection = Collection(schema=default_schema, publications={})

    # by default, we have just the default collection; we'll discover more
    collections = {"default": default_collection}

    # we will run a BFS to discover the collection -> publication -> archive
    # hierarchy. each BFS node will be a triple of the current directory, the
    # parent collection, and the path to the parent collection's directory
    initial_node = _BFSNode(
        path=input_directory,
        parent_collection=default_collection,
        parent_collection_path=input_directory,
    )

    # to simplify the code, our BFS function will outsource the creation and validation
    # of our new collection/publication to the below callbacks functions

    def make_collection(node: _BFSNode):
        """Called when a new collection is discovered. Creates/returns collection."""
        path, parent_collection, parent_collection_path = node

        # ensure no nested collections
        if parent_collection is not default_collection:
            raise DiscoveryError("Nested collection found.", path)

        # create the collection
        collection_file = path / constants.COLLECTION_FILE
        new_collection = read_collection_file(collection_file)

        # add it to the rest of the collections
        key = str(path.relative_to(input_directory))
        collections[key] = new_collection

        # callback
        callbacks.on_collection(collection_file)

        # return the new collection
        return collections[key]

    def make_publication(node: _BFSNode):
        """Called when a new publication is discovered."""
        path, parent_collection, parent_collection_path = node

        # read the publication file
        publication_file = path / constants.PUBLICATION_FILE

        try:
            publication = read_publication_file(
                publication_file, schema=parent_collection.schema
            )
        except ValidationError as exc:
            raise DiscoveryError(str(exc), publication_file)

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
