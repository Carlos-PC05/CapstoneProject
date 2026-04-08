import hashlib
import os
import re
import unicodedata
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

#SocketIO imports
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.middleware.proxy_fix import ProxyFix

from werkzeug.utils import secure_filename

from models import Conversation, Favorite, Item, ItemImage, Message, User, db
from utils import confirm_token, generate_confirmation_token, mail, send_email

# Search scoring powered by RapidFuzz, with a difflib fallback for safety.
try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback for environments without rapidfuzz
    from difflib import SequenceMatcher

    class _FallbackFuzz:
        @staticmethod
        def ratio(first, second):
            return SequenceMatcher(None, first, second).ratio() * 100

        @staticmethod
        def partial_ratio(first, second):
            if not first or not second:
                return 0

            shorter, longer = (first, second) if len(first) <= len(second) else (second, first)
            if shorter in longer:
                return 100

            window = len(shorter)
            best = 0
            for index in range(max(len(longer) - window + 1, 1)):
                candidate = longer[index:index + window]
                best = max(best, SequenceMatcher(None, shorter, candidate).ratio() * 100)
            return best

        @staticmethod
        def token_set_ratio(first, second):
            first_tokens = " ".join(sorted(set(first.split())))
            second_tokens = " ".join(sorted(set(second.split())))
            return SequenceMatcher(None, first_tokens, second_tokens).ratio() * 100

    fuzz = _FallbackFuzz()


load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")
app.config["SECURITY_PASSWORD_SALT"] = os.getenv("SECURITY_PASSWORD_SALT", "default_salt")
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.googlemail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///database.db")

db.init_app(app)
mail.init_app(app)
#initialize socketIO app
socketio = SocketIO(app, manage_session=False)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_search_text(value):
    normalized_value = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(
        character for character in normalized_value
        if not unicodedata.combining(character)
    )
    lowered_value = without_accents.lower().strip()
    return re.sub(r"\s+", " ", lowered_value)


def tokenize_search_text(value):
    return [token for token in re.split(r"[^a-z0-9]+", value) if token]


CONDITION_LABELS = {
    "new": "New",
    "like-new": "Like New",
    "good": "Good",
    "fair": "Fair",
    "poor": "Poor",
}

VALID_CONDITIONS = set(CONDITION_LABELS.keys())


def normalize_condition(value):
    return (value or "").strip().lower()


def score_search_match(item, normalized_query, query_tokens):
    normalized_name = normalize_search_text(item.name)
    normalized_description = normalize_search_text(item.description)
    normalized_content = f"{normalized_name} {normalized_description}".strip()
    content_tokens = tokenize_search_text(normalized_content)

    score = 0
    matched = False

    if normalized_query in normalized_name:
        score += 140
        matched = True
    elif normalized_query in normalized_description:
        score += 95
        matched = True
    elif normalized_query in normalized_content:
        score += 85
        matched = True

    for token in query_tokens:
        if token in normalized_name:
            score += 30
            matched = True
        elif token in normalized_description:
            score += 18
            matched = True

    fuzzy_candidates = [
        fuzz.partial_ratio(normalized_query, normalized_name),
        fuzz.partial_ratio(normalized_query, normalized_description),
        fuzz.partial_ratio(normalized_query, normalized_content),
        fuzz.token_set_ratio(normalized_query, normalized_content),
        fuzz.ratio(normalized_query, normalized_name),
    ]

    for token in content_tokens:
        fuzzy_candidates.append(fuzz.ratio(normalized_query, token))
        fuzzy_candidates.append(fuzz.partial_ratio(normalized_query, token))

        for query_token in query_tokens:
            fuzzy_candidates.append(fuzz.ratio(query_token, token))

    best_fuzzy_score = max(fuzzy_candidates) if fuzzy_candidates else 0

    if best_fuzzy_score >= 92:
        score += 95
        matched = True
    elif best_fuzzy_score >= 84:
        score += 75
        matched = True
    elif best_fuzzy_score >= 74:
        score += 55
        matched = True
    elif best_fuzzy_score >= 68:
        score += 35
        matched = True

    if normalized_query == normalized_name:
        score += 50

    return matched, score, best_fuzzy_score


def search_items_for_dashboard(base_query, search_query):
    normalized_query = normalize_search_text(search_query)
    if not normalized_query:
        return []

    query_tokens = tokenize_search_text(normalized_query)
    items = base_query.order_by(Item.id.asc()).all()
    ranked_items = []
    minimum_fuzzy_score = 88 if len(normalized_query) <= 3 else 74 if len(normalized_query) <= 5 else 78

    for item in items:
        matched, score, best_fuzzy_score = score_search_match(item, normalized_query, query_tokens)
        if not matched:
            continue

        if score < 60 and best_fuzzy_score < minimum_fuzzy_score:
            continue

        ranked_items.append((score, item.created_at, item.id, item))

    ranked_items.sort(key=lambda ranked_item: (-ranked_item[0], ranked_item[1], ranked_item[2]))
    return [ranked_item[3] for ranked_item in ranked_items]


def get_current_user_from_session():
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.session.get(User, user_id)
        if user:
            session["user_id"] = user.id
            session["username"] = user.username
            return user

    legacy_username = session.get("username")
    if legacy_username and user_id is None:
        user = User.query.filter_by(username=legacy_username).first()
        if user:
            session["user_id"] = user.id
            session["username"] = user.username
            return user

    session.pop("user_id", None)
    session.pop("username", None)
    return None


@app.context_processor
def inject_search_query():
    return {
        "current_search_query": request.args.get("q", "").strip(),
        "condition_labels": CONDITION_LABELS,
    }

""" SocketIO Config """

def format_chat_timestamp(value):
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


def format_offer_message_body(price):
    return f"OFFER::{price:.2f}"


def format_offer_preview(body):
    if not isinstance(body, str) or not body.startswith("OFFER::"):
        return body

    try:
        price = float(body.split("::", 1)[1])
        return f"I have an offer for you: ${price:.2f}"
    except (IndexError, ValueError):
        return "Offer"


def serialize_message(message, current_user_id):
    body = message.body
    preview = body
    if body.startswith("OFFER::"):
        try:
            price = float(body.split("::")[1])
            preview = f"💰 I have an offer for you: ${price:.2f}"
        except (IndexError, ValueError):
            preview = "💰 Offer"

    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "body": message.body,
        "created_at": format_chat_timestamp(message.created_at),
        "created_at_iso": message.created_at.isoformat() if message.created_at else "",
        "is_own": message.sender_id == current_user_id,
    }


def serialize_conversation(conversation, current_user_id):
    other_user = conversation.other_user_for(current_user_id)
    last_message = conversation.last_message
    preview = format_offer_preview((last_message.body or "") if last_message else "No messages yet.")
    if len(preview) > 70:
        preview = f"{preview[:67]}..."

    return {
        "id": conversation.id,
        "item_id": conversation.item_id,
        "item_name": conversation.item.name,
        "item_status": conversation.item.estado,
        "item_image_url": url_for("static", filename=conversation.item.image_url),
        "other_user_id": other_user.id if other_user else None,
        "other_user_name": other_user.username if other_user else "Unknown user",
        "other_user_photo_url": (
            url_for("static", filename=other_user.photo_url)
            if other_user and other_user.photo_url
            else None
        ),
        "last_message_preview": preview,
        "last_message_at": format_chat_timestamp(conversation.last_message_at),
        "last_message_at_iso": conversation.last_message_at.isoformat() if conversation.last_message_at else "",
        "is_unread": conversation.is_unread_for(current_user_id),
        "messages_url": url_for("messages", conversation_id=conversation.id),
    }


def get_conversation_for_user(conversation_id, user_id):
    if not conversation_id:
        return None

    return Conversation.query.filter(
        Conversation.id == conversation_id,
        db.or_(Conversation.buyer_id == user_id, Conversation.seller_id == user_id),
    ).first()


def create_or_get_conversation(item, buyer_id):
    conversation = Conversation.query.filter_by(
        item_id=item.id,
        buyer_id=buyer_id,
        seller_id=item.user_id,
    ).first()
    if conversation:
        return conversation

    conversation = Conversation(
        item_id=item.id,
        buyer_id=buyer_id,
        seller_id=item.user_id,
    )
    db.session.add(conversation)
    db.session.commit()
    return conversation

""" Database Seeding """


def seed_data():
    if User.query.first():
        return

    user1 = User(
        username="Carlos",
        email="carlosparracamacho@gmail.com",
        is_active=True,
        items=[],
        country="EspaÃ±a",
        city="HuÃ©rcal-Overa",
        description="Hola, soy Carlos.",
        photo_url="img/users/fotoNYSkyline.jpeg",
    )
    user1.set_password("Saltador2005_")

    user2 = User(
        username="Juan",
        email="juanperez@gmail.com",
        is_active=True,
        items=[],
        country="España",
        city="Madrid",
        description="Hola, soy Juan.",
        photo_url="",
    )
    user2.set_password("Juan1234_")

    user3 = User(
        username="Ana",
        email="anagomez@gmail.com",
        is_active=True,
        items=[],
        country="España",
        city="Madrid",
        description="Hola, soy Ana.",
        photo_url="",
    )
    user3.set_password("Ana1234_")

    db.session.add_all([user1, user2, user3])
    db.session.commit()

    item1 = Item(name="Taza", description="Taza de ceramica", brand="", condition="good", price=10.0, category="furniture", images=[], user_id=user1.id)
    item2 = Item(name="Lampara", description="Lampara LED", brand="Philips", condition="good", price=20.0, category="furniture", images=[], user_id=user2.id)
    item3 = Item(name="Mesa", description="Mesa de madera", brand="Ikea", condition="fair", price=30.0, category="furniture", images=[], user_id=user3.id)
    item4 = Item(name="Silla", description="Silla de plÃ¡stico", brand="", condition="good", price=40.0, category="furniture", images=[], user_id=user1.id)
    item5 = Item(name="Tennis Racket", description="Used tennis racket in good condition", brand="Wilson", condition="good", price=15.0, category="sport", images=[], user_id=user2.id)
    item6 = Item(name="Padel Racket", description="Brand new padel racket, never used", brand="Bullpadel", condition="new", price=100.0, category="sport", images=[], user_id=user3.id)
    item7 = Item(name="Pillow Set", description="Set of 2 comfortable pillows", brand="", condition="like-new", price=25.0, category="bedding", images=[], user_id=user1.id)
    item8 = Item(name="Desk Lamp", description="Adjustable desk lamp with LED light", brand="Xiaomi", condition="good", price=35.0, category="electronics", images=[], user_id=user2.id)
    item9 = Item(name="Jacket", description="Warm winter jacket, size M", brand="Zara", condition="fair", price=50.0, category="clothes", images=[], user_id=user3.id)

    db.session.add_all([item1, item2, item3, item4, item5, item6, item7, item8, item9])
    db.session.commit()

    images = [
        ItemImage(image_url="img/items/taza.jpg", item=item1),
        ItemImage(image_url="img/items/lampara.jpg", item=item2),
        ItemImage(image_url="img/items/mesa.jpg", item=item3),
        ItemImage(image_url="img/items/silla.jpg", item=item4),
        ItemImage(image_url="img/items/taza2.jpg", item=item1),
        ItemImage(image_url="img/items/taza3.jpg", item=item1),
        ItemImage(image_url="img/items/taza4.jpg", item=item1),
        ItemImage(image_url="img/items/tennis.jpg", item=item5),
        ItemImage(image_url="img/items/padel.jpg", item=item6),
        ItemImage(image_url="img/items/pillows.jpg", item=item7),
        ItemImage(image_url="img/items/deskLamp.jpg", item=item8),
        ItemImage(image_url="img/items/jacket.jpg", item=item9),
    ]

    db.session.add_all(images)
    db.session.commit()


""" Auth """


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if not user:
            return render_template("auth/login.html", error="Email not registered.")

        if user and user.check_password(password):
            if not user.is_active:
                return render_template("auth/login.html", error="Please confirm your account first. Check your email.")

            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("dashboard"))

        return render_template("auth/login.html", error="Incorrect password.")

    if get_current_user_from_session():
        return redirect(url_for("dashboard"))
    return render_template("auth/login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/auth/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        password2 = request.form.get("password2")

        if len(password) < 8:
            return render_template("auth/SignUp.html", error="The password must be at least 8 characters long.")
        if password != password2:
            return render_template("auth/SignUp.html", error="Passwords don't match.")

        user = User.query.filter_by(email=email).first()
        if user:
            return render_template("auth/SignUp.html", error="Email already registered.")

        new_user = User(username=username, email=email, is_active=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        token = generate_confirmation_token(new_user.email)
        confirm_url = url_for("confirm_email", token=token, _external=True)
        html = render_template("auth/confirm_email_template.html", confirm_url=confirm_url)

        try:
            send_email(new_user.email, "Please confirm your email address", html)
        except Exception as error:
            print(f"Error sending email: {error}")
            print(f"LINK DE CONFIRMACION (DEV): {confirm_url}")

        return redirect(url_for("confirm"))

    return render_template("auth/SignUp.html")


@app.route("/auth/confirm/<token>")
def confirm_email(token):
    try:
        email = confirm_token(token)
    except Exception:
        return render_template("auth/login.html", error="The confirmation link is invalid or has expired.")

    user = User.query.filter_by(email=email).first_or_404()
    if user.is_active:
        return render_template("auth/login.html", error="Account already confirmed. Please log in.")

    user.is_active = True
    db.session.add(user)
    db.session.commit()
    return render_template("auth/activated.html")


@app.route("/auth/confirm_info")
def confirm():
    return render_template("auth/confirm.html")


@app.route("/auth/recover", methods=["GET", "POST"])
def recover():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if not user:
            return render_template("auth/recover.html", error="Email not registered.")

        token = generate_confirmation_token(user.email)
        recover_url = url_for("recover_password", token=token, _external=True)
        html = render_template("auth/recover_password_template.html", recover_url=recover_url)
        try:
            send_email(user.email, "Password recovery", html)
        except Exception as error:
            print(f"Error sending email: {error}")
            print(f"LINK DE RECOVERY (DEV): {recover_url}")

        return render_template("auth/confirm.html")

    return render_template("auth/recover.html")


@app.route("/auth/restore/<token>", methods=["GET", "POST"])
def recover_password(token):
    try:
        email = confirm_token(token)
    except Exception:
        return render_template("auth/login.html", error="The recovery link is invalid or has expired.")

    if request.method == "POST":
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        if len(password) < 8:
            return render_template("auth/restore.html", token=token, error="The password must be at least 8 characters long.")
        if not password or not password_confirm:
            return render_template("auth/restore.html", token=token, error="Please fill in all fields")
        if password != password_confirm:
            return render_template("auth/restore.html", token=token, error="Passwords do not match")

        user = User.query.filter_by(email=email).first_or_404()
        user.set_password(password)
        db.session.commit()
        return render_template("auth/login.html", success="Password updated successfully. Please login.")

    return render_template("auth/restore.html", token=token)


""" User Profile """


@app.route("/profile")
def profile():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    return render_template("user/profile.html", user=user)


@app.route("/user/edit", methods=["GET", "POST"])
def edit_profile():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        if "photo" in request.files:
            file = request.files["photo"]
            if file.filename == "":
                flash("No selected file", "error")
                return redirect(request.url)

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_content = file.read()
                file_hash = hashlib.sha256(file_content).hexdigest()
                file.seek(0)

                file_ext = os.path.splitext(filename)[1].lower()
                unique_filename = f"{file_hash}{file_ext}"
                relative_path = os.path.join("img", "users", unique_filename)
                full_path = os.path.join(app.root_path, "static", relative_path)

                if not os.path.exists(full_path):
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    file.save(full_path)

                user.photo_url = f"img/users/{unique_filename}"
                db.session.commit()
                flash("Profile photo updated successfully", "success")
            else:
                flash("Invalid file type", "error")

        if "username" in request.form:
            new_username = request.form.get("username")
            if new_username != user.username:
                if not new_username:
                    flash("Username cannot be empty.", "error")
                else:
                    user.username = new_username
                    db.session.commit()
                    session["username"] = new_username
                    flash("Username updated successfully.", "success")

        if "description" in request.form:
            new_description = request.form.get("description")
            if new_description != user.description:
                if not new_description:
                    flash("Description cannot be empty.", "error")
                else:
                    user.description = new_description
                    db.session.commit()
                    flash("Description updated successfully.", "success")

        return redirect(url_for("edit_profile"))

    return render_template("user/editProfile.html", user=user)


""" Upload Item """


@app.route("/user/upload", methods=["GET", "POST"])
def upload():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        brand = (request.form.get("brand") or "").strip()
        condition = normalize_condition(request.form.get("condition"))
        category = (request.form.get("category") or "").strip().lower()
        price = request.form.get("price")

        if not title or not description or not condition or not category or not price:
            flash("Please fill in all required fields", "error")
            return redirect(request.url)

        if condition not in VALID_CONDITIONS:
            flash("Invalid condition", "error")
            return redirect(request.url)

        try:
            price = float(price)
        except ValueError:
            flash("Invalid price", "error")
            return redirect(request.url)

        if "photos" not in request.files:
            flash("At least one photo is required", "error")
            return redirect(url_for("upload"))

        files = request.files.getlist("photos")
        if not files or files[0].filename == "":
            flash("At least one photo is required", "error")
            return redirect(request.url)

        if len(files) > 6:
            flash("Maximum 6 photos allowed. Please select fewer photos.", "error")
            return redirect(request.url)

        new_item = Item(
            name=title,
            description=description,
            brand=brand,
            condition=condition,
            price=price,
            category=category,
            user_id=user.id,
        )
        db.session.add(new_item)
        db.session.commit()

        for file in files:
            if file and file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_content = file.read()
                file_hash = hashlib.sha256(file_content).hexdigest()
                file.seek(0)

                file_ext = os.path.splitext(filename)[1].lower()
                unique_filename = f"{file_hash}{file_ext}"
                relative_path = os.path.join("img", "items", unique_filename)
                full_path = os.path.join(app.root_path, "static", relative_path)

                if not os.path.exists(full_path):
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    file.save(full_path)

                db.session.add(ItemImage(image_url=f"img/items/{unique_filename}", item_id=new_item.id))

        db.session.commit()
        flash("Item uploaded successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("user/upload.html", edit_mode=False, item=None)


""" Edit Item """


@app.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    item = Item.query.get_or_404(item_id)
    if item.user_id != user.id:
        flash("You cannot edit this item.", "error")
        return redirect(url_for("item", item_id=item.id))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        brand = (request.form.get("brand") or "").strip()
        condition = normalize_condition(request.form.get("condition"))
        category = (request.form.get("category") or "").strip().lower()
        price = request.form.get("price")

        if not title or not description or not condition or not category or not price:
            flash("Please fill in all required fields", "error")
            return redirect(request.url)

        if condition not in VALID_CONDITIONS:
            flash("Invalid condition", "error")
            return redirect(request.url)

        try:
            price = float(price)
        except ValueError:
            flash("Invalid price", "error")
            return redirect(request.url)

        item.name = title
        item.description = description
        item.brand = brand
        item.condition = condition
        item.category = category
        item.price = price

        files = []
        if "photos" in request.files:
            files = [file for file in request.files.getlist("photos") if file and file.filename != ""]

        if files:
            total_images = len(item.images) + len(files)
            if total_images > 6:
                flash("Maximum 6 photos allowed. Please select fewer photos.", "error")
                return redirect(request.url)

            for file in files:
                if file and file.filename != "" and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_content = file.read()
                    file_hash = hashlib.sha256(file_content).hexdigest()
                    file.seek(0)

                    file_ext = os.path.splitext(filename)[1].lower()
                    unique_filename = f"{file_hash}{file_ext}"
                    relative_path = os.path.join("img", "items", unique_filename)
                    full_path = os.path.join(app.root_path, "static", relative_path)

                    if not os.path.exists(full_path):
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        file.save(full_path)

                    db.session.add(ItemImage(image_url=f"img/items/{unique_filename}", item_id=item.id))

        db.session.commit()
        flash("Item updated successfully!", "success")
        return redirect(url_for("item", item_id=item.id))

    return render_template("user/upload.html", edit_mode=True, item=item)


""" Delete Item """


@app.route("/item/delete/<int:item_id>", methods=["GET"])
def delete(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    item = Item.query.get_or_404(item_id)
    if item.user_id != user.id:
        flash("You cannot delete this item.", "error")
        return redirect(url_for("item", item_id=item.id))

    item.estado = "deleted"
    db.session.commit()
    flash("Item deleted successfully!", "success")
    return redirect(url_for("profile"))


""" Favorite Items """


@app.route("/user/favItems")
def favItems():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    favorite_items = [item for item in user.favorite_items if (item.estado or "").lower() != "deleted"]
    return render_template("user/favItems.html", favorite_items=favorite_items)


@app.route("/item/<int:item_id>/favorite", methods=["POST"])
def toggle_favorite(item_id):
    user = get_current_user_from_session()
    if not user:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    item = Item.query.get_or_404(item_id)
    if (item.estado or "").lower() == "deleted":
        return jsonify({"ok": False, "error": "This item is no longer available"}), 400
    if item.user_id == user.id:
        return jsonify({"ok": False, "error": "You cannot favorite your own item"}), 400

    existing_favorite = Favorite.query.filter_by(user_id=user.id, item_id=item.id).first()
    if existing_favorite:
        db.session.delete(existing_favorite)
        db.session.commit()
        return jsonify({"ok": True, "is_favorite": False, "item_id": item.id})

    db.session.add(Favorite(user_id=user.id, item_id=item.id))
    db.session.commit()
    return jsonify({"ok": True, "is_favorite": True, "item_id": item.id})


""" Messages """


@app.route("/item/<int:item_id>/messages/start")
def start_item_conversation(item_id):
    user = get_current_user_from_session()
    #if there is no user in session, go back to login
    if not user:
        return redirect(url_for("login"))

    #get the item
    item = Item.query.get_or_404(item_id)
    item_status = (item.estado or "").lower()

    #Prevent starting a conversation about own item
    if item.user_id == user.id:
        flash("You cannot start a conversation about your own item.", "error")
        return redirect(url_for("item", item_id=item.id))

    #Prevent starting a conversation about deleted items
    if item_status == "deleted":
        flash("This item is no longer available for new conversations.", "error")
        return redirect(url_for("dashboard"))

    #Create or get existing conversation and redirect to messages
    conversation = create_or_get_conversation(item, user.id)
    return redirect(url_for("messages", conversation_id=conversation.id))


@app.route("/user/messages")
def messages():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    conversation_id = request.args.get("conversation_id", type=int)
    conversations = Conversation.query.filter(
        db.or_(Conversation.buyer_id == user.id, Conversation.seller_id == user.id)
    ).order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc()).all()

    selected_conversation = get_conversation_for_user(conversation_id, user.id)
    if selected_conversation is None and conversations:
        selected_conversation = conversations[0]

    selected_messages = []
    if selected_conversation:
        selected_conversation.mark_read_for(user.id)
        db.session.commit()
        selected_messages = [serialize_message(message, user.id) for message in selected_conversation.messages]

    return render_template(
        "user/messages.html",
        conversations=[serialize_conversation(conversation, user.id) for conversation in conversations],
        selected_conversation=serialize_conversation(selected_conversation, user.id) if selected_conversation else None,
        selected_messages=selected_messages,
        current_user=user,
    )


""" Comprar Item """


@app.route("/item/comprar/<int:item_id>", methods=["POST"])
def comprar(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    item = Item.query.get_or_404(item_id)
    if item.user_id == user.id:
        flash("You cannot purchase your own item.", "error")
        return redirect(url_for("item", item_id=item.id))

    if (item.estado or "").lower() != "active":
        flash("This item is already purchased.", "error")
        return redirect(url_for("item", item_id=item.id))

    item.estado = "comprado"
    db.session.commit()
    flash("Item purchased successfully!", "success")
    send_email(
        to=item.owner.email,
        subject="You sold an item!",
        template="Congratulations, you have sold an item!! Thank you for using DeSales Exchange Hub.",
    )
    return redirect(url_for("item", item_id=item.id))


""" Dashboard """


@app.route("/dashboard")
def dashboard():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    search_query = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip().lower()

    base_query = Item.query.filter(
        db.func.lower(Item.estado) == "active",
        Item.user_id != user.id,
    )

    if search_query:
        items = search_items_for_dashboard(base_query, search_query)
    elif category and category != "all":
        items = base_query.filter(db.func.lower(Item.category) == category).order_by(db.func.random()).all()
    else:
        items = base_query.order_by(db.func.random()).all()

    users = User.query.all()
    favorite_item_ids = {favorite_item.id for favorite_item in user.favorite_items}
    return render_template("index.html", items=items, users=users, favorite_item_ids=favorite_item_ids)


""" Item """


@app.route("/item/<int:item_id>")
def item(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    current_item = Item.query.get_or_404(item_id)
    item_status = (current_item.estado or "").lower()
    similar_items = []

    if item_status != "deleted":
        similar_items = Item.query.filter(
            db.func.lower(Item.category) == current_item.category.lower(),
            Item.id != current_item.id,
            db.func.lower(Item.estado) == "active",
        ).limit(10).all()

    favorite_item_ids = {favorite_item.id for favorite_item in user.favorite_items}
    return render_template(
        "item.html",
        item=current_item,
        similar_items=similar_items,
        favorite_item_ids=favorite_item_ids,
        item_unavailable=item_status == "deleted" and current_item.user_id != user.id,
    )

""" Hacer oferta """

@app.route("/item/<int:item_id>/offer", methods = ['POST'])
def make_offer(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))
    
    item = Item.query.get_or_404(item_id)

    if item.user_id == user.id:
        flash("You can not make an offer on your own item", "error")
        return redirect(url_for("item", item_id=item.id))

    if (item.estado or "").lower() != "active":
        flash("This item is no longer available", "error")
        return redirect(url_for("item", item_id=item.id))

    try:
        offer_price = float(request.form.get("offer_price", 0))
    except (TypeError, ValueError):
        flash("Invalid offer price", "error")
        return redirect(url_for("item", item_id=item.id))

    if offer_price <= 0:
        flash("The offer must be greater than 0", "error")
        return redirect(url_for("item", item_id=item.id))

    if offer_price >= item.price:
        flash("The offer must be lower than the item price.", "error")
        return redirect(url_for("item", item_id=item.id))

    conversation = create_or_get_conversation(item, user.id)
    created_at = datetime.now()

    offer_body = format_offer_message_body(offer_price)

    message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        body=offer_body,
        created_at=created_at,
    )
    db.session.add(message)
    conversation.last_message_at = created_at
    conversation.mark_read_for(user.id)
    db.session.commit()

    socketio.emit(
        "message_created",
        serialize_message(message, user.id),
        to=f"conversation:{conversation.id}",
    )
    socketio.emit(
        "conversation_updated",
        serialize_conversation(conversation, conversation.buyer_id),
        to=f"user:{conversation.buyer_id}"
    )
    socketio.emit(
        "conversation_updated",
        serialize_conversation(conversation, conversation.seller_id),
        to=f"user:{conversation.seller_id}",
    )
    
    return redirect(url_for("messages", conversation_id=conversation.id))

""" Socket.IO """

#Connect to the room
@socketio.on("connect")
def handle_connect():
    user = get_current_user_from_session()
    if not user:
        return False

    join_room(f"user:{user.id}")

#Join conversation
@socketio.on("join_conversation")
def handle_join_conversation(data):
    user = get_current_user_from_session()
    if not user:
        return False

    conversation_id = (data or {}).get("conversation_id")
    conversation = get_conversation_for_user(conversation_id, user.id)
    if not conversation:
        emit("chat_error", {"message": "Conversation not found."})
        return

    join_room(f"conversation:{conversation.id}")
    conversation.mark_read_for(user.id)
    db.session.commit()
    emit("conversation_read", {"conversation_id": conversation.id})

#Leave conversation
@socketio.on("leave_conversation")
def handle_leave_conversation(data):
    user = get_current_user_from_session()
    if not user:
        return

    conversation_id = (data or {}).get("conversation_id")
    conversation = get_conversation_for_user(conversation_id, user.id)
    if not conversation:
        return

    leave_room(f"conversation:{conversation.id}")

#Send message
@socketio.on("send_message")
def handle_send_message(data):
    user = get_current_user_from_session()
    if not user:
        emit("chat_error", {"message": "Unauthorized."})
        return

    payload = data or {}
    conversation = get_conversation_for_user(payload.get("conversation_id"), user.id)
    if not conversation:
        emit("chat_error", {"message": "Conversation not found."})
        return

    body = (payload.get("body") or "").strip()
    if not body:
        emit("chat_error", {"message": "Message cannot be empty."})
        return
    if len(body) > 1000:
        emit("chat_error", {"message": "Message cannot exceed 1000 characters."})
        return

    created_at = datetime.now()
    message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        body=body,
        created_at=created_at,
    )
    db.session.add(message)
    conversation.last_message_at = created_at
    conversation.mark_read_for(user.id)
    db.session.commit()

    emit(
        "message_created",
        serialize_message(message, user.id),
        to=f"conversation:{conversation.id}",
    )
    emit(
        "conversation_updated",
        serialize_conversation(conversation, conversation.buyer_id),
        to=f"user:{conversation.buyer_id}",
    )
    emit(
        "conversation_updated",
        serialize_conversation(conversation, conversation.seller_id),
        to=f"user:{conversation.seller_id}",
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    socketio.run(app, debug=True)
