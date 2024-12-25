from flask import Flask
from .routes import main
import firebase_init

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    # Register blueprints
    app.register_blueprint(main)

    return app
