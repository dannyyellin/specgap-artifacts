# Required packages: flask, flask-pymongo, requests, flask-cors

import os
from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from flask_cors import CORS
import requests
from pymongo import ReturnDocument

SERVICE_NAME = "dishes"
AUTH_VALIDATE_URL = "http://authentication:5001/validate"
NINJA_API_URL = "https://api.api-ninjas.com/v1/nutrition"

app = Flask(__name__)
app.config["MONGO_URI"] = f"mongodb://mongo:27017/{SERVICE_NAME}db"
mongo = PyMongo(app)
CORS(app)


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

NINJA_FIELD_MAP = {
    "fat_total_g": "total_fat",
    "fat_saturated_g": "saturated_fat",
    "protein_g": "protein",
    "sodium_mg": "sodium",
    "cholesterol_mg": "cholesterol",
    "carbohydrates_total_g": "total_carbohydrates",
    "fiber_g": "fiber",
    "sugar_g": "sugar",
}


def round2(value):
    return round(float(value), 2)


def error_response(message, status_code):
    return jsonify({"message": message}), status_code


def validate_token():
    token = request.headers.get("Authorization")
    if not token:
        return None, error_response("Unauthorized", 401)

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

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
    except Exception:
        return None, error_response("Unauthorized", 401)

    if not data.get("valid"):
        return None, error_response("Unauthorized", 401)

    return data, None


def serialize_dish(doc):
    return {
        "name": doc["name"],
        "id": doc["id"],
        "ingredients": doc["ingredients"],
        "total_fat": round2(doc["total_fat"]),
        "saturated_fat": round2(doc["saturated_fat"]),
        "protein": round2(doc["protein"]),
        "sodium": round2(doc["sodium"]),
        "cholesterol": round2(doc["cholesterol"]),
        "total_carbohydrates": round2(doc["total_carbohydrates"]),
        "fiber": round2(doc["fiber"]),
        "sugar": round2(doc["sugar"]),
    }


def parse_numeric_query_value(field, value):
    try:
        return round2(float(value))
    except Exception:
        raise ValueError(f"Invalid value for field '{field}'")


def build_query_from_args(args):
    query = {}
    allowed_fields = {"id", "name", "ingredients"} | set(NUTRITION_FIELDS)

    for field, value in args.items():
        if field not in allowed_fields:
            continue

        if field == "id":
            try:
                query["id"] = int(value)
            except Exception:
                raise ValueError("Invalid value for field 'id'")
        elif field == "name":
            query["name"] = value
        elif field == "ingredients":
            query["ingredients"] = value
        else:
            query[field] = parse_numeric_query_value(field, value)

    return query


def get_next_id():
    counter = mongo.db.counters.find_one_and_update(
        {"_id": "dish_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(counter["seq"])


def fetch_ingredient_nutrition(ingredient):
    api_key = os.environ.get("NINJA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing NINJA_API_KEY")

    headers = {"X-Api-Key": api_key}
    params = {"query": ingredient}

    try:
        resp = requests.get(NINJA_API_URL, headers=headers, params=params, timeout=10)
    except requests.RequestException:
        raise ConnectionError("Nutrition API request failed")

    if resp.status_code != 200:
        raise ConnectionError("Nutrition API request failed")

    try:
        data = resp.json()
    except Exception:
        raise ConnectionError("Nutrition API invalid response")

    totals = {field: 0.0 for field in NUTRITION_FIELDS}

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for ninja_field, local_field in NINJA_FIELD_MAP.items():
                    totals[local_field] += float(item.get(ninja_field, 0.0) or 0.0)

    return {k: round2(v) for k, v in totals.items()}


def compute_dish_nutrition(ingredients):
    totals = {field: 0.0 for field in NUTRITION_FIELDS}

    for ingredient in ingredients:
        ingredient_totals = fetch_ingredient_nutrition(ingredient)
        for field in NUTRITION_FIELDS:
            totals[field] += ingredient_totals[field]

    return {k: round2(v) for k, v in totals.items()}


def validate_dish_payload(data):
    if not request.is_json:
        return None, error_response("Unsupported media type", 415)

    if not isinstance(data, dict):
        return None, error_response("Bad request", 400)

    name = data.get("name")
    ingredients = data.get("ingredients")

    if name is None or ingredients is None:
        return None, error_response("Bad request", 400)

    if not isinstance(name, str) or not name.strip():
        return None, error_response("Bad request", 400)

    if not isinstance(ingredients, list):
        return None, error_response("Bad request", 400)

    cleaned_ingredients = []
    for item in ingredients:
        if not isinstance(item, str) or not item.strip():
            return None, error_response("Bad request", 400)
        cleaned_ingredients.append(item.strip())

    return {"name": name.strip(), "ingredients": cleaned_ingredients}, None


@app.before_request
def require_authentication():
    if request.method == "OPTIONS":
        return None
    auth_data, error = validate_token()
    if error:
        return error
    request.auth_data = auth_data
    return None


@app.route("/dishes", methods=["GET", "POST"])
def dishes_collection():
    if request.method == "GET":
        try:
            query = build_query_from_args(request.args)
        except ValueError as e:
            return error_response(str(e), 400)

        docs = mongo.db.dishes.find(query, {"_id": 0}).sort("id", 1)
        return jsonify([serialize_dish(doc) for doc in docs]), 200

    data = request.get_json(silent=True)
    payload, error = validate_dish_payload(data)
    if error:
        return error

    try:
        nutrition = compute_dish_nutrition(payload["ingredients"])
    except RuntimeError:
        return error_response("Internal Server Error", 500)
    except ConnectionError:
        return error_response("Internal Server Error", 500)
    except Exception:
        return error_response("Internal Server Error", 500)

    dish = {
        "id": get_next_id(),
        "name": payload["name"],
        "ingredients": payload["ingredients"],
    }
    dish.update(nutrition)

    mongo.db.dishes.insert_one(dish)
    return jsonify(serialize_dish(dish)), 201


@app.route("/dishes/<dish_id>", methods=["GET", "PUT", "DELETE"])
def dish_resource(dish_id):
    try:
        dish_id_int = int(dish_id)
    except Exception:
        return error_response("Not Found", 404)

    existing = mongo.db.dishes.find_one({"id": dish_id_int}, {"_id": 0})
    if not existing:
        return error_response("Not Found", 404)

    if request.method == "GET":
        return jsonify(serialize_dish(existing)), 200

    if request.method == "DELETE":
        mongo.db.dishes.delete_one({"id": dish_id_int})
        return Response(status=204)

    data = request.get_json(silent=True)
    payload, error = validate_dish_payload(data)
    if error:
        return error

    try:
        nutrition = compute_dish_nutrition(payload["ingredients"])
    except RuntimeError:
        return error_response("Internal Server Error", 500)
    except ConnectionError:
        return error_response("Internal Server Error", 500)
    except Exception:
        return error_response("Internal Server Error", 500)

    updated = {
        "id": dish_id_int,
        "name": payload["name"],
        "ingredients": payload["ingredients"],
    }
    updated.update(nutrition)

    mongo.db.dishes.update_one({"id": dish_id_int}, {"$set": updated})
    return jsonify(serialize_dish(updated)), 200


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
    mongo.db.dishes.create_index("id", unique=True)
    mongo.db.counters.create_index("_id", unique=True)
    app.run(host="0.0.0.0", port=5002)