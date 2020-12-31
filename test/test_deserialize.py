import json
import datetime
import pathlib

import publish


def test_serialize_deserialize_universe_roundtrip():
    # given
    collection = publish.Collection(
        schema=publish.Schema(required_artifacts=["foo", "bar"]), publications={}
    )

    collection.publications["01-intro"] = publish.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={"homework": publish.PublishedArtifact("foo/bar")},
    )

    original = publish.Universe({"homeworks": collection})

    # when
    s = publish.serialize(original)
    result = publish.deserialize(s)

    # then
    assert original == result


def test_serialize_deserialize_built_publication_roundtrip():
    # given
    publication = publish.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={"homework": publish.BuiltArtifact(workdir=None, file="foo/bar")},
    )

    # when
    s = publish.serialize(publication)
    result = publish.deserialize(s)

    # then
    assert publication == result


# misc.
# --------------------------------------------------------------------------------------


def test_collection_as_dict():
    # given
    collection = publish.Collection(
        schema=publish.Schema(required_artifacts=["foo", "bar"]), publications={}
    )

    collection.publications["01-intro"] = publish.Publication(
        metadata={"name": "testing"},
        artifacts={
            "homework": publish.UnbuiltArtifact(
                workdir=None, file="homework.pdf", recipe="make", release_time=None
            ),
        },
    )

    # when
    d = collection._deep_asdict()

    # then
    assert d["schema"]["required_artifacts"] == ["foo", "bar"]
    assert (
        d["publications"]["01-intro"]["artifacts"]["homework"]["file"] == "homework.pdf"
    )
