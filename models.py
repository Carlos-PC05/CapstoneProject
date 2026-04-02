from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=False, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    items = db.relationship("Item", backref="owner", lazy=True)
    favorite_items = db.relationship("Item", secondary="favorite", back_populates="favorited_by", lazy=True)
    country = db.Column(db.String(20), nullable=True, default="")
    city = db.Column(db.String(20), nullable=True, default="")
    description = db.Column(db.String(400), nullable=True, default="")
    photo_url = db.Column(db.String(200), nullable=True, default="")

    def __repr__(self) -> str:
        return f"<User {self.username}>"

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(400), nullable=False)
    condition = db.Column(db.String(20), nullable=True, default="")
    brand = db.Column(db.String(50), nullable=True, default="")
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="active")
    images = db.relationship("ItemImage", backref="item", lazy=True)
    favorited_by = db.relationship("User", secondary="favorite", back_populates="favorite_items", lazy=True)

    @property
    def image_url(self):
        if self.images:
            return self.images[0].image_url
        return "img/default.jpg"

    def __repr__(self) -> str:
        return f"<Item {self.name}>"


class ItemImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(200), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)

    def __repr__(self) -> str:
        return f"<ItemImage {self.image_url}>"


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint("user_id", "item_id", name="uq_favorite_user_item"),)

""" Chat Models """

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    last_message_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    buyer_last_read_at = db.Column(db.DateTime, nullable=True)
    seller_last_read_at = db.Column(db.DateTime, nullable=True)

    item = db.relationship("Item", backref=db.backref("conversations", lazy=True))
    buyer = db.relationship("User", foreign_keys=[buyer_id], backref=db.backref("buyer_conversations", lazy=True))
    seller = db.relationship("User", foreign_keys=[seller_id], backref=db.backref("seller_conversations", lazy=True))
    messages = db.relationship(
        "Message",
        backref="conversation",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )

    __table_args__ = (
        db.UniqueConstraint("item_id", "buyer_id", "seller_id", name="uq_conversation_item_buyer_seller"),
    )

    @property
    def last_message(self):
        if self.messages:
            return self.messages[-1]
        return None

    def other_user_for(self, user_id):
        if user_id == self.buyer_id:
            return self.seller
        if user_id == self.seller_id:
            return self.buyer
        return None

    def is_unread_for(self, user_id):
        if not self.last_message_at:
            return False

        if user_id == self.buyer_id:
            last_read_at = self.buyer_last_read_at
        elif user_id == self.seller_id:
            last_read_at = self.seller_last_read_at
        else:
            return False

        if last_read_at is None:
            return self.last_message is not None

        return self.last_message_at > last_read_at

    def mark_read_for(self, user_id):
        read_at = datetime.utcnow()

        if user_id == self.buyer_id:
            self.buyer_last_read_at = read_at
            return True

        if user_id == self.seller_id:
            self.seller_last_read_at = read_at
            return True

        return False


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    sender = db.relationship("User", backref=db.backref("sent_messages", lazy=True))
