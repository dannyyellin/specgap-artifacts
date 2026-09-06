# Required packages:
# pip install flask flask-pymongo requests

from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import requests

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/cardholdersdb"
mongo = PyMongo(app)

CARDHOLDERS_COLLECTION = mongo.db.cardholders
BORROWS_SERVICE_URL = "http://borrows:5003/borrows"


def serialize_cardholder(doc):
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "email": doc.get("email", "")
    }


def is_valid_objectid(value):
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def get_cardholder_or_404(cardholder_id):
    if not is_valid_objectid(cardholder_id):
        return None
    return CARDHOLDERS_COLLECTION.find_one({"_id": ObjectId(cardholder_id)})


def parse_date_ddmmyyyy(date_str):
    try:
        day, month, year = date_str.split("-")
        return int(year), int(month), int(day)
    except Exception:
        return None


def is_overdue(return_date_str):
    from datetime import datetime
    parsed = parse_date_ddmmyyyy(return_date_str)
    if not parsed:
        return False
    year, month, day = parsed
    try:
        due_date = datetime(year, month, day)
        return due_date.date() < datetime.utcnow().date()
    except Exception:
        return False


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "Not Found"}), 404


@app.errorhandler(405)
def method_not_allowed(_e):
    return jsonify({"error": "Method Not Allowed"}), 405


@app.errorhandler(500)
def internal_error(_e):
    return jsonify({"error": "Internal Server Error"}), 500


@app.route("/cardholders", methods=["GET"])
def get_cardholders():
    try:
        query_params = request.args.to_dict(flat=True)
        mongo_query = {}

        allowed_fields = {"name", "email"}
        for key, value in query_params.items():
            if key in allowed_fields:
                mongo_query[key] = value

        docs = CARDHOLDERS_COLLECTION.find(mongo_query)
        result = [serialize_cardholder(doc) for doc in docs]
        return jsonify(result), 200
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/cardholders", methods=["POST"])
def create_cardholder():
    try:
        if not request.is_json:
            return jsonify({"error": "Bad request"}), 400

        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "Bad request"}), 400

        name = data.get("name")
        email = data.get("email")

        if not isinstance(name, str) or not isinstance(email, str):
            return jsonify({"error": "Bad request"}), 400

        result = CARDHOLDERS_COLLECTION.insert_one({
            "name": name,
            "email": email
        })

        return jsonify({"id": str(result.inserted_id)}), 201
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/cardholders/<cardholder_id>", methods=["GET"])
def get_cardholder(cardholder_id):
    try:
        doc = get_cardholder_or_404(cardholder_id)
        if not doc:
            return jsonify({"error": "Not Found"}), 404
        return jsonify(serialize_cardholder(doc)), 200
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/cardholders/<cardholder_id>", methods=["PUT"])
def update_cardholder(cardholder_id):
    try:
        if not request.is_json:
            return jsonify({"error": "Bad request"}), 400

        existing = get_cardholder_or_404(cardholder_id)
        if not existing:
            return jsonify({"error": "Not Found"}), 404

        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "Bad request"}), 400

        update_fields = {}
        if "name" in data:
            if not isinstance(data["name"], str):
                return jsonify({"error": "Bad request"}), 400
            update_fields["name"] = data["name"]

        if "email" in data:
            if not isinstance(data["email"], str):
                return jsonify({"error": "Bad request"}), 400
            update_fields["email"] = data["email"]

        if "id" in data and str(data["id"]) != cardholder_id:
            return jsonify({"error": "Bad request"}), 400

        if not update_fields and "id" not in data:
            return jsonify({"error": "Bad request"}), 400

        CARDHOLDERS_COLLECTION.update_one(
            {"_id": ObjectId(cardholder_id)},
            {"$set": update_fields}
        )

        return jsonify({"id": cardholder_id}), 200
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/cardholders/<cardholder_id>", methods=["DELETE"])
def delete_cardholder(cardholder_id):
    try:
        existing = get_cardholder_or_404(cardholder_id)
        if not existing:
            return jsonify({"error": "Not Found"}), 404

        CARDHOLDERS_COLLECTION.delete_one({"_id": ObjectId(cardholder_id)})
        return Response(status=204)
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/cardholders/fines/<cardholder_id>", methods=["GET"])
def get_cardholder_fines(cardholder_id):
    try:
        existing = get_cardholder_or_404(cardholder_id)
        if not existing:
            return jsonify({"error": "Not Found"}), 404

        try:
            borrows_response = requests.get(
                BORROWS_SERVICE_URL,
                params={"cardholderId": cardholder_id},
                timeout=5
            )
        except requests.RequestException:
            return jsonify({"error": "Internal Server Error"}), 500

        if borrows_response.status_code != 200:
            if 400 <= borrows_response.status_code < 500:
                return jsonify({"error": "Bad request"}), 400
            return jsonify({"error": "Internal Server Error"}), 500

        try:
            borrows = borrows_response.json()
        except Exception:
            return jsonify({"error": "Internal Server Error"}), 500

        if not isinstance(borrows, list):
            return jsonify({"error": "Internal Server Error"}), 500

        fine_amount = 0
        for borrow in borrows:
            if isinstance(borrow, dict):
                return_date = borrow.get("returnDate")
                if isinstance(return_date, str) and is_overdue(return_date):
                    fine_amount += 1

        return jsonify({"id": cardholder_id, "fineAmount": fine_amount}), 200
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)