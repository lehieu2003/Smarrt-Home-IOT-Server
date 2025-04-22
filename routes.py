from flask import Blueprint, jsonify, request
from models import db, Room, Device
from mqtt_client import publish_device_status, get_mqtt_status
from auth_routes import token_required
from datetime import datetime

api = Blueprint('api', __name__)

# Rooms
@api.route('/rooms', methods=['GET'])
@token_required
def get_rooms(current_user):
    # Filter rooms by the current user's ID
    rooms = Room.query.filter_by(owner_id=current_user.id).all()
    return jsonify([{'id': room.id, 'name': room.name} for room in rooms])

# Devices
@api.route('/devices', methods=['GET'])
@token_required
def get_devices(current_user):
    # Get rooms owned by current user first
    user_rooms = Room.query.filter_by(owner_id=current_user.id).all()
    user_room_ids = [room.id for room in user_rooms]
    
    # Filter devices to only include those in rooms owned by current user
    devices = Device.query.filter(Device.room_id.in_(user_room_ids)).all()
    
    return jsonify([{
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id
    } for device in devices])

@api.route('/rooms/<int:room_id>/devices', methods=['GET'])
@token_required
def get_room_devices(current_user, room_id):
    devices = Device.query.filter_by(room_id=room_id).all()
    return jsonify([{
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id
    } for device in devices])

@api.route('/devices', methods=['POST'])
@token_required
def add_device(current_user):
    data = request.json
    device = Device(
        name=data['name'],
        type=data['type'],
        status=data.get('status', False),
        value=data.get('value', 0),
        room_id=data['room_id']
    )
    db.session.add(device)
    db.session.commit()
    
    # Publish new device to MQTT
    publish_device_status(device)
    
    return jsonify({
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id
    }), 201
    
# this route for update the status of the devices afterr user control devices (MQTT Broker)
@api.route('/devices/<int:device_id>', methods=['PUT'])
@token_required
def update_device(current_user, device_id):
    device = Device.query.get_or_404(device_id)
    data = request.json
    
    if 'status' in data:
        device.status = data['status']
    if 'value' in data:
        device.value = data['value']
    
    db.session.commit()
    
    # Publish device state change to MQTT and capture success/failure
    mqtt_success = publish_device_status(device)
    
    response = {
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id,
        'mqtt_published': mqtt_success
    }
    
    return jsonify(response)

@api.route('/devices/<int:device_id>/toggle', methods=['POST'])
@token_required
def toggle_device(current_user, device_id):
    device = Device.query.get_or_404(device_id)
    device.status = not device.status
    db.session.commit()
    
    # Publish device state change to MQTT and track success
    mqtt_success = publish_device_status(device)
    
    response = {
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id,
        'mqtt_published': mqtt_success
    }
    
    return jsonify(response)

@api.route('/devices/<int:device_id>/control', methods=['POST'])
@token_required
def control_device(current_user, device_id):
    device = Device.query.get_or_404(device_id)
    data = request.json
    
    # Track if anything changed
    changed = False
    
    # Ensure device type is not None
    if device.type is None:
        device.type = "unknown"
        changed = True
    
    # Handle device control based on type and parameters
    if 'status' in data:
        if device.status != data['status']:
            device.status = data['status']
            changed = True
        
    if 'value' in data:
        if device.value != data['value']:
            device.value = data['value']
            changed = True
        
    # Handle special control parameters based on device type
    if 'command' in data and device.type:
        if device.type == 'light' and 'brightness' in data['command']:
            if device.value != data['command']['brightness']:
                device.value = data['command']['brightness']
                changed = True
        elif device.type == 'thermostat' and 'temperature' in data['command']:
            if device.value != data['command']['temperature']:
                device.value = data['command']['temperature']
                changed = True
        elif device.type == 'fan' and 'speed' in data['command']:
            if device.value != data['command']['speed']:
                device.value = data['command']['speed']
                changed = True
    
    # commit changes to the database only if something changed
    db.session.commit()
    
    # Ensure device state change is published to MQTT
    # Important: Always publish regardless of whether the database changed
    # The device state must be synchronized with ShiftR
    success = publish_device_status(device)
    
    response = {
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id,
        'message': 'Device control successful',
        'mqtt_published': success
    }
    
    return jsonify(response)

@api.route('/devices/<int:device_id>', methods=['DELETE'])
@token_required
def delete_device(current_user, device_id):
    device = Device.query.get_or_404(device_id)
    
    # Get device info before deletion for response
    device_info = {
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id
    }
    
    # Delete the device from database
    db.session.delete(device)
    db.session.commit()
    
    return jsonify({
        'message': 'Device deleted successfully',
        'device': device_info
    })

# Add a new route to check MQTT status
@api.route('/mqtt_status', methods=['GET'])
def mqtt_connection_status():
    status = get_mqtt_status()
    return jsonify(status)

# Sensor data endpoint
@api.route('/sensor_data', methods=['GET'])
@token_required
def get_sensor_data(current_user):
    # Get rooms owned by current user first
    user_rooms = Room.query.filter_by(owner_id=current_user.id).all()
    user_room_ids = [room.id for room in user_rooms]
    
    # Filter sensor devices to only include those in rooms owned by current user
    sensors = Device.query.filter(
        Device.room_id.in_(user_room_ids),
        Device.type.in_(['sensor', 'temperature', 'humidity', 'motion', 'light_sensor'])
    ).all()
    
    return jsonify([{
        'id': device.id,
        'name': device.name,
        'type': device.type,
        'status': device.status,
        'value': device.value,
        'room_id': device.room_id,
        'timestamp': datetime.now().isoformat()
    } for device in sensors])

# Advanced sensor data with room grouping
@api.route('/advanced_sensor_data', methods=['GET'])
@token_required
def get_advanced_sensor_data(current_user):
    # Get rooms owned by current user
    user_rooms = Room.query.filter_by(owner_id=current_user.id).all()
    user_room_ids = [room.id for room in user_rooms]
    
    # Get all sensors in these rooms
    sensors = Device.query.filter(
        Device.room_id.in_(user_room_ids),
        Device.type.in_(['sensor', 'temperature', 'humidity', 'motion', 'light_sensor'])
    ).all()
    
    # Group by rooms
    rooms_data = {}
    for room in user_rooms:
        room_sensors = [s for s in sensors if s.room_id == room.id]
        rooms_data[room.id] = {
            'room_name': room.name,
            'room_id': room.id,
            'sensors': [{
                'id': device.id,
                'name': device.name,
                'type': device.type,
                'status': device.status,
                'value': device.value,
                'timestamp': datetime.now().isoformat()
            } for device in room_sensors]
        }
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'rooms': rooms_data
    })

# Overall device status dashboard data
@api.route('/device_status', methods=['GET'])
@token_required
def get_device_status(current_user):
    # Get rooms owned by current user
    user_rooms = Room.query.filter_by(owner_id=current_user.id).all()
    user_room_ids = [room.id for room in user_rooms]
    
    # Get all devices in these rooms
    devices = Device.query.filter(Device.room_id.in_(user_room_ids)).all()
    
    # Count devices by type and status
    device_count = len(devices)
    online_count = sum(1 for device in devices if device.status)
    offline_count = device_count - online_count
    
    # Count by type
    type_counts = {}
    for device in devices:
        device_type = device.type or "unknown"
        if device_type not in type_counts:
            type_counts[device_type] = {"total": 0, "online": 0}
        type_counts[device_type]["total"] += 1
        if device.status:
            type_counts[device_type]["online"] += 1
    
    # Check MQTT broker status
    mqtt_status = get_mqtt_status()
    
    return jsonify({
        'total_devices': device_count,
        'online_devices': online_count,
        'offline_devices': offline_count,
        'device_types': type_counts,
        'mqtt_status': mqtt_status,
        'timestamp': datetime.now().isoformat()
    })

# Public MQTT status endpoint for system monitoring
@api.route('/system/mqtt_status', methods=['GET'])
def system_mqtt_status():
    status = get_mqtt_status()
    return jsonify(status)

# Add error handling for 404 errors
@api.errorhandler(404)
def resource_not_found(e):
    return jsonify(error="Resource not found"), 404