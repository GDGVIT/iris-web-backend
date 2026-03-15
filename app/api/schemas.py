from typing import Any

from marshmallow import Schema, fields, post_load, validate

from app.core.models import SearchRequest


class SearchRequestSchema(Schema):
    """Schema for pathfinding search requests."""

    start = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255),
        error_messages={"required": "Start page is required"},
    )
    end = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255),
        error_messages={"required": "End page is required"},
    )
    max_depth = fields.Int(
        load_default=None, validate=validate.Range(min=1, max=10), allow_none=True
    )
    algorithm = fields.Str(
        load_default="bidirectional",
        validate=validate.OneOf(["bfs", "bidirectional"]),
        allow_none=True,
    )

    @post_load
    def make_request(self, data, **kwargs):
        """Convert validated data to SearchRequest object."""
        return SearchRequest(
            start_page=data["start"].strip(),
            end_page=data["end"].strip(),
            max_depth=data.get("max_depth"),
            algorithm=data.get("algorithm", "bidirectional"),
        )


class ErrorResponseSchema(Schema):
    """Schema for error responses."""

    error = fields.Bool(required=True, dump_default=True)
    message = fields.Str(required=True)
    code = fields.Str(allow_none=True)
    details = fields.Dict(allow_none=True)


def validate_request_data(schema_class: type[Schema], data: Any) -> Any:
    """
    Validate request data using the specified schema.

    Args:
        schema_class: Marshmallow schema class
        data: Data to validate

    Returns:
        Validated and deserialized data

    Raises:
        ValidationError: When validation fails
    """
    schema = schema_class()
    return schema.load(data)  # Let the original ValidationError bubble up
