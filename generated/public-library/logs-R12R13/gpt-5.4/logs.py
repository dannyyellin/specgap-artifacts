# Required packages:
# pip install flask flask-pymongo requests

from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import uuid

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/logsdb"
mongo = PyMongo(app)

collection = mongo.db.logs


def generate_id():
    return str(uuid.uuid4())


def normalize_log(doc):
    if not doc:
        return None
    return {
        "cardholderId": doc.get("cardholderId", ""),
        "borrowId": doc.get("borrowId", ""),
        "ISBN": doc.get("ISBN", ""),
        "loanDate": doc.get("loanDate", ""),
        "id": doc.get("id", "")
    }


def is_json_request():
    return request.content_type is not None and "application/json" in request.content_type.lower()


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request"}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(415)
def unsupported_media_type(error):
    return jsonify({"error": "Unsupported media type"}), 415


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error"}), 500


@app.route("/logs", methods=["GET", "POST"])
def logs():
    try:
        if request.method == "GET":
            query_params = request.args.to_dict()
            mongo_query = {}

            for key, value in query_params.items():
                if key in ["cardholderId", "borrowId", "ISBN", "loanDate", "id"]:
                    mongo_query[key] = value

            docs = collection.find(mongo_query, {"_id": 0})
            result = [normalize_log(doc) for doc in docs]
            return jsonify(result), 200

        if request.method == "POST":
            if not is_json_request():
                return jsonify({"error": "Unsupported media type"}), 415

            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "Bad request"}), 400

            required_fields = ["cardholderId", "borrowId", "ISBN", "loanDate"]
            for field in required_fields:
                if field not in data or not isinstance(data[field], str):
                    return jsonify({"error": "Bad request"}), 400

            new_id = generate_id()
            log_doc = {
                "cardholderId": data["cardholderId"],
                "borrowId": data["borrowId"],
                "ISBN": data["ISBN"],
                "loanDate": data["loanDate"],
                "id": new_id
            }

            collection.insert_one(log_doc)
            return jsonify({"id": new_id}), 201

    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/logs/<string:log_id>", methods=["GET"])
def log_by_id(log_id):
    try:
        doc = collection.find_one({"id": log_id}, {"_id": 0})
        if not doc:
            return jsonify({"error": "Not found"}), 404
        return jsonify(normalize_log(doc)), 200
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)