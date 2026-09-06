# Required packages:
# pip install flask flask-pymongo requests

from flask import Flask, request, jsonify, Response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import uuid

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://mongo:27017/booksdb"
mongo = PyMongo(app)

BOOK_FIELDS = ["title", "authors", "ISBN", "publisher", "publishedDate", "genre", "id"]
POST_REQUIRED_FIELDS = ["title", "authors", "ISBN", "genre"]
ALL_MUTABLE_FIELDS = ["title", "authors", "ISBN", "publisher", "publishedDate", "genre"]


def serialize_book(doc):
    return {
        "title": doc.get("title", ""),
        "authors": doc.get("authors", ""),
        "ISBN": doc.get("ISBN", ""),
        "publisher": doc.get("publisher", ""),
        "publishedDate": doc.get("publishedDate", ""),
        "genre": doc.get("genre", ""),
        "id": doc.get("id", "")
    }


def is_json_request():
    content_type = request.content_type or ""
    return "application/json" in content_type.lower()


def validate_string_field(data, field, required=False):
    if required and field not in data:
        return False
    if field in data and not isinstance(data[field], str):
        return False
    return True


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "Not Found"}), 404


@app.errorhandler(405)
def method_not_allowed(_e):
    return jsonify({"error": "Method Not Allowed"}), 405


@app.errorhandler(415)
def unsupported_media_type(_e):
    return jsonify({"error": "Unsupported Media Type"}), 415


@app.errorhandler(500)
def internal_server_error(_e):
    return jsonify({"error": "Internal Server Error"}), 500


@app.route("/books", methods=["GET"])
def get_books():
    try:
        query_params = request.args.to_dict(flat=True)
        mongo_query = {}

        for key, value in query_params.items():
            if key in BOOK_FIELDS:
                mongo_query[key] = value

        books = [serialize_book(doc) for doc in mongo.db.books.find(mongo_query)]
        return jsonify(books), 200
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/books", methods=["POST"])
def create_book():
    try:
        if not is_json_request():
            return jsonify({"error": "Unsupported Media Type"}), 415

        data = request.get_json(silent=True)
        if data is None or not isinstance(data, dict):
            return jsonify({"error": "Bad Request"}), 400

        for field in POST_REQUIRED_FIELDS:
            if not validate_string_field(data, field, required=True):
                return jsonify({"error": "Bad Request"}), 400

        for field in ["publisher", "publishedDate"]:
            if field in data and not isinstance(data[field], str):
                return jsonify({"error": "Bad Request"}), 400

        book_id = str(uuid.uuid4())
        book = {
            "id": book_id,
            "title": data["title"],
            "authors": data["authors"],
            "ISBN": data["ISBN"],
            "publisher": data.get("publisher", ""),
            "publishedDate": data.get("publishedDate", ""),
            "genre": data["genre"]
        }

        mongo.db.books.insert_one(book)
        return jsonify({"id": book_id}), 201
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/books/<string:book_id>", methods=["GET"])
def get_book(book_id):
    try:
        book = mongo.db.books.find_one({"id": book_id})
        if not book:
            return jsonify({"error": "Not Found"}), 404
        return jsonify(serialize_book(book)), 200
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/books/<string:book_id>", methods=["PUT"])
def update_book(book_id):
    try:
        if not is_json_request():
            return jsonify({"error": "Unsupported Media Type"}), 415

        data = request.get_json(silent=True)
        if data is None or not isinstance(data, dict):
            return jsonify({"error": "Bad Request"}), 400

        existing = mongo.db.books.find_one({"id": book_id})
        if not existing:
            return jsonify({"error": "Not Found"}), 404

        update_doc = {}
        for field in ALL_MUTABLE_FIELDS:
            if field in data:
                if not isinstance(data[field], str):
                    return jsonify({"error": "Bad Request"}), 400
                update_doc[field] = data[field]

        if "id" in data and data["id"] != book_id:
            return jsonify({"error": "Bad Request"}), 400

        mongo.db.books.update_one({"id": book_id}, {"$set": update_doc})
        return jsonify({"id": book_id}), 200
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/books/<string:book_id>", methods=["DELETE"])
def delete_book(book_id):
    try:
        result = mongo.db.books.delete_one({"id": book_id})
        if result.deleted_count == 0:
            return jsonify({"error": "Not Found"}), 404
        return Response(status=204)
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500


if __name__ == "__main__":
    mongo.db.books.create_index("id", unique=True)
    app.run(host="0.0.0.0", port=5002)