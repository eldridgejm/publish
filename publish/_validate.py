import cerberus
import datetime

from .types import Publication, Schema
from .exceptions import ValidationError

# validation
# --------------------------------------------------------------------------------------


class _PublicationValidator(cerberus.Validator):
    """A subclassed cerberus Validator with special "smart date" data types."""

    types_mapping = cerberus.Validator.types_mapping.copy()

    types_mapping["smartdate"] = cerberus.TypeDefinition(
        "smartdate", (str, datetime.date), ()
    )

    types_mapping["smartdatetime"] = cerberus.TypeDefinition(
        "smartdate", (str, datetime.datetime), ()
    )


def validate(publication: Publication, against: Schema):
    """Make sure that a publication satisfies the schema.

    This checks the publication's metadata dictionary against
    ``against.metadata_schema``. Verifies that all required artifacts are
    provided, and that no unknown artifacts are given (unless
    ``schema.allow_unspecified_artifacts == True``).

    Parameters
    ----------
    publication : Publication
        A fully-specified publication.
    against : Schema
        A schema for validating the publication.

    Raises
    ------
    ValidationError
        If the publication does not satisfy the schema's constraints.

    """
    schema = against

    # make an iterable default for optional artifacts
    if schema.optional_artifacts is None:
        schema = schema._replace(optional_artifacts={})

    # if there is a metadata schema, enforce it
    if schema.metadata_schema is not None:
        validator = _PublicationValidator(schema.metadata_schema, require_all=True)

        # define the smartdate and smartdatetime data types
        validator
        validated = validator.validated(publication.metadata)
        if validated is None:
            raise ValidationError(f"Invalid metadata. {validator.errors}")

    # ensure that all required artifacts are present
    required = set(schema.required_artifacts)
    optional = set(schema.optional_artifacts)
    provided = set(publication.artifacts)
    extra = provided - (required | optional)

    if required - provided:
        raise ValidationError(f"Required artifacts omitted: {required - provided}.")

    if extra and not schema.allow_unspecified_artifacts:
        raise ValidationError(f"Unknown artifacts provided: {provided - optional}.")
