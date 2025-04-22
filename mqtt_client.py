import json
import os
import paho.mqtt.client as mqtt
import time
from dotenv import load_dotenv
from models import db, Device

# Load environment variables
load_dotenv()

# MQTT Configuration
MQTT_BROKER_URL = os.getenv('MQTT_BROKER_URL', 'localhost')  # Fixed: Use getenv correctly with default value
MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')  # Username can be empty for local mosquitto without auth
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')  # Password can be empty for local mosquitto without auth
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', f'smart_home_app_{int(time.time())}')
MQTT_TOPIC_PREFIX = "smart-home/"
MQTT_RECONNECT_DELAY = 5  # seconds to wait before reconnect attempts
MQTT_CONNECTION_TIMEOUT = 10  # seconds to wait for connection

client = None
mqtt_app = None
mqtt_connected = False
mqtt_connection_error = "Not initialized"

def sanitize_topic(topic_part):
    """Ensure topic parts are valid MQTT topic names"""
    if not topic_part:
        return "unknown"
    # Replace spaces and special characters that might cause issues in MQTT topics
    return str(topic_part).replace(' ', '_').replace('/', '_').replace('+', '_').replace('#', '_').replace('&', '_')

def get_device_topic(device):
    """Generate a proper MQTT topic for a device based on its ID (follows API route pattern)"""
    device_id_str = sanitize_topic(str(device.id))
    # Use format similar to API routes: devices/{id}
    return f"{MQTT_TOPIC_PREFIX}devices/{device_id_str}"

def publish_device_status(device):
    """Publish device status to MQTT topic"""
    global client, mqtt_connected
    
    # Check if client exists and is connected
    if not client:
        print("MQTT client not initialized. Cannot publish message.")
        return False
    
    if not mqtt_connected or not client.is_connected():
        print("MQTT client not connected. Attempting to reconnect...")
        reconnected = try_reconnect()
        if not reconnected:
            print("Failed to reconnect to MQTT broker. Message not published.")
            return False

    try:
        # Get properly formatted topic for this device (follows API pattern)
        base_topic = get_device_topic(device)
        status_topic = f"{base_topic}/status"   # devices/{id}/status - matches API pattern
        
        payload = json.dumps({
            'id': device.id,
            'name': device.name,
            'type': device.type,
            'status': device.status,
            'value': device.value,
            'room_id': device.room_id,
            'timestamp': time.time()
        })
        
        # Use retain flag to ensure status persists on broker
        result = client.publish(status_topic, payload, qos=1, retain=True)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Successfully published to {status_topic}: {payload}")
            
            # Also publish to legacy topics for backward compatibility
            legacy_topic = f"{MQTT_TOPIC_PREFIX}{sanitize_topic(device.type or 'unknown')}/{device.id}/status"
            client.publish(legacy_topic, payload, qos=1, retain=True)
            
            # Also publish to a common status topic for all devices
            common_topic = f"{MQTT_TOPIC_PREFIX}all/updates"
            client.publish(common_topic, payload, qos=0, retain=False)
            
            return True
        else:
            print(f"Failed to publish to {status_topic}. Error code: {result.rc}")
            return False
    except Exception as e:
        print(f"Error publishing message: {e}")
        return False

def on_connect(client, userdata, flags, rc):
    global mqtt_connected, mqtt_connection_error
    connect_results = {
        0: "Connection successful",
        1: "Connection refused - incorrect protocol version",
        2: "Connection refused - invalid client identifier",
        3: "Connection refused - server unavailable",
        4: "Connection refused - bad username or password",
        5: "Connection refused - not authorized",
        6: "Connection refused - not yet available",
        7: "Connection refused - server unavailable"
    }
    
    if rc == 0:
        mqtt_connected = True
        mqtt_connection_error = None
        print(f"Successfully connected to MQTT broker ({MQTT_BROKER_URL}:{MQTT_BROKER_PORT})")
        
        # Subscribe only to legacy formats for backward compatibility
        for device_type in ["light", "thermostat", "plug", "fan", "sensor", "unknown"]:
            client.subscribe(f"{MQTT_TOPIC_PREFIX}{device_type}/+/control")
            client.subscribe(f"{MQTT_TOPIC_PREFIX}{device_type}/+/status")
        
        # Also subscribe to simple control topics
        client.subscribe(f"{MQTT_TOPIC_PREFIX}control/#")
        
        print(f"Subscribed to legacy topics for backward compatibility")
    else:
        mqtt_connected = False
        result_message = connect_results.get(rc, f"Unknown error (code {rc})")
        mqtt_connection_error = result_message
        print(f"Failed to connect to MQTT broker: {result_message}")
        print(f"Current settings - Broker: {MQTT_BROKER_URL}, Port: {MQTT_BROKER_PORT}")
        print(f"Username: {MQTT_USERNAME}, Client ID: {MQTT_CLIENT_ID}")

def on_disconnect(client, userdata, rc):
    global mqtt_connected, mqtt_connection_error
    mqtt_connected = False
    
    if rc == 0:
        mqtt_connection_error = "Disconnected normally"
        print("Disconnected from MQTT broker normally")
    else:
        mqtt_connection_error = f"Unexpected disconnect (code {rc})"
        print(f"Disconnected from MQTT broker with result code: {rc}")
        if rc == 7:
            print("Error 7: This is commonly an authentication or permission issue")
        print("Unexpected disconnection. Will attempt to reconnect after delay...")

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages for device control"""
    try:
        print(f"Received message on topic: {msg.topic}")
        
        # Extract device ID from topic
        topic_parts = msg.topic.split('/')
        device_id = None
        action = None
        
        # Handle different topic formats:
        # 1. API style: smart-home/devices/1/control
        # 2. Legacy type-based: smart-home/light/1/control
        # 3. Simple control: smart-home/control/1
        
        if len(topic_parts) >= 4:
            # Check API style first (devices/{id}/action)
            if topic_parts[1] == "devices" and topic_parts[3] in ["control", "status", "toggle"]:
                try:
                    device_id = int(topic_parts[2])
                    action = topic_parts[3]
                except ValueError:
                    print(f"Invalid device ID in topic: {msg.topic}")
                    return
            
            # Check legacy format (type/{id}/action)
            elif topic_parts[2].isdigit() and topic_parts[3] in ["control", "status", "toggle"]:
                try:
                    device_id = int(topic_parts[2])
                    action = topic_parts[3]
                except ValueError:
                    print(f"Invalid device ID in topic: {msg.topic}")
                    return
        
        # Check simple format (control/{id})
        elif len(topic_parts) >= 3 and topic_parts[1] == "control":
            try:
                device_id = int(topic_parts[2])
                action = "control"
            except ValueError:
                print(f"Invalid device ID in topic: {msg.topic}")
                return
        
        if not device_id:
            print(f"Could not extract device ID from topic: {msg.topic}")
            return
            
        # Parse the message payload
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            # Handle simple string commands from mosquitto_pub
            payload_str = msg.payload.decode().strip().lower()
            payload = {}
            
            # Simple commands like "on", "off", or numeric values
            if payload_str in ["on", "true", "1"]:
                payload["status"] = True
            elif payload_str in ["off", "false", "0"]:
                payload["status"] = False
            elif action == "toggle":
                payload["toggle"] = True
            else:
                try:
                    # Try to interpret as a numeric value
                    value = float(payload_str)
                    payload["value"] = value
                except ValueError:
                    print(f"Unrecognized command: {payload_str}")
                    return
        
        # Update device in database
        with mqtt_app.app_context():
            device = Device.query.get(device_id)
            if device:
                # Handle special actions
                if action == "toggle" or "toggle" in payload:
                    device.status = not device.status
                    print(f"Toggling device {device_id} to {device.status}")
                else:
                    # Normal control
                    if 'status' in payload:
                        device.status = payload['status']
                    if 'value' in payload:
                        device.value = payload['value']
                
                db.session.commit()
                
                # Publish the updated status
                publish_device_status(device)
                print(f"Updated device {device_id}: {payload}")
            else:
                print(f"Device {device_id} not found")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

def try_reconnect():
    """Try to reconnect to the MQTT broker"""
    global client, mqtt_connected, mqtt_connection_error
    
    if not client:
        mqtt_connection_error = "MQTT client not initialized"
        return False
    
    try:
        print(f"Attempting to reconnect to MQTT broker {MQTT_BROKER_URL}...")
        # Add a delay before reconnection attempt to avoid immediate retries
        time.sleep(MQTT_RECONNECT_DELAY)
        
        # Create a new client if the old one is in a bad state
        if not client.is_connected():
            # Close the old connection first
            try:
                client.loop_stop()
                client.disconnect()
            except:
                pass
                
            # Create and configure a new client instance
            unique_client_id = f"{MQTT_CLIENT_ID or 'smart_home_app'}_{int(time.time())}"
            print(f"Creating new MQTT client with ID: {unique_client_id}")
            
            client = mqtt.Client(client_id=unique_client_id, clean_session=True, protocol=mqtt.MQTTv311)
            
            if MQTT_USERNAME and MQTT_PASSWORD:
                client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
                
            client.on_connect = on_connect
            client.on_disconnect = on_disconnect
            client.on_message = on_message
            
            # Set will message
            client.will_set(
                f"{MQTT_TOPIC_PREFIX}system/clients/{unique_client_id}", 
                payload=json.dumps({"status": "offline"}), 
                qos=1,
                retain=True
            )
            
            # Connect and start loop
            client.connect(MQTT_BROKER_URL, MQTT_BROKER_PORT, keepalive=60)
            client.loop_start()
        else:
            # Try simple reconnect if client exists and seems healthy
            client.reconnect()
            
        # Wait to check connection status
        wait_count = 0
        max_wait = 5  # Maximum seconds to wait for connection
        while wait_count < max_wait and not mqtt_connected:
            time.sleep(1)
            wait_count += 1
            
        if mqtt_connected:
            print(f"Successfully reconnected to MQTT broker after {wait_count} seconds")
            return True
        else:
            mqtt_connection_error = "Failed to reconnect within timeout"
            print(f"Failed to reconnect to MQTT broker after {max_wait} seconds")
            return False
    except Exception as e:
        mqtt_connection_error = f"Reconnection failed: {str(e)}"
        print(f"Failed to reconnect to MQTT broker: {e}")
        return False

def setup_mqtt_client(app):
    """Initialize and configure MQTT client"""
    global client, mqtt_app, mqtt_connected, mqtt_connection_error
    mqtt_app = app
    
    if client:
        # If client already exists, disconnect it first
        try:
            client.loop_stop()
            client.disconnect()
        except Exception as e:
            print(f"Error disconnecting existing client: {e}")
    
    # Create new client instance with a uniquely identifiable client_id
    unique_client_id = f"{MQTT_CLIENT_ID or 'smart_home_app'}_{int(time.time())}"
    print(f"Creating MQTT client with ID: {unique_client_id}")
    
    # Set 3.1.1 protocol version explicitly
    client = mqtt.Client(client_id=unique_client_id, clean_session=True, protocol=mqtt.MQTTv311)
    
    # Only set username/password if they are provided
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Set a reasonable keepalive interval (in seconds)
    keepalive = 60
    
    # Set up will message (last testament) to show this client disconnected
    client.will_set(
        f"{MQTT_TOPIC_PREFIX}system/clients/{unique_client_id}", 
        payload=json.dumps({"status": "offline"}), 
        qos=1,
        retain=True
    )
    
    # Connect to the MQTT broker
    try:
        print(f"Connecting to MQTT broker {MQTT_BROKER_URL}:{MQTT_BROKER_PORT}...")
        mqtt_connection_error = "Connection in progress"
        # Use connect instead of connect_async for initial connection to get immediate feedback
        client.connect(MQTT_BROKER_URL, MQTT_BROKER_PORT, keepalive=keepalive)
        client.loop_start()
        
        # Wait briefly to check connection status
        time.sleep(2)
        
        if not client.is_connected():
            mqtt_connection_error = "Failed to connect within initial timeout"
            print("MQTT broker connection didn't complete in expected time")
        
        # Publish that we're online
        client.publish(
            f"{MQTT_TOPIC_PREFIX}system/clients/{unique_client_id}", 
            payload=json.dumps({"status": "online"}), 
            qos=1,
            retain=True
        )
        
        # Configure automatic reconnection
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        
    except Exception as e:
        mqtt_connected = False
        mqtt_connection_error = f"Connection error: {str(e)}"
        print(f"Failed to connect to MQTT broker: {e}")
        print("Check your network connection and MQTT broker settings")

def get_mqtt_status():
    """Return current MQTT connection status information"""
    global mqtt_connected, client, mqtt_connection_error, MQTT_BROKER_URL, MQTT_BROKER_PORT
    
    status = {
        "connected": mqtt_connected,
        "broker_url": MQTT_BROKER_URL,
        "broker_port": MQTT_BROKER_PORT,
        "error_message": mqtt_connection_error if not mqtt_connected else None,
        "client_id": MQTT_CLIENT_ID
    }
    
    return status

def disconnect_mqtt():
    """Disconnect and stop MQTT client"""
    global client, mqtt_connected
    
    if client:
        try:
            # Only publish if we're actually connected
            if mqtt_connected and client.is_connected():
                # Publish offline status before disconnecting
                client.publish(
                    f"smart-home/system/clients/{MQTT_CLIENT_ID}", 
                    payload=json.dumps({"status": "offline"}), 
                    qos=1,
                    retain=True
                )
                
            client.loop_stop()
            client.disconnect()
            mqtt_connected = False
            print("MQTT client disconnected successfully")
        except Exception as e:
            print(f"Error disconnecting MQTT client: {e}")
            # Set connected to false anyway since we're shutting down
            mqtt_connected = False
