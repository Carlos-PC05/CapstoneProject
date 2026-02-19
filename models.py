from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(20), unique = False, nullable = False)
    email = db.Column(db.String(120), unique = True, nullable = False)
    password = db.Column(db.String(255), nullable = False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    items = db.relationship('Item', backref = 'owner', lazy = True)
    country = db.Column(db.String(20), nullable = True, default = "")
    city = db.Column(db.String(20), nullable = True, default = "")
    description = db.Column(db.String(400), nullable = True, default = "")
    photo_url = db.Column(db.String(200), nullable = True, default = "")

    def __repr__(self) -> str:
        return f"<User {self.username}>"

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    name = db.Column(db.String(50), nullable = False)
    description = db.Column(db.String(400), nullable = False)
    price = db.Column(db.Float, nullable = False)
    category = db.Column(db.String(20), nullable = False)
    created_at = db.Column(db.DateTime, nullable = False, default = db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False)
    images = db.relationship('ItemImage', backref='item', lazy=True)

    @property
    def image_url(self):
        if self.images:
            return self.images[0].image_url
        return "img/default.jpg" # Fallback image

    def __repr__(self) -> str:
        return f"<Item {self.name}>"

class ItemImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(200), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)

    def __repr__(self) -> str:
        return f"<ItemImage {self.image_url}>"
