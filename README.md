

# 🛒 DeSales Exchange Hub — University Marketplace

A web application built with **Flask** that allows university students to buy, sell, and exchange second-hand items within their academic community.

---

## 📋 Table of Contents

- [About the Project](#about-the-project)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Database Models](#database-models)
- [Contributing](#contributing)

---

## 📖 About the Project

DeSales Exchange Hub is my Capstone Project developed as a university marketplace platform. It provides a space where students can publish items for sale, browse listings by category, save favorites, and communicate directly with sellers through an integrated chat system.

---

## ✨ Features

- 🔐 User authentication (register, login, email activation)
- 📦 Create, edit, delete item listings with images
- 🔍 Browse and filter items by category
- ❤️ Save favorite items
- 💬 Real-time messaging between buyers and sellers
- 👤 User profile with photo, location (static), and description
- ⚙️ Background task processing with Huey

---

## 🛠 Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | Python, Flask, Flask-SQLAlchemy   |
| Frontend   | HTML, SCSS, JavaScript            |
| Database   | SQLite (via SQLAlchemy ORM)       |
| Task Queue | Huey                              |
| Auth       | Werkzeug (password hashing)       |
| Styles     | SCSS compiled via npm             |

---

## 📁 Project Structure

```
CapstoneProject/
├── app.py              # Main Flask application & routes
├── models.py           # SQLAlchemy database models
├── utils.py            # Utility/helper functions
├── run_huey.py         # Huey task queue runner
├── requirements.txt    # Python dependencies
├── package.json        # Node.js dependencies (SCSS compiler)
├── static/             # Static assets (CSS, JS, images)
├── templates/          # Jinja2 HTML templates
└── instance/           # Instance-specific config & SQLite DB
```
---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js & npm
- pip

### Installation

1. **Clone the repository**
```bash
   git clone https://github.com/Carlos-PC05/CapstoneProject.git
   cd CapstoneProject
```

2. **Create and activate a virtual environment**
```bash
   python -m venv venv
   source venv/bin/activate      # Linux/macOS
   venv\Scripts\activate         # Windows
```

3. **Install Python dependencies**
```bash
   pip install -r requirements.txt
```

4. **Install Node.js dependencies**
```bash
   npm install
```

5. **Initialize the database**
```bash
   flask shell
   >>> from models import db
   >>> db.create_all()
   >>> exit()
```

---

## ▶️ Usage

You need **three terminals** running simultaneously:

**Terminal 1 — SCSS Watch Mode**
```bash
npm run watch
```

**Terminal 2 — Flask Development Server** *(inside virtual environment)*
```bash
python app.py
```

**Terminal 3 — Huey Task Worker** *(inside virtual environment)*
```bash
python -m huey.bin.huey_consumer run_huey.huey
```

Then open your browser at `http://localhost:5000`.

### Demo

[![CapstoneProjectDemo]([https://img.youtube.com/vi/ID_DE_TU_VIDEO/0.jpg])]

---

## 🗄 Database Models

| Model          | Description                                      |
|----------------|--------------------------------------------------|
| `User`         | Registered users with profile info              |
| `Item`         | Listings with name, price, category, condition  |
| `ItemImage`    | Images associated with each item                |
| `Favorite`     | Many-to-many: users ↔ favorite items            |
| `Conversation` | Chat thread between a buyer and a seller        |
| `Message`      | Individual messages within a conversation       |

---

## 🤝 Contributing

This is a university Capstone Project. Contributions, suggestions, and feedback are welcome.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

---

*Developed as a Computer Science Capstone Project at Desales University.*
