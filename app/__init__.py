import os
from flask import Flask
from app.db import init_db

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    
    os.makedirs(app.instance_path, exist_ok=True)
    default_db = os.path.join(app.instance_path, "attendance.db")
    
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-attendance-key-2025"),
        DATABASE=default_db,
    )
    
    if test_config:
        app.config.update(test_config)
        
    init_db(app.config["DATABASE"])
    
    from app.routes import bp
    app.register_blueprint(bp)
    
    return app
