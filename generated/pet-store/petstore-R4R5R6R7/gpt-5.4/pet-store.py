# Required packages:
# flask
# flask_pymongo
# requests
# bcrypt

import os
import re
import uuid
import imghdr
import random
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_pymongo import PyMongo
from pymongo.errors import DuplicateKeyError
import requests

SERVICE_NAME = "pet-store"
STORE_NUM = os.environ.get("STORE_NUM", "1")
MONGO_URI = f"mongodb://mongo:27017/{SERVICE_NAME}db"
REGISTRY_VERIFY_URL = "http://registry:8080/verify"
NINJA_API_URL = "https://api.api-ninjas.com/v1/animals"
NINJA_API_KEY = os.environ.get("NINJA_API_Key", "")
PICTURE_DIR = os.path.join(os.getcwd(), "pictures")

app = Flask(__name__)
app.config["MONGO_URI"] = MONGO_URI
mongo = PyMongo(app)

os.makedirs(PICTURE_DIR, exist_ok=True)

pet_types_collection = mongo.db[f"pet_types_{STORE_NUM}"]
counters_collection = mongo.db[f"counters_{STORE_NUM}"]

try:
    pet_types_collection.create_index("id", unique=True)
    pet_types_collection.create_index("type", unique=True)
except Exception:
    pass


def json_required():
    return request.content_type is not None and request.content_type.split(";")[0].strip().lower() == "application/json"


def parse_basic_auth():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return None, None
    return auth.username, auth.password


def verify_owner():
    username, password = parse_basic_auth()
    if not username or not password:
        return None, ("Unauthorized", 401)
    try:
        resp = requests.post(
            REGISTRY_VERIFY_URL,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
    except requests.RequestException:
        return None, ("Unauthorized", 401)

    if resp.status_code != 200:
        return None, ("Unauthorized", 401)

    try:
        data = resp.json()
    except Exception:
        return None, ("Unauthorized", 401)

    if not data.get("valid", False):
        return None, ("Unauthorized", 401)
    if not data.get("privileged", False):
        return None, ("Forbidden", 403)
    return data, None


def get_next_id():
    result = counters_collection.find_one_and_update(
        {"_id": "pet_type_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    if result and "seq" in result:
        return result["seq"]
    doc = counters_collection.find_one({"_id": "pet_type_id"})
    return doc["seq"] if doc else 1


def valid_birthdate(date_str):
    return bool(re.fullmatch(r"\d{2}-\d{2}-\d{4}", date_str))


def serialize_pet_type(doc):
    return {
        "id": doc["id"],
        "type": doc["type"],
        "family": doc.get("family", ""),
        "genus": doc.get("genus", ""),
        "attributes": doc.get("attributes", []),
        "lifespan": doc.get("lifespan", 0),
    }


def serialize_pet(pet):
    return {
        "name": pet["name"],
        "birthdate": pet.get("birthdate", "NA"),
        "picture": pet.get("picture", "NA"),
    }


def fetch_pet_type_from_ninja(pet_type_name):
    headers = {"X-Api-Key": NINJA_API_KEY} if NINJA_API_KEY else {}
    try:
        resp = requests.get(
            NINJA_API_URL,
            params={"name": pet_type_name},
            headers=headers,
            timeout=10,
        )
    except requests.RequestException:
        return None, 503

    if resp.status_code != 200:
        return None, 503

    try:
        arr = resp.json()
    except Exception:
        return None, 503

    if not isinstance(arr, list):
        return None, 503

    chosen = None
    for item in arr:
        if isinstance(item, dict) and str(item.get("name", "")).lower() == pet_type_name.lower():
            chosen = item
            break

    if not chosen:
        return None, 400

    characteristics = chosen.get("characteristics", {}) if isinstance(chosen.get("characteristics", {}), dict) else {}
    taxonomy = chosen.get("taxonomy", {}) if isinstance(chosen.get("taxonomy", {}), dict) else {}

    family = taxonomy.get("family", "")
    genus = taxonomy.get("genus", "")
    lifespan_raw = characteristics.get("lifespan", "")
    attributes = []

    for key in ["temperament", "slogan", "group", "color", "skin_type", "top_speed", "diet", "main_prey"]:
        val = characteristics.get(key)
        if isinstance(val, str) and val.strip():
            parts = [p.strip() for p in val.split(",") if p.strip()]
            attributes.extend(parts if parts else [val.strip()])

    seen = set()
    deduped = []
    for a in attributes:
        if a not in seen:
            seen.add(a)
            deduped.append(a)

    lifespan = 0
    if isinstance(lifespan_raw, str):
        nums = re.findall(r"\d+", lifespan_raw)
        if nums:
            lifespan = int(nums[0])
    elif isinstance(lifespan_raw, int):
        lifespan = lifespan_raw

    return {
        "family": family,
        "genus": genus,
        "attributes": deduped,
        "lifespan": lifespan,
    }, 200


def save_picture_from_url(url):
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    content_type = resp.headers.get("Content-Type", "").lower()
    content = resp.content

    img_type = imghdr.what(None, h=content)
    ext = None
    if "jpeg" in content_type or "jpg" in content_type or img_type == "jpeg":
        ext = ".jpg"
    elif "png" in content_type or img_type == "png":
        ext = ".png"

    if ext is None:
        return None

    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(PICTURE_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    return filename


@app.errorhandler(405)
def method_not_allowed(_e):
    return "", 405


@app.route("/pet-types", methods=["POST"])
def create_pet_type():
    owner, err = verify_owner()
    if err:
        return err

    if not json_required():
        return "", 415

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data.keys()) != {"type"}:
        return "", 400

    pet_type_name = data.get("type")
    if not isinstance(pet_type_name, str) or not pet_type_name.strip():
        return "", 400
    pet_type_name = pet_type_name.strip()

    if pet_types_collection.find_one({"type": pet_type_name}) is not None:
        return "", 409

    ninja_data, status = fetch_pet_type_from_ninja(pet_type_name)
    if status == 400:
        return "", 400
    if status == 503:
        return "", 503

    new_doc = {
        "id": get_next_id(),
        "type": pet_type_name,
        "family": ninja_data.get("family", ""),
        "genus": ninja_data.get("genus", ""),
        "attributes": ninja_data.get("attributes", []),
        "lifespan": ninja_data.get("lifespan", 0),
        "pets": [],
    }

    try:
        pet_types_collection.insert_one(new_doc)
    except DuplicateKeyError:
        return "", 409
    except Exception:
        return "", 500

    return jsonify(serialize_pet_type(new_doc)), 201


@app.route("/pet-types", methods=["GET"])
def list_pet_types():
    query = request.args
    docs = list(pet_types_collection.find({}, {"_id": 0, "pets": 0}))
    if not query:
        return jsonify([serialize_pet_type(d) for d in docs]), 200

    if len(query) != 1:
        return jsonify([]), 200

    field, value = next(iter(query.items()))
    results = []

    if field in {"id", "type", "family", "genus", "lifespan"}:
        for d in docs:
            if field in {"id", "lifespan"}:
                try:
                    if d.get(field) == int(value):
                        results.append(serialize_pet_type(d))
                except Exception:
                    return jsonify([]), 200
            else:
                if str(d.get(field, "")) == value:
                    results.append(serialize_pet_type(d))
    elif field == "hasAttribute":
        for d in docs:
            attrs = d.get("attributes", [])
            if isinstance(attrs, list) and value in attrs:
                results.append(serialize_pet_type(d))
    else:
        return jsonify([]), 200

    return jsonify(results), 200


@app.route("/pet-types/<int:pet_id>", methods=["GET"])
def get_pet_type(pet_id):
    doc = pet_types_collection.find_one({"id": pet_id}, {"_id": 0, "pets": 0})
    if not doc:
        return "", 404
    return jsonify(serialize_pet_type(doc)), 200


@app.route("/pet-types/<int:pet_id>", methods=["DELETE"])
def delete_pet_type(pet_id):
    owner, err = verify_owner()
    if err:
        return err

    result = pet_types_collection.delete_one({"id": pet_id})
    if result.deleted_count == 0:
        return "", 404
    return "", 204


@app.route("/pet-types/<int:pet_id>/pets", methods=["POST"])
def create_pet(pet_id):
    owner, err = verify_owner()
    if err:
        return err

    if not json_required():
        return "", 415

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "name" not in data:
        return "", 400

    name = data.get("name")
    birthdate = data.get("birthdate", "NA")
    picture_url = data.get("picture-url")

    if not isinstance(name, str) or not name:
        return "", 400

    if "birthdate" in data:
        if not isinstance(birthdate, str) or not valid_birthdate(birthdate):
            return "", 400
    else:
        birthdate = "NA"

    picture = "NA"
    if "picture-url" in data:
        if not isinstance(picture_url, str) or not picture_url:
            return "", 400
        picture = save_picture_from_url(picture_url)
        if picture is None:
            return "", 400

    doc = pet_types_collection.find_one({"id": pet_id})
    if not doc:
        return "", 404

    pets = doc.get("pets", [])
    for p in pets:
        if p.get("name") == name:
            return "", 400

    pet_obj = {"name": name, "birthdate": birthdate, "picture": picture}
    try:
        pet_types_collection.update_one({"id": pet_id}, {"$push": {"pets": pet_obj}})
    except Exception:
        return "", 500

    return jsonify(serialize_pet(pet_obj)), 201


@app.route("/pet-types/<int:pet_id>/pets", methods=["GET"])
def list_pets(pet_id):
    doc = pet_types_collection.find_one({"id": pet_id}, {"_id": 0, "pets": 1})
    if not doc:
        return "", 404
    pets = [serialize_pet(p) for p in doc.get("pets", [])]
    return jsonify(pets), 200


@app.route("/pet-types/<int:pet_id>/pets/<string:name>", methods=["GET"])
def get_pet(pet_id, name):
    doc = pet_types_collection.find_one({"id": pet_id}, {"_id": 0, "pets": 1})
    if not doc:
        return "", 404
    for pet in doc.get("pets", []):
        if pet.get("name") == name:
            return jsonify(serialize_pet(pet)), 200
    return "", 404


@app.route("/pet-types/<int:pet_id>/pets/<string:name>", methods=["DELETE"])
def delete_pet(pet_id, name):
    owner, err = verify_owner()
    if err:
        return err

    doc = pet_types_collection.find_one({"id": pet_id})
    if not doc:
        return "", 404

    exists = any(p.get("name") == name for p in doc.get("pets", []))
    if not exists:
        return "", 404

    try:
        pet_types_collection.update_one({"id": pet_id}, {"$pull": {"pets": {"name": name}}})
    except Exception:
        return "", 500

    return "", 204


@app.route("/pet-types/<int:pet_id>/pets/<string:name>", methods=["PUT"])
def update_pet(pet_id, name):
    owner, err = verify_owner()
    if err:
        return err

    if not json_required():
        return "", 415

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "name" not in data:
        return "", 400

    doc = pet_types_collection.find_one({"id": pet_id})
    if not doc:
        return "", 404

    pets = doc.get("pets", [])
    target_index = None
    for i, pet in enumerate(pets):
        if pet.get("name") == name:
            target_index = i
            break

    if target_index is None:
        return "", 404

    current = pets[target_index].copy()
    new_name = data.get("name")
    if not isinstance(new_name, str) or not new_name:
        return "", 400

    if "birthdate" in data:
        bd = data.get("birthdate")
        if not isinstance(bd, str) or not valid_birthdate(bd):
            return "", 400
        current["birthdate"] = bd

    if "picture" in data:
        pic = data.get("picture")
        if not isinstance(pic, str) or not pic:
            return "", 400
        current["picture"] = pic

    if "picture-url" in data:
        picfile = save_picture_from_url(data.get("picture-url"))
        if picfile is None:
            return "", 400
        current["picture"] = picfile

    current["name"] = new_name
    if "birthdate" not in current:
        current["birthdate"] = "NA"
    if "picture" not in current:
        current["picture"] = "NA"

    for i, pet in enumerate(pets):
        if i != target_index and pet.get("name") == new_name:
            return "", 400

    pets[target_index] = current
    try:
        pet_types_collection.update_one({"id": pet_id}, {"$set": {"pets": pets}})
    except Exception:
        return "", 500

    return jsonify(serialize_pet(current)), 200


@app.route("/pictures/<path:picture_name>", methods=["GET"])
def get_picture(picture_name):
    if "/" in picture_name or "\\" in picture_name or not picture_name:
        return "", 400
    path = os.path.join(PICTURE_DIR, picture_name)
    if not os.path.isfile(path):
        return "", 404
    return send_from_directory(PICTURE_DIR, picture_name), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)