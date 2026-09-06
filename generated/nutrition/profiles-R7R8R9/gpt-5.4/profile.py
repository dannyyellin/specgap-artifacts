# Required packages: flask, flask_pymongo, requests

from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from pymongo import ReturnDocument
import requests

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/profiledb"
mongo = PyMongo(app)

AUTH_URL = "http://authentication:5001/validate"
DISHES_URL = "http://dishes:5002/dishes"

NUTRITION_FIELDS = [
    "total_fat",
    "saturated_fat",
    "protein",
    "sodium",
    "cholesterol",
    "total_carbohydrates",
    "fiber",
    "sugar",
]


def error_response(message, status_code):
    return jsonify({"error": message}), status_code


def round2(value):
    try:
        return round(float(value), 2)
    except Exception:
        return 0.00


def format_profile(doc):
    if not doc:
        return None
    return {
        "user_id": int(doc["user_id"]),
        "total_fat": round2(doc.get("total_fat", 0.0)),
        "saturated_fat": round2(doc.get("saturated_fat", 0.0)),
        "protein": round2(doc.get("protein", 0.0)),
        "sodium": round2(doc.get("sodium", 0.0)),
        "cholesterol": round2(doc.get("cholesterol", 0.0)),
        "total_carbohydrates": round2(doc.get("total_carbohydrates", 0.0)),
        "fiber": round2(doc.get("fiber", 0.0)),
        "sugar": round2(doc.get("sugar", 0.0)),
    }


def get_token_from_request():
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    token = request.headers.get("token")
    if token:
        return token.strip()
    if request.is_json:
        body = request.get_json(silent=True) or {}
        token = body.get("token")
        if token:
            return str(token).strip()
    return None


def validate_token():
    token = get_token_from_request()
    if not token:
        return None, error_response("Unauthorized", 401)
    try:
        resp = requests.post(AUTH_URL, json={"token": token}, timeout=5)
    except requests.RequestException:
        return None, error_response("Internal Server Error", 500)

    if resp.status_code != 201:
        return None, error_response("Unauthorized", 401)

    data = resp.json()
    if not data.get("valid"):
        return None, error_response("Unauthorized", 401)

    return {
        "user_id": data.get("user_id"),
        "privileged": bool(data.get("privileged", False)),
    }, None


def require_json():
    if not request.is_json:
        return error_response("Unsupported media type", 415)
    return None


def parse_profile_payload(payload):
    if not isinstance(payload, dict):
        return None, "Bad request"

    parsed = {}
    for field in NUTRITION_FIELDS:
        if field in payload:
            try:
                parsed[field] = round2(payload[field])
            except Exception:
                return None, "Bad request"
    return parsed, None


def get_next_user_id():
    counter = mongo.db.counters.find_one_and_update(
        {"_id": "profile_user_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(counter["seq"])


@app.route("/profiles", methods=["GET", "POST"])
def profiles():
    auth_data, auth_error = validate_token()
    if auth_error:
        return auth_error

    if request.method == "GET":
        query = {}
        for key, value in request.args.items():
            if key == "user_id":
                try:
                    query["user_id"] = int(value)
                except ValueError:
                    return error_response("Bad request", 400)
            elif key in NUTRITION_FIELDS:
                try:
                    query[key] = round2(value)
                except Exception:
                    return error_response("Bad request", 400)
            else:
                return error_response("Bad request", 400)

        docs = mongo.db.profiles.find(query, {"_id": 0}).sort("user_id", 1)
        return jsonify([format_profile(doc) for doc in docs]), 200

    media_error = require_json()
    if media_error:
        return media_error

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("Bad request", 400)

    existing = mongo.db.profiles.find_one({"user_id": int(auth_data["user_id"])})
    if existing:
        return error_response("Bad request", 400)

    parsed, err = parse_profile_payload(payload)
    if err:
        return error_response(err, 400)

    user_id = int(auth_data["user_id"])
    profile = {"user_id": user_id}
    for field in NUTRITION_FIELDS:
        profile[field] = parsed.get(field, 0.00)

    mongo.db.profiles.insert_one(profile)
    return jsonify(format_profile(profile)), 201


@app.route("/profiles/<int:profile_id>", methods=["GET", "PUT", "DELETE"])
def profile_by_id(profile_id):
    auth_data, auth_error = validate_token()
    if auth_error:
        return auth_error

    if int(auth_data["user_id"]) != int(profile_id):
        return error_response("Unauthorized", 401)

    profile = mongo.db.profiles.find_one({"user_id": int(profile_id)})
    if not profile:
        return error_response("Not Found", 404)

    if request.method == "GET":
        return jsonify(format_profile(profile)), 200

    if request.method == "DELETE":
        mongo.db.profiles.delete_one({"user_id": int(profile_id)})
        return Response(status=204)

    media_error = require_json()
    if media_error:
        return media_error

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("Bad request", 400)

    parsed, err = parse_profile_payload(payload)
    if err:
        return error_response(err, 400)

    update_doc = {}
    for field in NUTRITION_FIELDS:
        if field in parsed:
            update_doc[field] = parsed[field]

    updated = mongo.db.profiles.find_one_and_update(
        {"user_id": int(profile_id)},
        {"$set": update_doc},
        return_document=ReturnDocument.AFTER,
    )
    return jsonify(format_profile(updated)), 200


@app.route("/profileDishes", methods=["GET"])
def profile_dishes():
    auth_data, auth_error = validate_token()
    if auth_error:
        return auth_error

    profile = mongo.db.profiles.find_one({"user_id": int(auth_data["user_id"])})
    if not profile:
        return error_response("Not Found", 404)

    params = {}
    for field in NUTRITION_FIELDS:
        params[field] = "{:.2f}".format(round2(profile.get(field, 0.0)))

    try:
        resp = requests.get(DISHES_URL, params=params, timeout=10)
    except requests.RequestException:
        return error_response("Internal Server Error", 500)

    if resp.status_code == 200:
        try:
            return jsonify(resp.json()), 200
        except Exception:
            return error_response("Internal Server Error", 500)
    if resp.status_code == 401:
        return error_response("Unauthorized", 401)
    if resp.status_code == 404:
        return error_response("Not Found", 404)
    if resp.status_code == 400:
        return error_response("Bad request", 400)
    return error_response("Internal Server Error", 500)


@app.errorhandler(404)
def handle_404(_e):
    return error_response("Not Found", 404)


@app.errorhandler(405)
def handle_405(_e):
    return error_response("Method Not Allowed", 405)


@app.errorhandler(500)
def handle_500(_e):
    return error_response("Internal Server Error", 500)


if __name__ == "__main__":
    mongo.db.profiles.create_index("user_id", unique=True)
    app.run(host="0.0.0.0", port=5003)