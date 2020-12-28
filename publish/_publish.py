import pathlib
import shutil
import re

from .types import BuiltArtifact, PublishedArtifact


# publishing
# --------------------------------------------------------------------------------------


class PublishCallbacks:
    def on_copy(self, src, dst):
        """Called when copying a file."""

    def on_publish(self, key, node):
        """When publish is called on a node."""


def _publish_artifact(built_artifact, outdir, filename, callbacks):

    # actually copy the artifact
    full_dst = outdir / filename
    full_dst.parent.mkdir(parents=True, exist_ok=True)
    full_src = built_artifact.workdir / built_artifact.file
    callbacks.on_copy(full_src, full_dst)
    shutil.copy(full_src, full_dst)

    return PublishedArtifact(path=full_dst.relative_to(outdir))


def publish(parent, outdir, prefix="", callbacks=None):
    """Publish a universe/collection/publication/artifact by copying it.

    Parameters
    ----------
    parent : Union[Universe, Collection, Publication, BuiltArtifact]
        The thing to publish.
    outdir : pathlib.Path
        Path to the output directory where artifacts will be copied.
    prefix : str
        String to prepend between output directory path and the keys of the
        children. If the thing being published is a :class:`BuiltArtifact`,
        this is simply the filename.
    callbacks : PublishCallbacks
        Callbacks to be invoked during the publication. If omitted, no
        callbacks are executed. See :class:`PublishCallbacks` for the possible
        callbacks and their arguments.

    Returns
    -------
    type(parent)
        A copy of the parent, but with all leaf artifact nodes replace by
        :class:`PublishedArtifact` instances. Artifacts which have not yet
        been released are still converted to PublishedArtifact, but their ``path``
        is set to ``None``.
    
    Notes
    -----
    The prefix is build up recursively, so that calling this function on a
    universe will publish each artifact to 
    ``<prefix><collection_key>/<publication_key>/<artifact_key>``

    """
    if callbacks is None:
        callbacks = PublishCallbacks()

    if isinstance(parent, BuiltArtifact):
        return _publish_artifact(parent, outdir, prefix, callbacks)

    new_children = {}
    for child_key, child in parent._children.items():
        callbacks.on_publish(child_key, child)
        new_prefix = pathlib.Path(prefix) / child_key
        new_children[child_key] = publish(child, outdir, new_prefix, callbacks)

    return parent._replace_children(new_children)
