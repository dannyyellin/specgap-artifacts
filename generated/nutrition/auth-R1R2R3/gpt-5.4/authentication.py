# Required packages: flask, flask_pymongo, pymongo, pyjwt, requests

import os
import datetime
from functools import wraps

from flask import Flask, request, jsonify, make_response
from flask_pymongo import PyMongo
import jwt
from pymongo import ReturnDocument

SERVICE_NAME = "authentication"
MONGO_URI = f"mongodb://mongo:27017/{SERVICE_NAME}db"

app = Flask(__name__)
app.config["MONGO_URI"] = MONGO_URI
mongo = PyMongo(app)

app.config["SECRET_KEY"] = os.environ.get("JWT_SECRET", "restaurant-nutrition-auth-secret")
TOKEN_EXPIRATION_HOURS = int(os.environ.get("TOKEN_EXPIRATION_HOURS", "24"))

OWNER_NAME = os.environ.get("OWNER_NAME", "owner")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "owner")

NUMERIC_ID_FIELDS = ["id"]


def error_response(message, status_code):
    return make_response(message, status_code)


def is_json_request():
    return request.is_json


def get_json_body():
    if not is_json_request():
        return None, error_response("Unsupported media type", 415)
    data = request.get_json(silent=True)
    if data is None:
        return None, error_response("Bad request", 400)
    if not isinstance(data, dict):
        return None, error_response("Bad request", 400)
    return data, None


def round_float(value):
    return round(float(value), 2)


def get_next_sequence(sequence_name):
    counter = mongo.db.counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return int(counter["seq"])


def user_to_response(user_doc):
    return {
        "name": user_doc["name"],
        "password": user_doc["password"],
        "id": int(user_doc["id"])
    }


def generate_token(user_doc):
    payload = {
        "user_id": int(user_doc["id"]),
        "name": user_doc["name"],
        "privileged": bool(user_doc["name"] == OWNER_NAME),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRATION_HOURS),
        "iat": datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_token(token):
    return jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])


def ensure_indexes():
    mongo.db.users.create_index("name", unique=True)
    mongo.db.users.create_index("id", unique=True)


def ensure_owner_user():
    existing = mongo.db.users.find_one({"name": OWNER_NAME})
    if existing is None:
        owner_id = get_next_sequence("user_id")
        mongo.db.users.insert_one({
            "name": OWNER_NAME,
            "password": OWNER_PASSWORD,
            "id": owner_id
        })


@app.errorhandler(404)
def not_found(_e):
    return error_response("Not Found", 404)


@app.errorhandler(405)
def method_not_allowed(_e):
    return error_response("Method Not Allowed", 405)


@app.errorhandler(500)
def internal_error(_e):
    return error_response("Internal Server Error", 500)


@app.route("/register", methods=["POST"])
def register():
    data, err = get_json_body()
    if err:
        return err

    name = data.get("name")
    password = data.get("password")

    if name is None or password is None:
        return error_response("Bad request", 400)
    if not isinstance(name, str) or not isinstance(password, str):
        return error_response("Bad request", 400)
    if name.strip() == "" or password.strip() == "":
        return error_response("Bad request", 400)

    existing = mongo.db.users.find_one({"name": name})
    if existing is not None:
        return error_response("Bad request", 400)

    try:
        user_id = get_next_sequence("user_id")
        mongo.db.users.insert_one({
            "name": name,
            "password": password,
            "id": user_id
        })
        return error_response("successful", 201)
    except Exception:
        return error_response("Internal Server Error", 500)


@app.route("/login", methods=["POST"])
def login():
    data, err = get_json_body()
    if err:
        return err

    name = data.get("name")
    password = data.get("password")

    if name is None or password is None:
        return error_response("Bad request", 400)
    if not isinstance(name, str) or not isinstance(password, str):
        return error_response("Bad request", 400)

    user = mongo.db.users.find_one({"name": name, "password": password})
    if user is None:
        return error_response("Unauthorized", 401)

    try:
        token = generate_token(user)
        return make_response(jsonify({"token": token}), 201)
    except Exception:
        return error_response("Internal Server Error", 500)


@app.route("/validate", methods=["POST"])
def validate():
    data, err = get_json_body()
    if err:
        return err

    token = data.get("token")
    if token is None or not isinstance(token, str) or token.strip() == "":
        return error_response("Unauthorized", 401)

    try:
        payload = decode_token(token)
        user_id = int(payload.get("user_id"))
        user = mongo.db.users.find_one({"id": user_id})
        if user is None:
            return error_response("Unauthorized", 401)

        response = {
            "valid": True,
            "privileged": bool(payload.get("privileged", False)),
            "user_id": user_id
        }
        return make_response(jsonify(response), 201)
    except jwt.ExpiredSignatureError:
        return error_response("Unauthorized", 401)
    except jwt.InvalidTokenError:
        return error_response("Unauthorized", 401)
    except Exception:
        return error_response("Internal Server Error", 500)


if __name__ == "__main__":
    with app.app_context():
        ensure_indexes()
        ensure_owner_user()
    app.run(host="0.0.0.0", port=5001)