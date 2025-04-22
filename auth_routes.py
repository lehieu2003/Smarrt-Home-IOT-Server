# auth_routes.py
from flask import Blueprint, request, jsonify
from models import db, User
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os

auth = Blueprint('auth', __name__)
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key')

# Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

@auth.route('/register', methods=['POST'])
def register():
    data = request.json
    
    # Check if user already exists
    existing_user = User.query.filter((User.username == data['username']) | 
                                      (User.email == data['email'])).first()
    if existing_user:
        return jsonify({'message': 'Username or email already exists'}), 409
    
    # Create new user
    new_user = User(
        username=data['username'],
        email=data['email']
    )
    new_user.set_password(data['password'])
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'User registered successfully'}), 201

@auth.route('/login', methods=['POST'])
def login():
    data = request.json
    
    # Find user by username or email
    user = User.query.filter((User.username == data.get('username')) | 
                             (User.email == data.get('email'))).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    # Generate token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, SECRET_KEY, algorithm="HS256")
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    })

@auth.route('/user', methods=['GET'])
@token_required
def get_user(current_user):
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'created_at': current_user.created_at
    })