# Required packages:
# pip install flask flask-pymongo requests

from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import uuid
import requests
from datetime import datetime

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/borrowsdb"
mongo = PyMongo(app)

BORROWS_COLLECTION = "borrows"
CARDHOLDERS_URL = "http://cardholders:5001/cardholders"
BOOKS_URL = "http://books:5002/books"
LOGS_URL = "http://logs:5004/logs"


def borrows_collection():
    return mongo.db[BORROWS_COLLECTION]


def parse_date(date_str):
    return datetime.strptime(date_str, "%d-%m-%Y")


def is_valid_date(date_str):
    try:
        parse_date(date_str)
        return True
    except Exception:
        return False


def serialize_borrow(doc):
    if not doc:
        return None
    return {
        "cardholderId": doc.get("cardholderId", ""),
        "ISBN": doc.get("ISBN", ""),
        "loanDate": doc.get("loanDate", ""),
        "returnDate": doc.get("returnDate", ""),
        "id": doc.get("id", "")
    }


def validate_json_request():
    if not request.is_json:
        return jsonify({"error": "Unsupported media type"}), 415
    return None


def validate_borrow_payload(data, require_all_post=True):
    required_post_fields = ["cardholderId", "ISBN", "loanDate"]
    allowed_fields = ["cardholderId", "ISBN", "loanDate", "returnDate", "id"]

    if not isinstance(data, dict):
        return "Bad request"

    for key in data.keys():
        if key not in allowed_fields:
            return "Bad request"

    if require_all_post:
        for field in required_post_fields:
            if field not in data or not isinstance(data[field], str):
                return "Bad request"

    if "cardholderId" in data and not isinstance(data["cardholderId"], str):
        return "Bad request"
    if "ISBN" in data and not isinstance(data["ISBN"], str):
        return "Bad request"
    if "loanDate" in data:
        if not isinstance(data["loanDate"], str) or not is_valid_date(data["loanDate"]):
            return "Bad request"
    if "returnDate" in data:
        if not isinstance(data["returnDate"], str) or (data["returnDate"] != "" and not is_valid_date(data["returnDate"])):
            return "Bad request"
    if "id" in data and not isinstance(data["id"], str):
        return "Bad request"

    if "loanDate" in data and "returnDate" in data and data["returnDate"] != "":
        try:
            if parse_date(data["returnDate"]) < parse_date(data["loanDate"]):
                return "Bad request"
        except Exception:
            return "Bad request"

    return None


def remote_resource_exists(base_url, resource_id):
    try:
        resp = requests.get(f"{base_url}/{resource_id}", timeout=5)
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        return None
    except Exception:
        return None


def book_exists_by_isbn(isbn):
    try:
        resp = requests.get(BOOKS_URL, params={"ISBN": isbn}, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return isinstance(data, list) and len(data) > 0
    except Exception:
        return None


def create_log_for_borrow(borrow_doc):
    payload = {
        "cardholderId": borrow_doc["cardholderId"],
        "borrowId": borrow_doc["id"],
        "ISBN": borrow_doc["ISBN"],
        "loanDate": borrow_doc["loanDate"]
    }
    try:
        resp = requests.post(LOGS_URL, json=payload, timeout=5)
        return resp.status_code == 201
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


@app.route("/borrows", methods=["GET", "POST"])
def borrows():
    if request.method == "GET":
        try:
            args = request.args.to_dict(flat=True)

            if "startDate" in args or "endDate" in args:
                if "startDate" not in args or "endDate" not in args:
                    return jsonify({"error": "Bad request"}), 400
                start_date = args.get("startDate")
                end_date = args.get("endDate")
                if not is_valid_date(start_date) or not is_valid_date(end_date):
                    return jsonify({"error": "Bad request"}), 400
                if parse_date(start_date) > parse_date(end_date):
                    return jsonify({"error": "Bad request"}), 400

                docs = []
                for doc in borrows_collection().find():
                    loan_date = doc.get("loanDate", "")
                    if is_valid_date(loan_date):
                        ld = parse_date(loan_date)
                        if parse_date(start_date) <= ld <= parse_date(end_date):
                            docs.append(serialize_borrow(doc))
                return jsonify(docs), 200

            query = {}
            for key, value in args.items():
                if key not in ["cardholderId", "ISBN", "loanDate", "returnDate", "id"]:
                    return jsonify({"error": "Bad request"}), 400
                query[key] = value

            docs = [serialize_borrow(doc) for doc in borrows_collection().find(query)]
            return jsonify(docs), 200
        except Exception:
            return jsonify({"error": "Internal Server Error"}), 500

    if request.method == "POST":
        media_error = validate_json_request()
        if media_error:
            return media_error

        try:
            data = request.get_json()
        except Exception:
            return jsonify({"error": "Bad request"}), 400

        validation_error = validate_borrow_payload(data, require_all_post=True)
        if validation_error:
            return jsonify({"error": validation_error}), 400

        try:
            cardholder_ok = remote_resource_exists(CARDHOLDERS_URL, data["cardholderId"])
            if cardholder_ok is False:
                return jsonify({"error": "Bad request"}), 400
            if cardholder_ok is None:
                return jsonify({"error": "Internal Server Error"}), 500

            book_ok = book_exists_by_isbn(data["ISBN"])
            if book_ok is False:
                return jsonify({"error": "Bad request"}), 400
            if book_ok is None:
                return jsonify({"error": "Internal Server Error"}), 500

            borrow_id = str(uuid.uuid4())
            borrow_doc = {
                "cardholderId": data["cardholderId"],
                "ISBN": data["ISBN"],
                "loanDate": data["loanDate"],
                "returnDate": data.get("returnDate", ""),
                "id": borrow_id
            }

            borrows_collection().insert_one(borrow_doc)
            create_log_for_borrow(borrow_doc)

            return jsonify({"id": borrow_id}), 201
        except Exception:
            return jsonify({"error": "Internal Server Error"}), 500


@app.route("/borrows/<string:borrow_id>", methods=["GET", "PUT", "DELETE"])
def borrow_by_id(borrow_id):
    if request.method == "GET":
        try:
            doc = borrows_collection().find_one({"id": borrow_id})
            if not doc:
                return jsonify({"error": "Not Found"}), 404
            return jsonify(serialize_borrow(doc)), 200
        except Exception:
            return jsonify({"error": "Internal Server Error"}), 500

    if request.method == "PUT":
        media_error = validate_json_request()
        if media_error:
            return media_error

        try:
            existing = borrows_collection().find_one({"id": borrow_id})
            if not existing:
                return jsonify({"error": "Not Found"}), 404

            data = request.get_json()
        except Exception:
            return jsonify({"error": "Bad request"}), 400

        validation_error = validate_borrow_payload(data, require_all_post=False)
        if validation_error:
            return jsonify({"error": validation_error}), 400

        try:
            updated = {
                "cardholderId": existing.get("cardholderId", ""),
                "ISBN": existing.get("ISBN", ""),
                "loanDate": existing.get("loanDate", ""),
                "returnDate": existing.get("returnDate", ""),
                "id": borrow_id
            }

            for field in ["cardholderId", "ISBN", "loanDate", "returnDate"]:
                if field in data:
                    updated[field] = data[field]

            if updated["returnDate"] != "" and parse_date(updated["returnDate"]) < parse_date(updated["loanDate"]):
                return jsonify({"error": "Bad request"}), 400

            if "cardholderId" in data:
                cardholder_ok = remote_resource_exists(CARDHOLDERS_URL, updated["cardholderId"])
                if cardholder_ok is False:
                    return jsonify({"error": "Bad request"}), 400
                if cardholder_ok is None:
                    return jsonify({"error": "Internal Server Error"}), 500

            if "ISBN" in data:
                book_ok = book_exists_by_isbn(updated["ISBN"])
                if book_ok is False:
                    return jsonify({"error": "Bad request"}), 400
                if book_ok is None:
                    return jsonify({"error": "Internal Server Error"}), 500

            borrows_collection().update_one({"id": borrow_id}, {"$set": updated})
            return jsonify({"id": borrow_id}), 200
        except Exception:
            return jsonify({"error": "Internal Server Error"}), 500

    if request.method == "DELETE":
        try:
            result = borrows_collection().delete_one({"id": borrow_id})
            if result.deleted_count == 0:
                return jsonify({"error": "Not Found"}), 404
            return Response(status=204)
        except Exception:
            return jsonify({"error": "Internal Server Error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)