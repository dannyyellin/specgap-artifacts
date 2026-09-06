# Required packages: flask, flask_pymongo, requests

from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
import requests

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/ratingsdb"
mongo = PyMongo(app)

AUTH_VALIDATE_URL = "http://authentication:5001/validate"
DISHES_BASE_URL = "http://dishes:5002/dishes"

NUMERIC_FIELDS = {"dish_id", "rating"}


def error_response(message, status_code):
    return jsonify({"message": message}), status_code


def round2(value):
    return float(f"{float(value):.2f}")


def get_json_body():
    if not request.is_json:
        return None, error_response("Unsupported media type", 415)
    data = request.get_json(silent=True)
    if data is None:
        return None, error_response("Bad request", 400)
    return data, None


def get_token_from_request():
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
        if auth_header.strip():
            return auth_header.strip()
    token = request.headers.get("token")
    if token and token.strip():
        return token.strip()
    return None


def validate_token():
    token = get_token_from_request()
    if not token:
        return None, error_response("Unauthorized", 401)
    try:
        resp = requests.post(AUTH_VALIDATE_URL, json={"token": token}, timeout=5)
    except requests.RequestException:
        return None, error_response("Internal Server Error", 500)

    if resp.status_code != 201:
        return None, error_response("Unauthorized", 401)

    try:
        data = resp.json()
    except ValueError:
        return None, error_response("Unauthorized", 401)

    if not data.get("valid") or "user_id" not in data:
        return None, error_response("Unauthorized", 401)

    return {
        "user_id": data.get("user_id"),
        "privileged": bool(data.get("privileged", False))
    }, None


def dish_exists(dish_id):
    try:
        resp = requests.get(f"{DISHES_BASE_URL}/{dish_id}", timeout=5)
    except requests.RequestException:
        return None, error_response("Internal Server Error", 500)

    if resp.status_code == 200:
        return True, None
    if resp.status_code == 404:
        return False, None
    if resp.status_code == 401:
        return False, error_response("Unauthorized", 401)
    return False, error_response("Internal Server Error", 500)


def get_next_sequence(name):
    doc = mongo.db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return int(doc["seq"])


def ensure_indexes():
    mongo.db.ratings.create_index([("id", 1)], unique=True)
    mongo.db.ratings.create_index([("dish_id", 1), ("user_id", 1)], unique=True)


def serialize_avg(dish_id, avg_rating):
    return {
        "dish_id": int(dish_id),
        "avg_rating": round2(avg_rating)
    }


def compute_avg_for_dish(dish_id):
    pipeline = [
        {"$match": {"dish_id": int(dish_id)}},
        {"$group": {"_id": "$dish_id", "avg_rating": {"$avg": "$rating"}}}
    ]
    result = list(mongo.db.ratings.aggregate(pipeline))
    if not result:
        return None
    return round2(result[0]["avg_rating"])


@app.errorhandler(405)
def method_not_allowed(_e):
    return error_response("Method Not Allowed", 405)


@app.errorhandler(404)
def not_found(_e):
    return error_response("Not Found", 404)


@app.errorhandler(500)
def internal_error(_e):
    return error_response("Internal Server Error", 500)


@app.route("/ratings", methods=["GET", "POST"])
def ratings_collection():
    auth_data, auth_error = validate_token()
    if auth_error:
        return auth_error

    if request.method == "GET":
        try:
            pipeline = [
                {"$group": {"_id": "$dish_id", "avg_rating": {"$avg": "$rating"}}},
                {"$sort": {"_id": 1}}
            ]
            results = list(mongo.db.ratings.aggregate(pipeline))
            response = [serialize_avg(item["_id"], item["avg_rating"]) for item in results]
            return jsonify(response), 200
        except PyMongoError:
            return error_response("Internal Server Error", 500)

    data, err = get_json_body()
    if err:
        return err

    if "dish_id" not in data or "rating" not in data:
        return error_response("Bad request", 400)

    try:
        dish_id = int(data["dish_id"])
        rating = round2(float(data["rating"]))
    except (TypeError, ValueError):
        return error_response("Bad request", 400)

    exists, exists_err = dish_exists(dish_id)
    if exists_err:
        return exists_err
    if not exists:
        return error_response("Not Found", 404)

    try:
        rating_id = get_next_sequence("rating_id")
        doc = {
            "id": rating_id,
            "dish_id": dish_id,
            "user_id": int(auth_data["user_id"]),
            "rating": rating
        }
        mongo.db.ratings.insert_one(doc)
        avg = compute_avg_for_dish(dish_id)
        return jsonify(serialize_avg(dish_id, avg)), 201
    except PyMongoError:
        return error_response("Bad request", 400)


@app.route("/ratings/<int:dish_id>", methods=["GET", "PUT", "DELETE"])
def rating_item(dish_id):
    auth_data, auth_error = validate_token()
    if auth_error:
        return auth_error

    if request.method == "GET":
        try:
            avg = compute_avg_for_dish(dish_id)
            if avg is None:
                return error_response("Not Found", 404)
            return jsonify(serialize_avg(dish_id, avg)), 200
        except PyMongoError:
            return error_response("Internal Server Error", 500)

    user_id = int(auth_data["user_id"])

    if request.method == "PUT":
        data, err = get_json_body()
        if err:
            return err

        if "dish_id" not in data or "rating" not in data:
            return error_response("Bad request", 400)

        try:
            body_dish_id = int(data["dish_id"])
            rating = round2(float(data["rating"]))
        except (TypeError, ValueError):
            return error_response("Bad request", 400)

        if body_dish_id != dish_id:
            return error_response("Bad request", 400)

        exists, exists_err = dish_exists(dish_id)
        if exists_err:
            return exists_err
        if not exists:
            return error_response("Not Found", 404)

        try:
            updated = mongo.db.ratings.find_one_and_update(
                {"dish_id": dish_id, "user_id": user_id},
                {"$set": {"rating": rating}},
                return_document=ReturnDocument.AFTER
            )
            if updated is None:
                return error_response("Not Found", 404)
            avg = compute_avg_for_dish(dish_id)
            return jsonify(serialize_avg(dish_id, avg)), 200
        except PyMongoError:
            return error_response("Internal Server Error", 500)

    try:
        deleted = mongo.db.ratings.delete_one({"dish_id": dish_id, "user_id": user_id})
        if deleted.deleted_count == 0:
            return error_response("Not Found", 404)
        return Response(status=204)
    except PyMongoError:
        return error_response("Internal Server Error", 500)


if __name__ == "__main__":
    ensure_indexes()
    app.run(host="0.0.0.0", port=5004)