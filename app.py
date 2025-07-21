from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.secret_key = 'your_secret_key'  # Required for session management

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is not set! Please configure it in Render.")

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Debugging: Print which database is being used
print(f"📌 Database URL in use: {app.config['SQLALCHEMY_DATABASE_URI']}")

db = SQLAlchemy(app)

# Ensure the database is created before handling requests
with app.app_context():
    db.create_all()
    print("✅ Connected to PostgreSQL and initialized database!")

# Doctor locations - can be expanded or made configurable
DOCTOR_LOCATIONS = {
    "office": {
        "name": "Office - Rue de la station 57, 4890 Thimister",
        "latitude": 50.653662,
        "longitude": 5.871008
    },
    "home": {
        "name": "Home - Rue Julien Ghuysen 12, 4670 Blegny, Belgium",
        "latitude": 50.670612,
        "longitude": 5.727724
    }
}

# Default starting location (office)
DEFAULT_START_LOCATION = "office"

class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    desired_day = db.Column(db.String(20), nullable=False)
    desired_time = db.Column(db.String(50), nullable=False)
    call_time = db.Column(db.String(50), nullable=True)
    reason = db.Column(db.String(300), nullable=True)
    questions = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    seen = db.Column(db.Boolean, default=False)
    route_order = db.Column(db.Integer, nullable=True)  # NEW COLUMN for optimization order


# Haversine formula to calculate distance between two coordinates
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c  # Distance in km

# Optimize patient route using Nearest Neighbor Algorithm
def optimize_route_for_day(desired_day, start_location_key="office"):
    """Optimize route for all patients on a specific day and update their route_order"""
    try:
        start_location = DOCTOR_LOCATIONS[start_location_key]
        start_lat, start_lon = start_location["latitude"], start_location["longitude"]
        
        # Get all patients for the specific day with GPS coordinates
        patients = Patient.query.filter_by(desired_day=desired_day).filter(
            Patient.latitude.isnot(None), 
            Patient.longitude.isnot(None)
        ).all()

        if not patients:
            return []

        optimized_route = []
        remaining_patients = patients[:]
        current_location = (start_lat, start_lon)
        route_order = 1

        while remaining_patients:
            next_patient = min(remaining_patients, key=lambda p: haversine(
                current_location[0], current_location[1], p.latitude, p.longitude
            ))

            next_patient.route_order = route_order
            optimized_route.append(next_patient)
            remaining_patients.remove(next_patient)
            current_location = (next_patient.latitude, next_patient.longitude)
            route_order += 1

        # Reset route_order for patients without GPS coordinates
        patients_without_gps = Patient.query.filter_by(desired_day=desired_day).filter(
            Patient.latitude.is_(None)
        ).all()
        
        for patient in patients_without_gps:
            patient.route_order = None

        # Commit changes to database
        db.session.commit()
        
        return optimized_route

    except Exception as e:
        print(f"❌ Error optimizing route: {e}")
        return []

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        code = request.form.get('code')
        if code == '1234':  # Hardcoded code for simplicity
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return "Invalid code", 401
    return render_template('login.html')

# initiate DB
@app.route("/init-db")
def init_db_route():
    import init_db  # this runs your init_db.py script
    return "✅ Database initialized!"

# Logout route
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Protect the home route
@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('frontend.html')

# Get doctor locations
@app.route('/api/doctor-locations', methods=['GET'])
def get_doctor_locations():
    return jsonify(DOCTOR_LOCATIONS)

# Add a patient and automatically optimize route for that day
@app.route('/api/patients', methods=['POST'])
def add_patient():
    try:
        data = request.json

        # Ensure all required fields exist
        required_fields = ["name", "address", "desired_day", "desired_time"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        # Debugging: Log received data
        print("Received patient data:", data)

        new_patient = Patient(
            name=data['name'],
            address=data['address'],
            latitude=data.get('latitude', None),
            longitude=data.get('longitude', None),
            desired_day=data['desired_day'],
            desired_time=data['desired_time'],
            call_time=data.get('call_time', ''),
            reason=data.get('reason', ''),
            questions=data.get('questions', ''),
            phone=data.get('phone', '')
        )

        db.session.add(new_patient)
        db.session.commit()

        # Automatically optimize route for this day
        start_location = data.get('start_location', DEFAULT_START_LOCATION)
        optimize_route_for_day(data['desired_day'], start_location)

        return jsonify({"message": "Patient added successfully and route optimized"}), 201

    except Exception as e:
        print(f"❌ Error adding patient: {e}")
        return jsonify({"error": str(e)}), 500

# Manually optimize route for a specific day
@app.route('/api/optimize-route', methods=['POST'])
def optimize_route_manual():
    try:
        data = request.json
        desired_day = data.get('desired_day')
        start_location = data.get('start_location', DEFAULT_START_LOCATION)
        
        if not desired_day:
            return jsonify({"error": "desired_day is required"}), 400
            
        if start_location not in DOCTOR_LOCATIONS:
            return jsonify({"error": "Invalid start_location"}), 400

        optimized_patients = optimize_route_for_day(desired_day, start_location)
        
        return jsonify({
            "message": f"Route optimized for {desired_day}",
            "optimized_count": len(optimized_patients),
            "start_location": DOCTOR_LOCATIONS[start_location]["name"]
        }), 200

    except Exception as e:
        print(f"❌ Error optimizing route: {e}")
        return jsonify({"error": str(e)}), 500

# Fetch patients for a specific day (now includes route_order)
@app.route('/api/patients', methods=['GET'])
def get_patients():
    try:
        day_filter = request.args.get('desired_day', None)
        sort_by = request.args.get('sort_by', 'route_order')  # Default sort by route optimization

        if day_filter:
            patients = Patient.query.filter_by(desired_day=day_filter).all()
        else:
            patients = Patient.query.all()

        # Sort patients based on the requested parameter
        if sort_by == 'route_order':
            # Sort by route_order (optimized route), then by desired_time for those without route_order
            patients.sort(key=lambda p: (p.route_order is None, p.route_order or 999, p.desired_time))
        elif sort_by == 'desired_time':
            patients.sort(key=lambda p: p.desired_time)
        elif sort_by == 'address':
            patients.sort(key=lambda p: p.address)

        return jsonify([
            {
                "id": p.id,
                "name": p.name,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "desired_day": p.desired_day,
                "desired_time": p.desired_time,
                "call_time": p.call_time,
                "reason": p.reason,
                "questions": p.questions,
                "phone": p.phone,
                "seen": p.seen,
                "route_order": p.route_order  # Include route optimization order
            }
            for p in patients
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Update patient details
@app.route('/api/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    try:
        data = request.json
        patient = Patient.query.get(patient_id)

        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        # Update fields if provided
        patient.call_time = data.get('call_time', patient.call_time)
        patient.reason = data.get('reason', patient.reason)
        patient.questions = data.get('questions', patient.questions)
        patient.phone = data.get('phone', patient.phone)

        db.session.commit()
        return jsonify({"message": "Patient details updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Seen functionality
@app.route('/api/patients/<int:patient_id>/seen', methods=['PUT'])
def toggle_patient_seen(patient_id):
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        patient.seen = not patient.seen  # Toggle seen status
        db.session.commit()

        return jsonify({"message": "Patient seen status updated", "seen": patient.seen}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
