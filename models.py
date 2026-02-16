from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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
    # image_url removed in favor of ItemImage table
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
