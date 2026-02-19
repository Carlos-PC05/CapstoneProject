import os
from flask import Flask, render_template, request, redirect, url_for, session
from models import db, User, Item, ItemImage
from utils import mail, generate_confirmation_token, confirm_token, send_email
from extensions import huey
from dotenv import load_dotenv

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

""" Database """

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///database.db")
db.init_app(app)
mail.init_app(app)

#Seed de ejmplo 
def seed_data():
    #Verificar que no existen los datos para no duplicar
    if User.query.first():
        return;

    #Crear Usuarios
    user1 = User(username="Carlos", email="carlosparracamacho@gmail.com", is_active=True, items=[])
    user1.set_password("Saltador2005_")
    
    user2 = User(username="Juan", email="juanperez@gmail.com", is_active=True, items=[])  #creamos las instancias de los usuarios
    user2.set_password("Juan1234_")
    
    user3 = User(username="Ana", email="anagomez@gmail.com", is_active=True, items=[])
    user3.set_password("Ana1234_")

    db.session.add_all([user1, user2, user3]) #Añadimos a la base de datos a estos usuarios
    db.session.commit() #ejecutamos la transacción

    #Crear Items
    item1 = Item(name="Taza", description="Taza de ceramica", price=10.0, category="Hogar", images=[], user_id=user1.id)
    item2 = Item(name="Lampara", description="Lampara LED", price=20.0, category="Hogar", images=[], user_id=user2.id)
    item3 = Item(name="Mesa", description="Mesa de madera", price=30.0, category="Hogar", images=[], user_id=user3.id)
    item4 = Item(name="Silla", description="Silla de plástico", price=40.0, category="Hogar", images=[], user_id=user1.id)

    db.session.add_all([item1, item2, item3, item4]) #Añadimos a la base de datos a estos items
    db.session.commit() #ejecutamos la transacción

    # Add images
    img1 = ItemImage(image_url="img/items/taza.jpg", item=item1)
    img2 = ItemImage(image_url="img/items/lampara.jpg", item=item2)
    img3 = ItemImage(image_url="img/items/mesa.jpg", item=item3)
    img4 = ItemImage(image_url="img/items/silla.jpg", item=item4)
    img5 = ItemImage(image_url="img/items/taza2.jpg", item=item1)
    img6 = ItemImage(image_url="img/items/taza3.jpg", item=item1)
    img7 = ItemImage(image_url="img/items/taza4.jpg", item=item1)
    
    db.session.add_all([img1, img2, img3, img4, img5, img6, img7])
    db.session.commit()

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

            #Guardamos el username en la sesión y redirigimos al dashboard
            session["username"] = user.username
            return redirect(url_for("dashboard"))
        else:
            #Si la contraseña es incorrecta, cargamos la página de login con un mensaje de error (debemos imprimir alertas y darle estilo)
            return render_template('auth/login.html', error="Incorrect password.")
            
    # GET request
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template('auth/login.html')

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
                return render_template('auth/login.html', error = "Email already registered.")
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

""" Dashboard """

@app.route("/dashboard")
def dashboard():
    #Recuperar todos los items de la base de datos
    items = Item.query.all()
    users = User.query.all()
    return render_template('index.html', items=items, users=users)

@app.route("/item/<int:item_id>")
def item(item_id):
    #Recuperar el item de la base de datos
    item = Item.query.get_or_404(item_id)
    #Recuperar los items similares de la base de datos (límite de 10)
    similar_items = Item.query.filter_by(category=item.category).filter(Item.id != item.id).limit(10).all()
    return render_template('item.html', item=item, similar_items=similar_items)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)
