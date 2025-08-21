import json as pyjson
import os
import pytest
from flask import Flask, jsonify, Response, request

from app.api import middleware as mw
from app.utils.exceptions import (
    IrisBaseException,
    PathNotFoundError,
    InvalidPageError,
    WikipediaPageNotFoundError,
    CacheConnectionError,
    TaskError,
)
from app.utils.logging import configure_logging


@pytest.fixture()
def flask_app():
    app = Flask(__name__)
    return app


def make_request_context(app, method="GET", json=None, headers=None, data=None):
    headers = headers or {}
    if json is not None:
        headers.setdefault("Content-Type", "application/json")
        data = pyjson.dumps(json)
    return app.test_request_context("/t", method=method, headers=headers, data=data)


def test_handle_validation_and_application_errors(flask_app):
    @mw.handle_validation_errors
    def fn_val():
        from marshmallow import ValidationError

        raise ValidationError({"f": ["bad"]})

    @mw.handle_application_errors
    def fn_path():
        raise PathNotFoundError("A", "B")

    @mw.handle_application_errors
    def fn_invalid():
        raise InvalidPageError(page_title="X")

    @mw.handle_application_errors
    def fn_wiki():
        raise WikipediaPageNotFoundError("X")

    @mw.handle_application_errors
    def fn_cache():
        raise CacheConnectionError("down")

    @mw.handle_application_errors
    def fn_task():
        raise TaskError("oops")

    @mw.handle_application_errors
    def fn_app():
        raise IrisBaseException("nope")

    @mw.handle_application_errors
    def fn_other():
        raise RuntimeError("boom")

    with make_request_context(flask_app, method="POST", json={"x": 1}):
        resp, code = fn_val()
        assert code == 400 and resp.json["code"] == "VALIDATION_ERROR"

        resp, code = fn_path()
        assert code == 404 and resp.json["code"] == "PATH_NOT_FOUND"

        resp, code = fn_invalid()
        assert code == 400 and resp.json["code"] == "INVALID_PAGE"

        resp, code = fn_wiki()
        assert code == 404 and resp.json["code"] == "WIKIPEDIA_PAGE_NOT_FOUND"

        resp, code = fn_cache()
        assert code == 503 and resp.json["code"] == "CACHE_ERROR"

        resp, code = fn_task()
        assert code == 500 and resp.json["code"] == "TASK_ERROR"

        resp, code = fn_app()
        assert code == 500 and resp.json["code"] == "APPLICATION_ERROR"

        resp, code = fn_other()
        assert code == 500 and resp.json["code"] == "INTERNAL_ERROR"


def test_log_requests_and_require_json(flask_app):
    @mw.log_requests
    def ok_handler():
        return {"ok": True}, 201

    @mw.log_requests
    def err_handler():
        raise ValueError("bad")

    @mw.require_json
    def requires_json():
        return {"ok": True}

    with make_request_context(flask_app, method="POST", json={"a": 1}):
        resp, code = ok_handler()
        assert code == 201 and resp["ok"] is True

    with pytest.raises(ValueError):
        with make_request_context(flask_app, method="POST", json={"a": 1}):
            err_handler()

    with make_request_context(flask_app, method="POST", headers={}):
        resp, code = requires_json()
        assert code == 400 and resp.json["code"] == "INVALID_CONTENT_TYPE"

    with make_request_context(flask_app, method="POST", json={"a": 1}):
        assert requires_json() == {"ok": True}


def test_rate_limit_and_cors_and_validate_request_size(flask_app):
    @mw.rate_limit(10)
    def inner():
        return {"ok": True}

    @mw.cors_headers
    def raw_tuple():
        return {"a": 1}, 202

    @mw.cors_headers
    def resp_obj():
        r = jsonify({"a": 1})
        return r, 202

    @mw.validate_request_size(1)
    def sized():
        return {"ok": True}

    with make_request_context(flask_app):
        assert inner() == {"ok": True}

    with make_request_context(flask_app):
        r = raw_tuple()
        assert hasattr(r, "headers")
        assert r.headers["Access-Control-Allow-Origin"] == "*"
        assert r.status_code == 202

    with make_request_context(flask_app):
        r = resp_obj()
        assert r.headers["Access-Control-Allow-Methods"]

    # too large (send actual large body so content_length is set)
    large_body = b"x" * (2 * 1024 * 1024)
    with flask_app.test_request_context("/t", method="POST", data=large_body):
        resp, code = sized()
        assert code == 413 and resp.json["code"] == "REQUEST_TOO_LARGE"

    with make_request_context(flask_app, method="POST", json={"x": 1}):
        assert sized() == {"ok": True}


def test_api_endpoint_composition(flask_app):
    @mw.api_endpoint(require_json_content=False, log_request=False, add_cors=True)
    def hello():
        return {"hello": "world"}

    with make_request_context(flask_app):
        r = hello()
        assert hasattr(r, "headers") and r.json == {"hello": "world"}


def test_configure_logging_writes_file_handler(tmp_path):
    app = Flask(__name__)
    app.debug = False
    app.testing = False

    log_dir = tmp_path / "logs_test"
    os.environ["LOG_DIR"] = str(log_dir)
    configure_logging(app)

    # File handler should be added when not debug/testing
    has_file_handler = any(
        h.__class__.__name__ == "RotatingFileHandler" for h in app.logger.handlers
    )
    assert has_file_handler is True
