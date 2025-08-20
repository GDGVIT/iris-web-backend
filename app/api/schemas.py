from marshmallow import Schema, fields, validate, post_load
from app.core.models import SearchRequest, ExploreRequest


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
        load_default="bfs",
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
            algorithm=data.get("algorithm", "bfs"),
        )


class ExploreRequestSchema(Schema):
    """Schema for page exploration requests."""

    start = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255),
        error_messages={"required": "Start page is required"},
    )
    max_links = fields.Int(load_default=10, validate=validate.Range(min=1, max=50))

    @post_load
    def make_request(self, data, **kwargs):
        """Convert validated data to ExploreRequest object."""
        return ExploreRequest(
            start_page=data["start"].strip(), max_links=data.get("max_links", 10)
        )


class PathResultSchema(Schema):
    """Schema for pathfinding results."""

    path = fields.List(fields.Str(), required=True)
    length = fields.Int(required=True)
    start_page = fields.Str(required=True)
    end_page = fields.Str(required=True)
    search_time = fields.Float(allow_none=True)
    nodes_explored = fields.Int(allow_none=True)


class ExploreResultSchema(Schema):
    """Schema for exploration results."""

    start_page = fields.Str(required=True)
    nodes = fields.List(fields.Str(), required=True)
    edges = fields.List(fields.Tuple((fields.Str(), fields.Str())), required=True)
    total_links = fields.Int(required=True)


class TaskStatusSchema(Schema):
    """Schema for task status responses."""

    status = fields.Str(required=True)
    task_id = fields.Str(required=True)
    result = fields.Dict(allow_none=True)
    error = fields.Str(allow_none=True)
    progress = fields.Dict(allow_none=True)
    poll_url = fields.Str(allow_none=True)


class ErrorResponseSchema(Schema):
    """Schema for error responses."""

    error = fields.Bool(required=True, dump_default=True)
    message = fields.Str(required=True)
    code = fields.Str(allow_none=True)
    details = fields.Dict(allow_none=True)


class HealthCheckSchema(Schema):
    """Schema for health check responses."""

    status = fields.Str(required=True)
    redis_status = fields.Str(required=True)
    celery_status = fields.Str(required=True)
    wikipedia_api_status = fields.Str(required=True)
    timestamp = fields.Str(required=True)
    details = fields.Dict(allow_none=True)


def validate_request_data(schema_class, data):
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


def serialize_response(schema_class, data):
    """
    Serialize response data using the specified schema.

    Args:
        schema_class: Marshmallow schema class
        data: Data to serialize

    Returns:
        Serialized data
    """
    schema = schema_class()
    return schema.dump(data)
