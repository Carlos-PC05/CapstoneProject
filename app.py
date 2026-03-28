import os
import hashlib
import re
import unicodedata
#from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
#from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename
from models import db, User, Item, ItemImage, Favorite
from utils import mail, generate_confirmation_token, confirm_token, send_email
from dotenv import load_dotenv

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

# Cargar variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "default_secret_key") # Fallback en caso de que no exista
app.config['SECURITY_PASSWORD_SALT'] = os.getenv("SECURITY_PASSWORD_SALT", "default_salt")

# Mail Configuration
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER", 'smtp.googlemail.com')
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

# File Upload Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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

""" Database """

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///database.db")
db.init_app(app)
mail.init_app(app)
#socketio = SocketIO(app, manage_session=False)


def get_current_user_from_session():
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.session.get(User, user_id)
        if user:
            # Keep username during migration period for legacy usages.
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

#Seed de ejmplo 
def seed_data():
    #Verificar que no existen los datos para no duplicar
    if User.query.first():
        return;

    #Crear Usuarios
    user1 = User(username="Carlos", email="carlosparracamacho@gmail.com", is_active=True, items=[], country="España", city="Huércal-Overa", description="Hola, soy Carlos.", photo_url="img/users/fotoNYSkyline.jpeg")
    user1.set_password("Saltador2005_")
    
    user2 = User(username="Juan", email="juanperez@gmail.com", is_active=True, items=[], country="España", city="Madrid", description="Hola, soy Juan.", photo_url = "")  #creamos las instancias de los usuarios
    user2.set_password("Juan1234_")
    
    user3 = User(username="Ana", email="anagomez@gmail.com", is_active=True, items=[], country="España", city="Madrid", description="Hola, soy Ana.", photo_url = "")
    user3.set_password("Ana1234_")

    db.session.add_all([user1, user2, user3]) #Añadimos a la base de datos a estos usuarios
    db.session.commit() #ejecutamos la transacción

    #Crear Items
    item1 = Item(name="Taza", description="Taza de ceramica", brand="", condition="good", price=10.0, category="furniture", images=[], user_id=user1.id)
    item2 = Item(name="Lampara", description="Lampara LED", brand="Philips", condition="good", price=20.0, category="furniture", images=[], user_id=user2.id)
    item3 = Item(name="Mesa", description="Mesa de madera", brand="Ikea", condition="fair", price=30.0, category="furniture", images=[], user_id=user3.id)
    item4 = Item(name="Silla", description="Silla de plástico", brand="", condition="good", price=40.0, category="furniture", images=[], user_id=user1.id)
    item5 = Item(name="Tennis Racket", description="Used tennis racket in good condition", brand="Wilson", condition="good", price=15.0, category="sport", images=[], user_id=user2.id)
    item6 = Item(name="Padel Racket", description="Brand new padel racket, never used", brand="Bullpadel", condition="new", price=100.0, category="sport", images=[], user_id=user3.id)
    item7 = Item(name="Pillow Set", description="Set of 2 comfortable pillows", brand="", condition="like-new", price=25.0, category="bedding", images=[], user_id=user1.id)
    item8 = Item(name="Desk Lamp", description="Adjustable desk lamp with LED light", brand="Xiaomi", condition="good", price=35.0, category="electronics", images=[], user_id=user2.id)
    item9 = Item(name="Jacket", description="Warm winter jacket, size M", brand="Zara", condition="fair", price=50.0, category="clothes", images=[], user_id=user3.id)

    db.session.add_all([item1, item2, item3, item4, item5, item6, item7, item8, item9]) #Añadimos a la base de datos a estos items
    db.session.commit() #ejecutamos la transacción

    # Add images
    img1 = ItemImage(image_url="img/items/taza.jpg", item=item1)
    img2 = ItemImage(image_url="img/items/lampara.jpg", item=item2)
    img3 = ItemImage(image_url="img/items/mesa.jpg", item=item3)
    img4 = ItemImage(image_url="img/items/silla.jpg", item=item4)
    img5 = ItemImage(image_url="img/items/taza2.jpg", item=item1)
    img6 = ItemImage(image_url="img/items/taza3.jpg", item=item1)
    img7 = ItemImage(image_url="img/items/taza4.jpg", item=item1)
    img8 = ItemImage(image_url="img/items/tennis.jpg", item=item5)
    img9 = ItemImage(image_url="img/items/padel.jpg", item=item6)
    img10 = ItemImage(image_url="img/items/pillows.jpg", item=item7)
    img11 = ItemImage(image_url="img/items/deskLamp.jpg", item=item8)
    img12 = ItemImage(image_url="img/items/jacket.jpg", item=item9)
    
    db.session.add_all([img1, img2, img3, img4, img5, img6, img7, img8, img9, img10, img11, img12])
    db.session.commit()

""" 
----------------
    Rutas
----------------
"""


""" Auth """
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        #Obtenemos el email y la contraseña del formulario
        email = request.form.get("email")
        password = request.form.get("password")

        #Buscamos el usuario en la base de datos por su email
        user = User.query.filter_by(email=email).first()

        #Si el usuario no está, cargamos la página de login con un mensaje de error (debemos imprimir alertas y darle estilo)
        if not user:
            return render_template('auth/login.html', error="Email not registered.")

        #Si el usuario está, verificamos la contraseña
        if user and user.check_password(password):
            #La contraseña es correcta

            # Verificar si el usuario está activo
            if not user.is_active:
                return render_template('auth/login.html', error="Please confirm your account first. Check your email.")

            # Guardamos user_id como clave principal de sesion.
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("dashboard"))
        else:
            #Si la contraseña es incorrecta, cargamos la página de login con un mensaje de error (debemos imprimir alertas y darle estilo)
            return render_template('auth/login.html', error="Incorrect password.")
            
    # GET request
    if get_current_user_from_session():
        return redirect(url_for("dashboard"))
    return render_template('auth/login.html')

""" Logout """
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


#Registro de usuarios
@app.route("/auth/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        password2 = request.form.get("password2")
        if len(password) < 8:
            return render_template('auth/SignUp.html', error="The password must be at least 8 characters long.")
        if password != password2:
            return render_template('auth/SignUp.html', error="Passwords don't match.")
        else:
            #Verificar si el usuario ya está registrado
            user = User.query.filter_by(email=email).first()
            if user:
                #ya está registrado
                return render_template('auth/SignUp.html', error = "Email already registered.")
            else:
                #No está registrado, crear usuario inactivo
                newUser = User(username=username, email=email, is_active=False)
                newUser.set_password(password)
                db.session.add(newUser)
                db.session.commit()
                
                # Generar token y enviar email
                token = generate_confirmation_token(newUser.email)
                confirm_url = url_for('confirm_email', token=token, _external=True)
                html = render_template('auth/confirm_email_template.html', confirm_url=confirm_url)
                subject = "Please confirm your email address"
                
                try:
                    send_email(newUser.email, subject, html)
                except Exception as e:
                    print(f"Error sending email: {e}")
                    # In development, print the link in console
                    print(f"LINK DE CONFIRMACION (DEV): {confirm_url}")
                
                return redirect(url_for("confirm"))

    # GET request
    return render_template('auth/SignUp.html')

#Confirmar correo electrónico
@app.route('/auth/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        return render_template('auth/login.html', error="The confirmation link is invalid or has expired.")
        
    user = User.query.filter_by(email=email).first_or_404()
    
    if user.is_active:
        return render_template('auth/login.html', error="Account already confirmed. Please log in.")
    
    user.is_active = True
    db.session.add(user)
    db.session.commit()
    
    return render_template('auth/activated.html')

@app.route("/auth/confirm_info")
def confirm():
    return render_template('auth/confirm.html')

#Recuperar contraseña
@app.route("/auth/recover", methods=["GET", "POST"])
def recover():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if not user:
            return render_template('auth/recover.html', error="Email not registered.")
        
        # Generar token y enviar email
        token = generate_confirmation_token(user.email)
        recover_url = url_for('recover_password', token=token, _external=True)
        html = render_template('auth/recover_password_template.html', recover_url=recover_url)
        subject = "Password recovery"
        try:
            send_email(user.email, subject, html)
        except Exception as e:
            print(f"Error sending email: {e}")
            # In development, print the link in console
            print(f"LINK DE RECOVERY (DEV): {recover_url}")
            
        return render_template('auth/confirm.html')
    
    # GET request
    return render_template('auth/recover.html')

#Restaurar contraseña
@app.route("/auth/restore/<token>", methods=["GET", "POST"])
def recover_password(token):
    try:
        email = confirm_token(token)
    except:
        return render_template('auth/login.html', error="The recovery link is invalid or has expired.")
    
    if request.method == "POST":
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        if len(password) < 8:
            return render_template('auth/restore.html', token=token, error="The password must be at least 8 characters long.")
        
        if not password or not password_confirm:
             return render_template('auth/restore.html', token=token, error="Please fill in all fields")

        if password != password_confirm:
            return render_template('auth/restore.html', token=token, error="Passwords do not match")
            
        user = User.query.filter_by(email=email).first_or_404()
        user.set_password(password)
        db.session.commit()
        
        return render_template('auth/login.html', success="Password updated successfully. Please login.")
        
    return render_template('auth/restore.html', token=token)

""" User Profile """
@app.route("/profile")
def profile():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    return render_template('user/profile.html', user=user)

""" Edit Profile """
@app.route("/user/edit", methods=["GET", "POST"])
def edit_profile():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        #Photo button 
        if 'photo' in request.files:
            file = request.files['photo']
            if file.filename == '':
                flash('No selected file', 'error')
                return redirect(request.url)
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # Calculate file hash to check for duplicates
                file_content = file.read()
                file_hash = hashlib.sha256(file_content).hexdigest()
                # Reset file pointer to beginning
                file.seek(0)
                
                # Get file extension
                file_ext = os.path.splitext(filename)[1].lower()
                
                # Create unique filename based on hash
                unique_filename = f"{file_hash}{file_ext}"
                
                # Define path
                relative_path = os.path.join('img', 'users', unique_filename)
                full_path = os.path.join(app.root_path, 'static', relative_path)
                
                if not os.path.exists(full_path):
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    file.save(full_path)
                
                user.photo_url = f"img/users/{unique_filename}"
                db.session.commit()
                flash('Profile photo updated successfully', 'success')
            else:
                flash('Invalid file type', 'error')

        #Lógica para cambiar el nombre
        #Detecta si se ha enviado el formulario para cambiar el nombre
        if 'username' in request.form:
            #Almacenamos el texto ingresado en el campo de nombre de usuario
            new_username = request.form.get('username')
            #Comprobamos si el nombre de usuario es diferente al actual
            if new_username != user.username:
                #Comprobamos que no esté vacío
                if not new_username:
                    flash('Username cannot be empty.', 'error')
                else:
                    #Todo bien: asociamos nuevo nombre
                    user.username = new_username
                    db.session.commit()
                    session["username"] = new_username # Update session
                    flash('Username updated successfully.', 'success')

        #Lógica de cambio de descripción
        if 'description' in request.form:
            #Almacenamos la nueva descripción
            new_description = request.form.get('description')
            #Comprobamos si la descripción es diferente a la actual
            if new_description != user.description:
                #Comprobamos que no esté vacío
                if not new_description:
                    flash('Description cannot be empty.', 'error')
                else:
                    #Todo bien: asociamos nueva descripción
                    user.description = new_description
                    db.session.commit()
                    flash('Description updated successfully.', 'success')

        return redirect(url_for("edit_profile"))

    return render_template('user/editProfile.html', user=user)

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
             flash('Please fill in all required fields', 'error')
             return redirect(request.url)

        if condition not in VALID_CONDITIONS:
            flash('Invalid condition', 'error')
            return redirect(request.url)
        
        try:
            price = float(price)
        except ValueError:
            flash('Invalid price', 'error')
            return redirect(request.url)

        # Handle photos
        if 'photos' in request.files:
            files = request.files.getlist('photos')
            
            # Check if at least one file is selected (and not empty)
            if not files or files[0].filename == '':
                flash('At least one photo is required', 'error')
                return redirect(request.url)

            # Limit to 6 photos
            if len(files) > 6:
                flash('Maximum 6 photos allowed. Please select fewer photos.', 'error')
                return redirect(request.url)

            # Create Item only if validation passes
            new_item = Item(name=title, description=description, brand=brand, condition=condition, price=price, category=category, user_id=user.id)
            db.session.add(new_item)
            db.session.commit() # Commit to get ID

            #Gestionar cada foto
            for file in files:
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    
                    # Calculate hash
                    file_content = file.read()
                    file_hash = hashlib.sha256(file_content).hexdigest()
                    file.seek(0)
                    
                    file_ext = os.path.splitext(filename)[1].lower()
                    unique_filename = f"{file_hash}{file_ext}"
                    
                    relative_path = os.path.join('img', 'items', unique_filename)
                    full_path = os.path.join(app.root_path, 'static', relative_path)
                    
                    if not os.path.exists(full_path):
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        file.save(full_path)
                    
                    # Create ItemImage
                    new_image = ItemImage(image_url=f"img/items/{unique_filename}", item_id=new_item.id)
                    db.session.add(new_image)
            
            db.session.commit()
            flash('Item uploaded successfully!', 'success')
            return redirect(url_for('profile')) # Redirect to dashboard or item page
        
        else:
             # Item created without photos
             flash('At least one photo is required', 'error')
             return redirect(url_for('upload'))


    return render_template('user/upload.html', edit_mode=False, item=None)

""" Edit Item """
@app.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    item = Item.query.get_or_404(item_id)
    if item.user_id != user.id:
        flash('You cannot edit this item.', 'error')
        return redirect(url_for('item', item_id=item.id))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        brand = (request.form.get("brand") or "").strip()
        condition = normalize_condition(request.form.get("condition"))
        category = (request.form.get("category") or "").strip().lower()
        price = request.form.get("price")

        if not title or not description or not condition or not category or not price:
            flash('Please fill in all required fields', 'error')
            return redirect(request.url)

        if condition not in VALID_CONDITIONS:
            flash('Invalid condition', 'error')
            return redirect(request.url)

        try:
            price = float(price)
        except ValueError:
            flash('Invalid price', 'error')
            return redirect(request.url)

        item.name = title
        item.description = description
        item.brand = brand
        item.condition = condition
        item.category = category
        item.price = price

        files = []
        if 'photos' in request.files:
            files = [file for file in request.files.getlist('photos') if file and file.filename != '']

        if files:
            total_images = len(item.images) + len(files)
            if total_images > 6:
                flash('Maximum 6 photos allowed. Please select fewer photos.', 'error')
                return redirect(request.url)

            for file in files:
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)

                    file_content = file.read()
                    file_hash = hashlib.sha256(file_content).hexdigest()
                    file.seek(0)

                    file_ext = os.path.splitext(filename)[1].lower()
                    unique_filename = f"{file_hash}{file_ext}"

                    relative_path = os.path.join('img', 'items', unique_filename)
                    full_path = os.path.join(app.root_path, 'static', relative_path)

                    if not os.path.exists(full_path):
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        file.save(full_path)

                    new_image = ItemImage(image_url=f"img/items/{unique_filename}", item_id=item.id)
                    db.session.add(new_image)

        db.session.commit()
        flash('Item updated successfully!', 'success')
        return redirect(url_for('item', item_id=item.id))

    return render_template('user/upload.html', edit_mode=True, item=item)

""" Delete Item """
@app.route("/item/delete/<int:item_id>", methods=["GET"])
def delete(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    #Coger item a eliminar
    item = Item.query.get_or_404(item_id)
    try:
        # Eliminar imagenes del objeto
        db.session.query(ItemImage).filter_by(item_id=item_id).delete()
        # Eliminar item
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
        return redirect(url_for('profile'))
    except Exception as e:
        return f"Error deleting item images: {str(e)}"


""" Favorite Items """
@app.route("/user/favItems")
def favItems():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))
    
    # Coger los items favoritos desde la relacion del usuario
    favorite_items = user.favorite_items
    return render_template('user/favItems.html', favorite_items=favorite_items)

@app.route("/item/<int:item_id>/favorite", methods=["POST"])
def toggle_favorite(item_id):
    user = get_current_user_from_session()
    if not user:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    item = Item.query.get_or_404(item_id)

    # Evitar favorites sobre articulos propios
    if item.user_id == user.id:
        return jsonify({"ok": False, "error": "You cannot favorite your own item"}), 400

    existing_favorite = Favorite.query.filter_by(user_id=user.id, item_id=item.id).first()

    if existing_favorite:
        db.session.delete(existing_favorite)
        db.session.commit()
        return jsonify({"ok": True, "is_favorite": False, "item_id": item.id})

    new_favorite = Favorite(user_id=user.id, item_id=item.id)
    db.session.add(new_favorite)
    db.session.commit()
    return jsonify({"ok": True, "is_favorite": True, "item_id": item.id})

""" Messages """
@app.route("/user/messages")
def messages():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    return render_template('user/messages.html')

""" Comprar Item """
@app.route("/item/comprar/<int:item_id>", methods=["POST"])
def comprar(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    #Recuperar el item de la base de datos y editar su estado
    item = Item.query.get_or_404(item_id)
    if item.user_id == user.id:
        flash('You cannot purchase your own item.', 'error')
        return redirect(url_for('item', item_id=item.id))

    if (item.estado or "").lower() != "active":
        flash('This item is already purchased.', 'error')
        return redirect(url_for('item', item_id=item.id))

    item.estado = "comprado"
    db.session.commit()
    flash('Item purchased successfully!', 'success')
    #Enviar correo al dueño
    send_email(
        #to: dueño del objeto
        to = item.owner.email,
        #subject
        subject = "You sold an item!",
        #body
        template = "Congratulations, you have sold an item!! Thank you for using DeSales Exchange Hub.",
    )
    return redirect(url_for('item', item_id=item.id))

""" Dashboard """

@app.route("/dashboard")
def dashboard():
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))
    #Recuperar todos los items de la base de datos
    search_query = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip().lower()
    
    base_query = Item.query.filter(
        db.func.lower(Item.estado) == "active",
        Item.user_id != user.id
    )

    if search_query:
        items = search_items_for_dashboard(base_query, search_query)
    elif category and category != "all":
        items = base_query.filter(db.func.lower(Item.category) == category).order_by(db.func.random()).all()
    else:
        items = base_query.order_by(db.func.random()).all()

    users = User.query.all()
    favorite_item_ids = {favorite_item.id for favorite_item in user.favorite_items}
    return render_template('index.html', items=items, users=users, favorite_item_ids=favorite_item_ids)

""" Item """

@app.route("/item/<int:item_id>")
def item(item_id):
    user = get_current_user_from_session()
    if not user:
        return redirect(url_for("login"))

    #Recuperar el item de la base de datos
    item = Item.query.get_or_404(item_id)
    #Recuperar los items similares de la base de datos (límite de 10)
    similar_items = Item.query.filter_by(category=item.category).filter(Item.id != item.id).limit(10).all()
    favorite_item_ids = {favorite_item.id for favorite_item in user.favorite_items}
    return render_template('item.html', item=item, similar_items=similar_items, favorite_item_ids=favorite_item_ids)

""" App """
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)
