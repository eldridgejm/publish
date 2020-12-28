from .types import UnbuiltArtifact, BuiltArtifact, PublishedArtifact


# filter_nodes()
# --------------------------------------------------------------------------------------


class FilterCallbacks:
    def on_hit(self, x):
        """On an artifact match."""

    def on_miss(self, x):
        """On an artifact miss."""


def filter_nodes(parent, predicate, remove_empty_nodes=False, callbacks=None):
    """Remove nodes from a Universe/Collection/Publication.

    Parameters
    ----------
    parent
        The root of the tree.
    predicate : Callable[[node], bool]
        A function which takes in a node and returns True/False whether it
        should be kept.
    remove_empty_nodes : bool
        Whether nodes without children should be removed (True) or preserved
        (False). Default: False.
    
    Returns
    -------
    type(parent)
        An object of the same type as the parent, but wth all filtered nodes
        removed. Furthermore, if a node has no children after filtering, it
        is removed.

    """
    # bottom up -- by the time the predicate is applied to publication, its artifacts
    # have been filtered

    if isinstance(parent, (UnbuiltArtifact, BuiltArtifact, PublishedArtifact)):
        return parent

    new_children = {}
    for child_key, child in parent._children.items():
        new_child = filter_nodes(
            child, predicate, remove_empty_nodes=remove_empty_nodes, callbacks=callbacks
        )
        is_artifact = isinstance(
            new_child, (UnbuiltArtifact, BuiltArtifact, PublishedArtifact)
        )
        if is_artifact or (not remove_empty_nodes) or new_child._children:
            new_children[child_key] = new_child

    new_children = {k: v for (k, v) in new_children.items() if predicate(k, v)}

    return parent._replace_children(new_children)
