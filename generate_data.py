import sqlite3
import os
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Database path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'smart_home.db')

# Sample data
ROOMS = [
    "Living Room",
    "Kitchen",
    "Master Bedroom",
    "Guest Bedroom",
    "Bathroom",
    "Home Office",
    "Dining Room",
    "Garage",
    "Hallway",
    "Basement"
]

DEVICE_TYPES = {
    "light": ["Ceiling Light", "Floor Lamp", "Table Lamp", "Wall Light", "LED Strip"],
    "thermostat": ["AC", "Heater", "Smart Thermostat"],
    "plug": ["TV", "Computer", "Refrigerator", "Microwave", "Washing Machine"],
    "fan": ["Ceiling Fan", "Stand Fan", "Exhaust Fan"],
    "sensor": ["Motion Sensor", "Temperature Sensor", "Humidity Sensor", "Door Sensor"]
}

# Sample users
USERS = [
    {"username": "admin", "email": "admin@example.com", "password": "adminpass"},
    {"username": "john", "email": "john@example.com", "password": "johnpass"},
    {"username": "alice", "email": "alice@example.com", "password": "alicepass"},
]

# Add a function to sanitize device type names for consistency
def sanitize_device_type(device_type):
    """Ensure device type names are consistent and valid for MQTT topics"""
    return device_type.lower().replace(' ', '_').replace('-', '_')

def create_tables(conn):
    """Create tables if they don't exist"""
    cursor = conn.cursor()
    
    # Create user table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at DATETIME NOT NULL
    )
    ''')
    
    # Create room table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS room (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        owner_id INTEGER,
        FOREIGN KEY (owner_id) REFERENCES user (id)
    )
    ''')
    
    # Create device table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS device (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        status BOOLEAN DEFAULT FALSE,
        value FLOAT DEFAULT 0,
        room_id INTEGER NOT NULL,
        FOREIGN KEY (room_id) REFERENCES room (id)
    )
    ''')
    
    # Create device history table for logging
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS device_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        status BOOLEAN,
        value FLOAT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES device (id)
    )
    ''')
    
    conn.commit()

def generate_users(conn):
    """Generate sample users"""
    cursor = conn.cursor()
    
    for user in USERS:
        # Generate password hash
        password_hash = generate_password_hash(user["password"])
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO user (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user["username"], user["email"], password_hash, created_at)
        )
    
    conn.commit()
    print(f"Created {len(USERS)} users.")

def generate_rooms(conn, count=None):
    """Generate sample rooms"""
    cursor = conn.cursor()
    
    # Get all users
    cursor.execute("SELECT id FROM user")
    users = cursor.fetchall()
    
    # If count is not provided, use all sample rooms
    rooms_to_create = ROOMS[:count] if count else ROOMS
    
    total_rooms = 0
    
    for user_id, in users:
        # Create a subset of rooms for each user
        user_rooms = random.sample(rooms_to_create, k=random.randint(3, len(rooms_to_create)))
        
        for room_name in user_rooms:
            cursor.execute("INSERT INTO room (name, owner_id) VALUES (?, ?)", (room_name, user_id))
            total_rooms += 1
    
    conn.commit()
    print(f"Created {total_rooms} rooms across {len(users)} users.")

def generate_devices(conn, devices_per_room=(2, 6)):
    """Generate devices for each room"""
    cursor = conn.cursor()
    
    # Get all rooms
    cursor.execute("SELECT id, name FROM room")
    rooms = cursor.fetchall()
    
    total_devices = 0
    
    for room_id, room_name in rooms:
        # Random number of devices per room
        num_devices = random.randint(devices_per_room[0], devices_per_room[1])
        
        for _ in range(num_devices):
            # Choose a random device type
            device_type = random.choice(list(DEVICE_TYPES.keys()))
            
            # Choose a random device name from that type
            device_name = random.choice(DEVICE_TYPES[device_type])
            
            # For similar device types in the same room, add a number
            cursor.execute(
                "SELECT COUNT(*) FROM device WHERE room_id = ? AND name LIKE ?", 
                (room_id, f"{device_name}%")
            )
            count = cursor.fetchone()[0]
            
            if count > 0:
                device_name = f"{device_name} {count + 1}"
            
            # Generate random status and value
            status = random.choice([0, 1])
            
            # Value depends on device type
            if device_type == "thermostat":
                value = round(random.uniform(18.0, 26.0), 1)  # Temperature between 18-26°C
            elif device_type == "light" and status:
                value = random.randint(30, 100)  # Brightness level
            else:
                value = 0
            
            # Insert device
            cursor.execute(
                "INSERT INTO device (name, type, status, value, room_id) VALUES (?, ?, ?, ?, ?)",
                (device_name, device_type, status, value, room_id)
            )
            total_devices += 1
    
    conn.commit()
    print(f"Created {total_devices} devices across {len(rooms)} rooms.")

def generate_device_history(conn, days_back=7):
    """Generate device usage history"""
    cursor = conn.cursor()
    
    # Get all devices
    cursor.execute("SELECT id, type FROM device")
    devices = cursor.fetchall()
    
    total_history_entries = 0
    
    for device_id, device_type in devices:
        # Generate between 10-30 history entries per device
        num_entries = random.randint(10, 30)
        
        for _ in range(num_entries):
            # Random date within the last week
            days_ago = random.uniform(0, days_back)
            timestamp = datetime.now() - timedelta(days=days_ago)
            formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Random status
            status = random.choice([0, 1])
            
            # Value depends on device type
            if device_type == "thermostat" and status:
                value = round(random.uniform(18.0, 26.0), 1)
            elif device_type == "light" and status:
                value = random.randint(30, 100)
            else:
                value = 0
            
            # Insert history entry
            cursor.execute(
                "INSERT INTO device_history (device_id, status, value, timestamp) VALUES (?, ?, ?, ?)",
                (device_id, status, value, formatted_timestamp)
            )
            total_history_entries += 1
    
    conn.commit()
    print(f"Created {total_history_entries} history entries.")

def main():
    """Main function to generate all data"""
    global DB_PATH  # Add this line to indicate we want to modify the global DB_PATH
    
    # Check if database exists and delete if it does
    if os.path.exists(DB_PATH):
        confirm = input(f"Database at {DB_PATH} already exists. Delete and recreate? (y/n): ")
        if confirm.lower() == 'y':
            try:
                os.remove(DB_PATH)
                print("Database deleted.")
            except PermissionError:
                print(f"Error: Cannot delete database as it's being used by another process.")
                print("Options:")
                print("1. Close any applications using the database and try again")
                print("2. Create a database with a different name")
                print("3. Continue with existing database")
                
                choice = input("Enter your choice (1/2/3): ")
                
                if choice == '1':
                    print("Please close all applications using the database and press Enter to try again...")
                    input()
                    try:
                        os.remove(DB_PATH)
                        print("Database deleted.")
                    except PermissionError:
                        print("Still cannot delete database. Using existing database.")
                elif choice == '2':
                    new_name = input("Enter new database name (without .db extension): ")
                    DB_PATH = os.path.join(BASE_DIR, f"{new_name}.db")
                    print(f"Using new database path: {DB_PATH}")
                else:
                    print("Using existing database.")
        else:
            print("Using existing database.")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    # Create tables
    create_tables(conn)
    
    # Check if users already exist
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM user")
    user_count = cursor.fetchone()[0]
    
    if user_count == 0:
        # Generate users
        generate_users(conn)
        
        # Generate rooms
        generate_rooms(conn)
        
        # Generate devices
        generate_devices(conn)
        
        # Generate device history
        generate_device_history(conn)
    else:
        print(f"Database already contains {user_count} users.")
        
        # Check rooms
        cursor.execute("SELECT COUNT(*) FROM room")
        room_count = cursor.fetchone()[0]
        
        if room_count == 0:
            # Generate rooms
            generate_rooms(conn)
            
            # Generate devices
            generate_devices(conn)
            
            # Generate device history
            generate_device_history(conn)
        else:
            print(f"Database already contains {room_count} rooms.")
            
            # Option to regenerate just devices
            confirm = input("Regenerate devices and history? (y/n): ")
            if confirm.lower() == 'y':
                cursor.execute("DELETE FROM device_history")
                cursor.execute("DELETE FROM device")
                conn.commit()
                generate_devices(conn)
                generate_device_history(conn)
    
    # Close connection
    conn.close()
    print(f"Database created successfully at {DB_PATH}")

if __name__ == "__main__":
    main()