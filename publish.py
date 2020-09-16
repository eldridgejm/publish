"""
publish
=======

A script to build and publish artifacts.

Terminology
-----------

An **artifact** is a file — usually one generated by code.

A **publication** is a coherent group of zero or more artifacts and their
metadata. A publication is defined in a `publish.yaml` file.

A publication may or may not belong to a **collection**. A collection is
defined in a `collection.yaml` file. It describes the schema to which all
publications in the collection must adhere.

An example of a collection is that of all *homeworks*. An example of a
publication is an individual *homework* within the collection. And an example
of an artifact is the pdf of the homework's solutions.

"""

import typing
import pathlib
import yaml
from textwrap import dedent

import cerberus


class Error(Exception):
    """Generic error."""


class SchemaError(Error):
    """Invalid configuration file."""


class Artifact(typing.NamedTuple):
    file: str
    recipe: str
    workdir: pathlib.Path


class Publication(typing.NamedTuple):
    metadata: typing.Mapping[str, typing.Any]
    artifacts: typing.Mapping[str, Artifact]


class Collection(typing.NamedTuple):
    metadata_schema: str
    required_artifacts: typing.List[str]
    optional_artifacts: typing.List[str]
    allow_unspecified_artifacts: bool
    publications: typing.Mapping[str, Publication]


def read_collection_file(path):
    with path.open() as fileobj:
        contents = yaml.load(fileobj, Loader=yaml.Loader)

    # define the structure of the collections file. we require only the
    # 'required_artifacts' field.
    validator = cerberus.Validator(
        {
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
            "metadata_schema": {"type": "dict", "default": {}},
            "allow_unspecified_artifacts": {"type": "boolean", "default": False},
        }
    )

    validated_contents = validator.validated(contents)

    if validated_contents is None:
        raise SchemaError(f"Error loading {path}. {validator.errors}")

    # make sure that the metadata schema is valid
    try:
        cerberus.Validator(validated_contents["metadata_schema"])
    except Exception:
        raise SchemaError(f"Error loading {path}. Invalid metadata schema.")

    return Collection(publications={}, **validated_contents)


def _validate_artifact(workdir, definition):
    # validate and extract the artifacts
    artifact_validator = cerberus.Validator(
        {"file": {"type": "string"}, "recipe": {"type": "string", "default": None}}
    )

    artifact = artifact_validator.validated(definition)
    if artifact is None:
        raise SchemaError(f"{validator.errors}")

    return Artifact(workdir=workdir, **artifact)


def read_publication_file(path, collection):
    with path.open() as fileobj:
        contents = yaml.load(fileobj, Loader=yaml.Loader)

    if "artifacts" not in contents:
        raise SchemeError(f"{path} has no artifacts section.")

    # make sure that all necessary artifacts are specified
    provided_artifacts = set(contents["artifacts"])
    missing = set(collection.required_artifacts) - set(provided_artifacts)
    extra = set(provided_artifacts) - (
        set(collection.required_artifacts) | set(collection.optional_artifacts)
    )

    if missing:
        raise SchemaError(f"Missing artifacts {missing} in {path}.")

    if extra and not collection.allow_unspecified_artifacts:
        raise SchemaError(f"Extra artifacts {extra} in {path}.")

    artifacts = {}
    for key, definition in contents['artifacts'].items():
        try:
            artifacts[key] = _validate_artifact(path.parent, definition)
        except SchemaError as exc:
            raise SchemaError(f'Invalid {path}: {exc}')

    # everything besides the artifacts makes up the metadata
    metadata = contents.copy()
    del metadata["artifacts"]

    metadata_validator = cerberus.Validator(collection.metadata_schema)
    metadata = metadata_validator.validated(metadata)

    if metadata is None:
        raise SchemaError(f'Invalid metadata in {path}: {metadata.errors}')

    return Publication(metadata=metadata, artifacts=artifacts)
