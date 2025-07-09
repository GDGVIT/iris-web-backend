from flask import Blueprint, request, jsonify
import requests
from app.tasks import find_path_task
from app.services import generate_explore_graph
from flask import current_app
import time

main = Blueprint("main", __name__)


def verify_recaptcha(token):
    """Helper function to verify Google reCAPTCHA."""
    secret_key = current_app.config["RECAPTCHA_SECRET_KEY"]
    if not token or not secret_key:
        return False, "reCAPTCHA token or secret key is missing"

    url = f"https://www.google.com/recaptcha/api/siteverify"
    params = {"secret": secret_key, "response": token, "remoteip": request.remote_addr}
    response = requests.get(url, params=params)
    res = response.json()
    return res.get("success", False), res.get("error-codes", "Verification failed")


@main.route("/getPath", methods=["POST"])
def get_path_route():
    # # --- reCAPTCHA Verification ---
    # token = request.headers.get("g-recaptcha-response")
    # success, error_msg = verify_recaptcha(token)
    # if not success:
    #     return jsonify({"error": True, "message": str(error_msg)}), 400

    # --- Main Logic ---
    data = request.get_json()
    start_page = data.get("start")
    end_page = data.get("end")

    print("I got here")

    if not start_page or not end_page:
        return (
            jsonify({"error": True, "message": "Start and end pages are required."}),
            400,
        )

    # Always send the task to the background worker and return a task ID
    task = find_path_task.delay(start_page, end_page)
    return (
        jsonify(
            {
                "status": "IN_PROGRESS",
                "task_id": task.id,
                "poll_url": f"/tasks/status/{task.id}",
            }
        ),
        202,
    )


@main.route("/tasks/status/<task_id>", methods=["GET"])
def get_task_status_route(task_id):
    """Endpoint to poll for a task's status using Celery's native result backend."""
    task = find_path_task.AsyncResult(task_id)

    if task.state == "PENDING":
        response = {"status": "PENDING", "result": "Task is waiting to be processed."}
    elif task.state == "SUCCESS":
        response = task.result
    else:
        response = {
            "status": task.state,
            "result": str(task.info),
        }

    return jsonify(response)


@main.route("/explore", methods=["POST"])
def explore_route():
    # --- reCAPTCHA Verification ---
    token = request.headers.get("g-recaptcha-response")
    success, error_msg = verify_recaptcha(token)
    if not success:
        return jsonify({"error": True, "message": str(error_msg)}), 400

    # --- Main Logic ---
    data = request.get_json()
    start_page = data.get("start")
    if not start_page:
        return jsonify({"error": True, "message": "Start page is required."}), 400

    nodes, edges = generate_explore_graph(start_page)
    if nodes is None:
        return (
            jsonify({"error": True, "message": f"Page '{start_page}' does not exist."}),
            404,
        )

    return jsonify({"nodes": nodes, "edges": edges}), 200
