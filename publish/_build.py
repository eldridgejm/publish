import datetime
import subprocess
import pathlib
import typing


from .types import UnbuiltArtifact, BuiltArtifact, Universe, Collection, Publication
from .exceptions import BuildError


# building
# --------------------------------------------------------------------------------------


class BuildCallbacks:
    """Callbacks used by :func:`build`"""

    def on_build(self, key, node):
        """Called when building a collection/publication/artifact."""

    def on_too_soon(self, artifact: UnbuiltArtifact):
        """Called when it is too soon to release the artifact."""

    def on_not_ready(self, artifact: UnbuiltArtifact):
        """Called when the artifact is not ready."""

    def on_missing(self, artifact: UnbuiltArtifact):
        """Called when the artifact file is missing, but missing is OK."""

    def on_recipe(self, artifact: UnbuiltArtifact):
        """Called when artifact is being built using its recipe."""

    def on_success(self, artifact: BuiltArtifact):
        """Called when the build succeeded."""


def _build_artifact(
    artifact,
    *,
    ignore_release_time=False,
    now=datetime.datetime.now,
    verbose=False,
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
    Optional[BuiltArtifact]
        A summary of the build results. The result is `None` if the build time
        is in the future, or if the file was not created and missing_ok is
        True.

    """
    output = BuiltArtifact(workdir=artifact.workdir, file=artifact.file)

    if (
        not ignore_release_time
        and artifact.release_time is not None
        and artifact.release_time > now()
    ):
        callbacks.on_too_soon(artifact)
        return None

    if not artifact.ready:
        callbacks.on_not_ready(artifact)
        return None

    if artifact.recipe is None:
        stdout = None
        stderr = None
        returncode = None
    else:
        callbacks.on_recipe(artifact)

        kwargs = {
            "cwd": artifact.workdir,
        }
        if not verbose:
            kwargs["stdout"] = subprocess.PIPE
            kwargs["stderr"] = subprocess.PIPE

        proc = run(artifact.recipe, shell=True, **kwargs)

        if proc.returncode:
            msg = "There was a problem while building the artifact"
            if proc.stderr is not None:
                msg += f":\n{proc.stderr.decode()}"
            raise BuildError(msg)

        returncode = proc.returncode
        stdout = None if proc.stdout is None else proc.stdout.decode()
        stderr = None if proc.stderr is None else proc.stderr.decode()

    filepath = artifact.workdir / artifact.file
    if not exists(filepath):
        if artifact.missing_ok:
            callbacks.on_missing(artifact)
            return None
        else:
            raise BuildError(f"Artifact file {filepath} does not exist.")

    output = output._replace(returncode=returncode, stdout=stdout, stderr=stderr)
    callbacks.on_success(output)
    return output


def build(
    parent: typing.Union[Universe, Collection, Publication, UnbuiltArtifact],
    *,
    ignore_release_time=False,
    verbose=False,
    now=datetime.datetime.now,
    run=subprocess.run,
    exists=pathlib.Path.exists,
    callbacks=None,
):
    """Build a universe/collection/publication/artifact.

    Parameters
    ----------
    parent : Union[Universe, Collection, Publication, UnbuiltArtifact]
        The thing to build. Operates recursively, so if given a
        :class:`Universe`, for instance, will build all of the artifacts
        within.
    ignore_release_time : bool
        If ``True``, all artifacts will be built, even if their release time
        has not yet passed.
    callbacks : Optional[BuildCallbacks]
        Callbacks to be invoked during the build. If omitted, no callbacks
        are executed. See :class:`BuildCallbacks` for the possible callbacks
        and their arguments.

    Returns
    -------
    Optional[type(parent)]
        A copy of the parent where each leaf artifact is replaced with
        an instance of :class:`BuiltArtifact`. If the thing to be built is not
        built due to being unreleased, ``None`` is returned.

    Note
    ----
    If a publication or artifact is not yet released, either due to its release
    time being in the future or because it is marked as not ready, its recipe will
    not be run. If the parent node is a publication or artifact that is not
    built, the result of this function is None. If the parent node is a collection
    or universe, all of the unbuilt publications and artifacts within are
    recursively removed from the tree.

    """
    if callbacks is None:
        callbacks = BuildCallbacks()

    kwargs = dict(
        ignore_release_time=ignore_release_time,
        now=now,
        run=run,
        verbose=verbose,
        exists=exists,
        callbacks=callbacks,
    )

    if isinstance(parent, UnbuiltArtifact):
        return _build_artifact(parent, **kwargs)

    if isinstance(parent, Publication):
        if not parent.ready:
            callbacks.on_not_ready(parent)
            return None

        if (
            not ignore_release_time
            and parent.release_time is not None
            and parent.release_time > now()
        ):
            callbacks.on_too_soon(parent)
            return None

    # recursively build the children
    new_children = {}
    for child_key, child in parent._children.items():
        callbacks.on_build(child_key, child)
        result = build(child, **kwargs)
        # if a node is not built (perhaps due to it not being ready), the
        # result is None. this next conditional prevents such nodes from
        # appearing in the tree
        if result is not None:
            new_children[child_key] = result
    return parent._replace_children(new_children)
