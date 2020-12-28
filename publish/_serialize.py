import json
import datetime

from .types import Artifact, Publication, Collection, Universe


# serialization
# --------------------------------------------------------------------------------------


def serialize(node):
    """Serialize the universe/collection/publication/artifact to JSON.

    Parameters
    ----------
    node : Union[Universe, Collection, Publication, Artifact]
        The thing to serialize as JSON.

    Returns
    -------
    str
        The object serialized as JSON.

    """

    def converter(o):
        return str(o)

    if isinstance(node, Artifact):
        dct = node._asdict()
    else:
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
    """Reconstruct a universe/collection/publication/artifact from JSON.

    Parameters
    ----------
    s : str
        The JSON to deserialize.

    Returns
    -------
    Universe/Collection/Publication/Artifact
        The reconstructed object; its type is inferred from the string.

    """
    # we need to pass a hook to json.loads in order to automatically convert
    # datestring to date/datetime objects
    def hook(pairs):
        """Hook for json.loads to convert date/time-like values."""
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

    # infer what we're reconstructing
    if "collections" in dct:
        type_ = Universe
        children_key = "collections"
    elif "publications" in dct:
        type_ = Collection
        children_key = "publications"
    elif "artifacts" in dct:
        type_ = Publication
        children_key = "artifacts"
    else:
        return _artifact_from_dict(dct)

    return type_._deep_fromdict(dct)
