import publish


def test_collection_as_dict():
    # given
    collection = publish.Collection(
        schema=publish.Schema(required_artifacts=["foo", "bar"]), publications={}
    )

    collection.publications["01-intro"] = publish.Publication(
        metadata={"name": "testing"},
        artifacts={
            "homework": publish.ArtifactInputs(
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
