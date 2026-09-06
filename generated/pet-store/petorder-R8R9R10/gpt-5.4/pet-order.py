# Required packages: flask, flask_pymongo, requests

import os
import uuid
import base64
from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from pymongo.errors import PyMongoError
import requests

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/pet-orderdb"
mongo = PyMongo(app)

REGISTRY_VERIFY_URL = "http://registry:8080/verify"
PET_STORE_URL_TEMPLATE = "http://pet-store{store_num}:8000"
DEFAULT_STORE_SCAN_RANGE = int(os.environ.get("STORE_SCAN_MAX", "10"))

purchases_collection = mongo.db.purchases
transactions_collection = mongo.db.transactions
counters_collection = mongo.db.counters


def require_json():
    ct = request.headers.get("Content-Type", "")
    return ct.split(";")[0].strip().lower() == "application/json"


def parse_basic_auth():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Basic "):
        return None, None
    token = auth[6:].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return None, None
    if ":" not in decoded:
        return None, None
    username, password = decoded.split(":", 1)
    return username, password


def verify_credentials():
    username, password = parse_basic_auth()
    if not username or not password:
        return None, None, Response(status=401)
    try:
        resp = requests.post(
            REGISTRY_VERIFY_URL,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
    except requests.RequestException:
        return None, None, Response(status=500)
    if resp.status_code != 200:
        return None, None, Response(status=401)
    try:
        data = resp.json()
    except Exception:
        return None, None, Response(status=500)
    if not data.get("valid", False):
        return None, None, Response(status=401)
    return username, bool(data.get("privileged", False)), None


def get_next_transaction_id():
    result = counters_collection.find_one_and_update(
        {"_id": "transaction_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    if result and "seq" in result:
        return str(result["seq"])
    doc = counters_collection.find_one({"_id": "transaction_id"})
    return str(doc.get("seq", 1))


def normalize_purchase_payload(data):
    if not isinstance(data, dict):
        return None, jsonify({"error": "Invalid payload"}), 400

    if "purchaser" not in data or "pet-type" not in data:
        return None, jsonify({"error": "Missing required fields"}), 400

    purchaser = data.get("purchaser")
    pet_type = data.get("pet-type")
    store = data.get("store", None)
    pet_name = data.get("pet-name", None)

    if not isinstance(purchaser, str) or not isinstance(pet_type, str) or purchaser == "" or pet_type == "":
        return None, jsonify({"error": "Missing required fields"}), 400

    if pet_name is not None and store is None:
        return None, jsonify({"error": "pet-name requires store"}), 400

    if store is not None:
        if isinstance(store, bool) or not isinstance(store, int):
            return None, jsonify({"error": "Invalid store"}), 400

    if pet_name is not None and (not isinstance(pet_name, str) or pet_name == ""):
        return None, jsonify({"error": "Invalid pet-name"}), 400

    normalized = {
        "purchaser": purchaser,
        "pet-type": pet_type,
        "store": store,
        "pet-name": pet_name,
    }
    return normalized, None, None


def fetch_pet_types(store_num, pet_type):
    try:
        resp = requests.get(
            f"{PET_STORE_URL_TEMPLATE.format(store_num=store_num)}/pet-types",
            params={"type": pet_type},
            timeout=5,
        )
    except requests.RequestException:
        return None, "unreachable"
    if resp.status_code != 200:
        return None, "badstatus"
    try:
        data = resp.json()
    except Exception:
        return None, "badjson"
    if not isinstance(data, list):
        return None, "badjson"
    return data, None


def fetch_pets(store_num, pet_type_id, pet_name=None):
    url = f"{PET_STORE_URL_TEMPLATE.format(store_num=store_num)}/pet-types/{pet_type_id}/pets"
    if pet_name is not None:
        url = f"{url}/{pet_name}"
    try:
        resp = requests.get(url, timeout=5)
    except requests.RequestException:
        return None, "unreachable", None
    if pet_name is not None:
        if resp.status_code == 404:
            return None, None, 404
        if resp.status_code != 200:
            return None, "badstatus", resp.status_code
        try:
            data = resp.json()
        except Exception:
            return None, "badjson", None
        return data, None, 200
    else:
        if resp.status_code == 404:
            return None, None, 404
        if resp.status_code != 200:
            return None, "badstatus", resp.status_code
        try:
            data = resp.json()
        except Exception:
            return None, "badjson", None
        return data, None, 200


def choose_pet(purchase):
    pet_type = purchase["pet-type"]
    requested_store = purchase["store"]
    requested_pet_name = purchase["pet-name"]

    stores_to_check = [requested_store] if requested_store is not None else list(range(1, DEFAULT_STORE_SCAN_RANGE + 1))

    for store_num in stores_to_check:
        pet_types, err = fetch_pet_types(store_num, pet_type)
        if err is not None:
            continue
        matched_type = None
        for pt in pet_types:
            if isinstance(pt, dict) and pt.get("type") == pet_type and "id" in pt:
                matched_type = pt
                break
        if matched_type is None:
            continue

        pet_type_id = matched_type["id"]

        if requested_pet_name is not None:
            pet_obj, pet_err, status = fetch_pets(store_num, pet_type_id, requested_pet_name)
            if pet_err is None and status == 200 and isinstance(pet_obj, dict):
                return {"store": store_num, "pet-name": pet_obj.get("name", requested_pet_name)}
            continue

        pets, pet_err, status = fetch_pets(store_num, pet_type_id)
        if pet_err is None and status == 200 and isinstance(pets, list) and len(pets) > 0:
            first_pet = pets[0]
            if isinstance(first_pet, dict) and "name" in first_pet:
                return {"store": store_num, "pet-name": first_pet["name"]}

    return None


@app.route("/purchases", methods=["POST"])
def create_purchase():
    if not require_json():
        return Response(status=415)

    auth_user, privileged, auth_error = verify_credentials()
    if auth_error is not None:
        return auth_error

    try:
        data = request.get_json(silent=True)
    except Exception:
        data = None

    purchase, error_resp, status = normalize_purchase_payload(data)
    if error_resp is not None:
        return error_resp, status

    if purchase["purchaser"] != auth_user:
        return Response(status=403)

    try:
        chosen = choose_pet(purchase)
        if chosen is None:
            return jsonify({"error": "No pet of this type is available"}), 400

        purchase_id = str(uuid.uuid4())
        purchase_doc = {
            "purchaser": purchase["purchaser"],
            "pet-type": purchase["pet-type"],
            "store": chosen["store"],
            "pet-name": chosen["pet-name"],
            "purchase-id": purchase_id,
        }
        transaction_doc = {
            "id": get_next_transaction_id(),
            "purchaser": purchase["purchaser"],
            "pet-type": purchase["pet-type"],
            "store": chosen["store"],
            "purchase-id": purchase_id,
        }

        purchases_collection.insert_one(dict(purchase_doc))
        transactions_collection.insert_one(dict(transaction_doc))

        return jsonify(purchase_doc), 201
    except PyMongoError:
        return Response(status=500)
    except Exception:
        return Response(status=500)


@app.route("/purchases", methods=["GET", "PUT", "DELETE", "PATCH"])
def purchases_not_allowed():
    return Response(status=405)


@app.route("/transactions", methods=["GET"])
def get_transactions():
    auth_user, privileged, auth_error = verify_credentials()
    if auth_error is not None:
        return auth_error
    if not privileged:
        return Response(status=401)

    try:
        query = {}
        allowed_fields = {"id", "purchaser", "pet-type", "store", "purchase-id"}
        for key in request.args.keys():
            if key not in allowed_fields:
                return jsonify([])
            value = request.args.get(key)
            if key == "store":
                try:
                    value = int(value)
                except Exception:
                    return jsonify([])
            query[key] = value

        docs = list(transactions_collection.find(query, {"_id": 0}))
        return jsonify(docs), 200
    except PyMongoError:
        return Response(status=500)
    except Exception:
        return Response(status=500)


@app.route("/transactions", methods=["POST", "PUT", "DELETE", "PATCH"])
def transactions_not_allowed():
    return Response(status=405)


@app.route("/transactions/<tx_id>", methods=["GET"])
def get_transaction(tx_id):
    auth_user, privileged, auth_error = verify_credentials()
    if auth_error is not None:
        return auth_error
    if not privileged:
        return Response(status=401)

    try:
        if tx_id is None or str(tx_id).strip() == "":
            return Response(status=400)
        doc = transactions_collection.find_one({"id": tx_id}, {"_id": 0})
        if doc is None:
            return Response(status=404)
        return jsonify(doc), 200
    except PyMongoError:
        return Response(status=500)
    except Exception:
        return Response(status=500)


@app.route("/transactions/<tx_id>", methods=["POST", "PUT", "DELETE", "PATCH"])
def transaction_not_allowed(tx_id):
    return Response(status=405)


@app.errorhandler(405)
def method_not_allowed(e):
    return Response(status=405)


@app.errorhandler(404)
def not_found(e):
    return Response(status=404)


if __name__ == "__main__":
    try:
        counters_collection.update_one(
            {"_id": "transaction_id"},
            {"$setOnInsert": {"seq": 0}},
            upsert=True,
        )
    except Exception:
        pass
    app.run(host="0.0.0.0", port=80)