# Smart Home IoT Mobile App - Backend

This is the backend service for the Smart Home IoT Mobile App, providing APIs for device control, user authentication, and MQTT integration.

## Setup Instructions

### Prerequisites

- Python 3.8+ installed
- A MQTT broker (e.g., Mosquitto) for device communication (optional, but recommended)
- SQLite (included with Python)

### Installation Steps

1. Clone the repository:
   ```
   git clone <repository-url>
   cd SMART-HOME-IOT-MOBILE-APP/backend
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Configure environment variables (optional):
   Create a `.env` file in the backend directory with:
   ```
   SECRET_KEY=your_secret_key
   MQTT_BROKER_URL=localhost
   MQTT_BROKER_PORT=1883
   MQTT_USERNAME=your_username  # if required
   MQTT_PASSWORD=your_password  # if required
   ```

6. Generate sample data (optional):
   ```
   python generate_data.py
   ```

### Starting the Server

1. Ensure your virtual environment is activated
2. Run the Flask application:
   ```
   python app.py
   ```
3. The server will start on http://0.0.0.0:5000

## API Endpoints

### Authentication
- POST `/auth/register` - Register a new user
- POST `/auth/login` - Log in and get a JWT token
- GET `/auth/user` - Get current user info (requires auth)

### Rooms
- GET `/api/rooms` - Get all rooms for current user

### Devices
- GET `/api/devices` - Get all devices for current user
- POST `/api/devices` - Add a new device
- PUT `/api/devices/<id>` - Update device
- POST `/api/devices/<id>/toggle` - Toggle device on/off
- POST `/api/devices/<id>/control` - Control device with parameters
- DELETE `/api/devices/<id>` - Delete device

### Sensors
- GET `/api/sensor_data` - Get sensor data
- GET `/api/advanced_sensor_data` - Get sensor data grouped by rooms

### System
- GET `/api/mqtt_status` - Get MQTT connection status
- GET `/api/device_status` - Get overall device status dashboard data

## MQTT Integration

The system connects to an MQTT broker for real-time device control. Each device has topics:
- `smart-home/devices/<id>/status` - Device status updates
- `smart-home/devices/<id>/control` - Control messages for device

## Database

The system uses SQLite with the following data models:
- User - User accounts with authentication
- Room - Rooms containing devices
- Device - IoT devices with status and values
- DeviceHistory - History of device states

## Troubleshooting

1. MQTT Connection Issues:
   - Check if MQTT broker is running
   - Verify credentials in .env file
   - Check firewall settings

2. Database Issues:
   - If database is locked, ensure no other process is using it
   - Try regenerating data with `generate_data.py`

3. API Permission Issues:
   - Ensure you're using a valid JWT token
   - Check user permissions for the resource

## Project Structure

- `app.py` - Main application entry point
- `models.py` - Database models
- `routes.py` - API routes and controllers
- `auth_routes.py` - Authentication routes
- `mqtt_client.py` - MQTT integration
- `config.py` - Application configuration
- `generate_data.py` - Sample data generation
- `requirements.txt` - Package dependencies
