import typing
import pathlib
import datetime


# types
# --------------------------------------------------------------------------------------


class Artifact:
    """Base class for all artifact types."""


class UnbuiltArtifact(Artifact, typing.NamedTuple):
    """The inputs needed to build an artifact.

    Attributes
    ----------
    workdir : pathlib.Path
        Absolute path to the working directory used to build the artifact.
    file : str
        Path (relative to the workdir) of the file produced by the build.
    recipe : Union[str, None]
        Command used to build the artifact. If None, no command is necessary.
    release_time: Union[datetime.datetime, None]
        Time/date the artifact should be made public. If None, it is always available.
    ready : bool
        Whether or not the artifact is ready for publication. Default: True.
    missing_ok : bool
        If True and the file is missing after building, then no error is raised and the
        result of the build is `None`.

    """

    workdir: pathlib.Path
    file: str
    recipe: str = None
    release_time: datetime.datetime = None
    ready: bool = True
    missing_ok: bool = False


class BuiltArtifact(Artifact, typing.NamedTuple):
    """The results of building an artifact.

    Attributes
    ----------
    workdir : pathlib.Path
        Absolute path to the working directory used to build the artifact.
    file : str
        Path (relative to the workdir) of the file produced by the build.
    returncode : int
        The build process's return code. If None, there was no process.
    stdout : str
        The build process's stdout. If None, there was no process.
    stderr : str
        The build process's stderr. If None, there was no process.

    """

    workdir: pathlib.Path
    file: str
    returncode: int = None
    stdout: str = None
    stderr: str = None


class PublishedArtifact(Artifact, typing.NamedTuple):
    """A published artifact.

    Attributes
    ----------
    path : str
        The path to the artifact's file relative to the output directory.

    """

    path: str


def _artifact_from_dict(dct):
    """Infers the artifact type from the dictionary and performs conversion."""
    if "recipe" in dct:
        type_ = UnbuiltArtifact
    elif "returncode" in dct:
        type_ = BuiltArtifact
    else:
        type_ = PublishedArtifact

    return type_(**dct)


# the following are "Internal Nodes" of the collection -> publication ->
# artifact hierarchy. they all have _children attributes and _deep_asdict
# and _replace_children methods>


class Publication(typing.NamedTuple):
    """A publication.

    Attributes
    ----------
    artifacts : Dict[str, Artifact]
        The artifacts contained in the publication.
    metadata: Dict[str, Any]
        The metadata dictionary.
    ready: Optional[bool]
        If False, this publication is not ready and will not be published.
    release_time: Optional[datetime.datetime]
        The time before which this publication will not be released.

    """

    metadata: typing.Mapping[str, typing.Any]
    artifacts: typing.Mapping[str, Artifact]
    ready: bool = True
    release_time: datetime.datetime = None

    def _deep_asdict(self):
        """A dictionary representation of the publication and its children."""
        return {
            "metadata": self.metadata,
            "artifacts": {k: a._asdict() for (k, a) in self.artifacts.items()},
        }

    @classmethod
    def _deep_fromdict(cls, dct):
        return cls(
            metadata=dct["metadata"],
            artifacts={
                k: _artifact_from_dict(d) for (k, d) in dct["artifacts"].items()
            },
        )

    @property
    def _children(self):
        return self.artifacts

    def _replace_children(self, new_children):
        return self._replace(artifacts=new_children)


class Collection(typing.NamedTuple):
    """A collection.

    Attributes
    ----------
    schema : Schema
        The schema used to validate the publications within the collection.
    publications : Mapping[str, Publication]
        The publications contained in the collection.

    """

    schema: "Schema"
    publications: typing.Mapping[str, Publication]

    def _deep_asdict(self):
        """A dictionary representation of the collection and its children."""
        return {
            "schema": self.schema._asdict(),
            "publications": {
                k: p._deep_asdict() for (k, p) in self.publications.items()
            },
        }

    @classmethod
    def _deep_fromdict(cls, dct):
        return cls(
            schema=Schema(**dct["schema"]),
            publications={
                k: Publication._deep_fromdict(d)
                for (k, d) in dct["publications"].items()
            },
        )

    @property
    def _children(self):
        return self.publications

    def _replace_children(self, new_children):
        return self._replace(publications=new_children)


class Universe(typing.NamedTuple):
    """Container of all collections.

    Attributes
    ----------

    collections : Dict[str, Collection]
        The collections.

    """

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

    @classmethod
    def _deep_fromdict(cls, dct):
        return cls(
            collections={
                k: Collection._deep_fromdict(d) for (k, d) in dct["collections"].items()
            },
        )


class Schema(typing.NamedTuple):
    """Rules governing publications.

    Attributes
    ----------
    required_artifacts : typing.Collection[str]
        Names of artifacts that publications must contain.
    optional_artifacts : typing.Collection[str], optional
        Names of artifacts that publication are permitted to contain. Default: empty
        list.
    metadata_schema : Mapping[str, Any], optional
        A dictionary describing a schema used to validate publication metadata. In the
        style of cerberus. If None, no validation will be performed. Default: None.
    allow_unspecified_artifacts : Optional[Boolean]
        Is it permissible for a publication to have unknown artifacts? Default: False.
    is_ordered : Optional[Boolean]
        Should the publications be considered ordered by their keys? Default: False

    """

    required_artifacts: typing.Collection[str]
    optional_artifacts: typing.Collection[str] = None
    metadata_schema: typing.Mapping[str, typing.Mapping] = None
    allow_unspecified_artifacts: bool = False
    is_ordered: bool = False


class DateContext(typing.NamedTuple):
    """A context used to resolve smart dates.

    Attributes
    ----------
    known : Optional[Mapping[str, datetime]]
        A dictionary of known dates. If None, there are no known dates.
    start_of_week_one : Optional[datetime.date]
        What should be considered the start of "week 1". If None, smart dates referring
        to weeks cannot be used.

    """

    known: dict = None
    start_of_week_one: typing.Optional[datetime.date] = None
