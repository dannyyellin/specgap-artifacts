# Required packages:
# flask
# flask_pymongo
# requests
# bcrypt

import os
import re
import traceback
from flask import Flask, request, jsonify, make_response
from flask_pymongo import PyMongo
from pymongo.errors import DuplicateKeyError
import bcrypt

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/registrydb"
mongo = PyMongo(app)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,50}$$")
OWNER_USERNAME = "OwnerOfStore_1_9"
OWNER_PASSWORD = "X566Yef22Nm"
BCRYPT_ROUNDS = 12


def json_required():
    content_type = request.headers.get("Content-Type", "")
    return content_type.split(";")[0].strip().lower() == "application/json"


def parse_json():
    if not json_required():
        return None, make_response("", 415)
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return None, make_response("", 400)
    return data, None


def validate_username(username):
    return isinstance(username, str) and USERNAME_PATTERN.fullmatch(username) is not None


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def users_collection():
    return mongo.db.users


@app.before_first_request
def init_db():
    try:
        users_collection().create_index("username", unique=True)
        owner = users_collection().find_one({"username": OWNER_USERNAME})
        if owner is None:
            users_collection().insert_one({
                "username": OWNER_USERNAME,
                "password": hash_password(OWNER_PASSWORD),
                "privileged": True
            })
        else:
            updates = {}
            if not owner.get("privileged", False):
                updates["privileged"] = True
            if not check_password(OWNER_PASSWORD, owner.get("password", "")):
                updates["password"] = hash_password(OWNER_PASSWORD)
            if updates:
                users_collection().update_one({"username": OWNER_USERNAME}, {"$set": updates})
    except Exception:
        pass


@app.route("/users", methods=["POST"])
def create_user():
    try:
        data, error = parse_json()
        if error:
            return error

        username = data.get("username")
        password = data.get("password")

        if username is None or password is None:
            return make_response("", 400)

        if not validate_username(username):
            return make_response("", 400)

        privileged = username == OWNER_USERNAME and password == OWNER_PASSWORD

        doc = {
            "username": username,
            "password": hash_password(password),
            "privileged": privileged
        }

        users_collection().insert_one(doc)
        return jsonify({"username": username}), 201
    except DuplicateKeyError:
        return make_response("", 409)
    except Exception:
        return make_response("", 500)


@app.route("/verify", methods=["POST"])
def verify_user():
    try:
        if not json_required():
            return make_response("", 415)

        data = request.get_json(silent=True)
        if data is None or not isinstance(data, dict):
            return make_response("", 401)

        username = data.get("username")
        password = data.get("password")

        if username is None or password is None:
            return make_response("", 401)

        user = users_collection().find_one({"username": username})
        if user is None:
            return make_response("", 401)

        if not check_password(password, user.get("password", "")):
            return make_response("", 401)

        return jsonify({
            "username": username,
            "valid": True,
            "privileged": bool(user.get("privileged", False))
        }), 200
    except Exception:
        return make_response("", 500)


@app.route("/users/<username>/password", methods=["PUT"])
def change_password(username):
    try:
        data, error = parse_json()
        if error:
            return error

        old_password = data.get("oldPassword")
        new_password = data.get("newPassword")

        if old_password is None or new_password is None:
            return make_response("", 400)

        if old_password == new_password:
            return jsonify({
                "message": "New password must be different from old password",
                "username": username
            }), 400

        user = users_collection().find_one({"username": username})
        if user is None:
            return make_response("", 404)

        if not check_password(old_password, user.get("password", "")):
            return make_response("", 401)

        privileged = username == OWNER_USERNAME and new_password == OWNER_PASSWORD

        users_collection().update_one(
            {"username": username},
            {"$set": {"password": hash_password(new_password), "privileged": privileged}}
        )

        return jsonify({
            "message": "Password updated successfully",
            "username": username
        }), 200
    except Exception:
        return make_response("", 500)


@app.route("/users/<username>", methods=["DELETE"])
def delete_user(username):
    try:
        data, error = parse_json()
        if error:
            return error

        password = data.get("password")
        if password is None:
            return make_response("", 401)

        user = users_collection().find_one({"username": username})
        if user is None:
            return make_response("", 404)

        if not check_password(password, user.get("password", "")):
            return make_response("", 401)

        users_collection().delete_one({"username": username})
        return jsonify({
            "message": "User deleted successfully",
            "username": username
        }), 200
    except Exception:
        return make_response("", 500)


@app.errorhandler(405)
def method_not_allowed(_e):
    return make_response("", 405)


@app.errorhandler(404)
def not_found(_e):
    return make_response("", 404)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)