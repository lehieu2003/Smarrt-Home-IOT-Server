from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models import db, Room, Device  # Import Room and Device directly
from routes import api
from auth_routes import token_required, auth
from mqtt_client import setup_mqtt_client, disconnect_mqtt

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Enable CORS
    CORS(app)
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(auth, url_prefix='/auth')
    
    # Global error handler for 404 errors
    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Endpoint not found"), 404
    
    # Create database tables
    with app.app_context():
        db.create_all()
        
        # Add some initial data if database is empty
        if not db.session.query(db.exists().where(Room.id == 1)).scalar():  # Use imported Room instead of models.Room
            living_room = Room(name="Living Room")  # Use Room directly
            bedroom = Room(name="Bedroom")
            db.session.add_all([living_room, bedroom])
            db.session.commit()
            
            devices = [
                Device(name="Main Light", type="light", room_id=1),  # Use Device directly
                Device(name="TV", type="plug", room_id=1),
                Device(name="AC", type="thermostat", value=24, room_id=1),
                Device(name="Bedroom Light", type="light", room_id=2),
                Device(name="Fan", type="fan", room_id=2)
            ]
            db.session.add_all(devices)
            db.session.commit()
    
    # Setup MQTT client - uncommented to enable local MQTT
    setup_mqtt_client(app)
    
    # Register teardown function
    @app.teardown_appcontext
    def teardown_mqtt(exception=None):
        disconnect_mqtt()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)