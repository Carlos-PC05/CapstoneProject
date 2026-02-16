import os
from unicodedata import category
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

""" Database """

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(20), unique = True, nullable = False)
    email = db.Column(db.String(120), unique = True, nullable = False)
    password = db.Column(db.String(60), nullable = False)
    items = db.relationship('Item', backref = 'owner', lazy = True)

    def __repr__(self) -> str:
        return f"<User {self.username}>"

class Item(db.Model):
    id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    name = db.Column(db.String(50), nullable = False)
    description = db.Column(db.String(400), nullable = False)
    price = db.Column(db.Float, nullable = False)
    category = db.Column(db.String(20), nullable = False)
    image_url = db.Column(db.String(200), nullable = False)
    created_at = db.Column(db.DateTime, nullable = False, default = db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False)

    def __repr__(self) -> str:
        return f"<Item {self.name}>"

""" 
TODO:
    Para que la base de datos admita que cada objeto pueda tener más de una foto
    debemos crear una nueva tabla que relacione la clave primaria de cada objeto con 
    cada una de las fotos que tiene.
"""

#Seed de ejmplo 
def seed_data():
    #Verificar que no existen los datos para no duplicar
    if User.query.first():
        return;

    #Crear Usuarios
    user1 = User(username="Carlos", email="carlosparracamacho@gmail.com", password="Saltador2005_", items=[])
    user2 = User(username="Juan", email="juanperez@gmail.com", password="Juan1234_", items=[])  #creamos las instancias de los usuarios
    user3 = User(username="Ana", email="anagomez@gmail.com", password="Ana1234_", items=[])

    db.session.add_all([user1, user2, user3]) #Añadimos a la base de datos a estos usuarios
    db.session.commit() #ejecutamos la transacción

    #Crear Items
    item1 = Item(name="Taza", description="Taza de ceramica", price=10.0, category="Hogar", image_url="img/items/taza.jpg", user_id=user1.id)
    item2 = Item(name="Lampara", description="Lampara LED", price=20.0, category="Hogar", image_url="img/items/lampara.jpg", user_id=user2.id)
    item3 = Item(name="Mesa", description="Mesa de madera", price=30.0, category="Hogar", image_url="img/items/mesa.jpg", user_id=user3.id)
    item4 = Item(name="Silla", description="Silla de plástico", price=40.0, category="Hogar", image_url="img/items/silla.jpg", user_id=user1.id)

    db.session.add_all([item1, item2, item3, item4]) #Añadimos a la base de datos a estos items
    db.session.commit() #ejecutamos la transacción

""" Auth """

@app.route("/")
def login():
    return render_template('auth/login.html')

@app.route("/auth/signup")
def signup():
    return render_template('auth/SignUp.html')

@app.route("/auth/recover")
def recover():
    return render_template('auth/Recover.html')

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
