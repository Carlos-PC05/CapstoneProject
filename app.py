import os
from unicodedata import category
from flask import Flask, render_template, request
from models import db, User, Item, ItemImage

app = Flask(__name__)

""" Database """

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
db.init_app(app)

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
