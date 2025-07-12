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

# Doctor's addresses (can be managed through an admin interface later)
DOCTORS = {
    "doctor1": {"name": "Doctor 1", "address": "Rue de l'Université 1, 4000 Liège", "latitude": 50.653618, "longitude": 5.870655},
    "doctor2": {"name": "Doctor 2", "address": "Rue Lambert Lombard 5, 4000 Liège", "latitude": 50.6425, "longitude": 5.5714}
}

# Ensure the database is created before handling requests
with app.app_context():
    db.create_all()
    print("✅ Connected to PostgreSQL and initialized database!")

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
    route_position = db.Column(db.Integer, nullable=True)  # New column for route position
    doctor_address = db.Column(db.String(50), nullable=True)  # New column for doctor's address

# Haversine formula to calculate distance between two coordinates
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c  # Distance in km

# Optimize patient route using Nearest Neighbor Algorithm and assign positions
def optimize_and_assign_positions(patients, doctor_key):
    if not patients:
        return []
    
    if doctor_key not in DOCTORS:
        doctor_key = list(DOCTORS.keys())[0]  # Default to first doctor
    
    doctor = DOCTORS[doctor_key]
    start_location = (doctor['latitude'], doctor['longitude'])
    
    optimized_route = []
    remaining_patients = [p for p in patients if p.latitude and p.longitude]
    current_location = start_location
    position = 1  # Starting position number
    
    while remaining_patients:
        next_patient = min(remaining_patients, key=lambda p: haversine(
            current_location[0], current_location[1], p.latitude, p.longitude
        ))
        
        next_patient.route_position = position
        next_patient.doctor_address = doctor_key
        optimized_route.append(next_patient)
        remaining_patients.remove(next_patient)
        current_location = (next_patient.latitude, next_patient.longitude)
        position += 1
    
    # Patients without coordinates get higher position numbers
    for patient in [p for p in patients if not (p.latitude and p.longitude)]:
        patient.route_position = position
        patient.doctor_address = doctor_key
        optimized_route.append(patient)
        position += 1
    
    # Commit the position changes to database
    db.session.commit()
    
    return optimized_route

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
    return render_template('frontend.html', doctors=DOCTORS)

# Add a patient and return updated list in optimized order
@app.route('/api/patients', methods=['POST'])
def add_patient():
    try:
        data = request.json

        # Ensure all required fields exist
        required_fields = ["name", "address", "desired_day", "desired_time"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

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
            phone=data.get('phone', ''),
            doctor_address=data.get('doctor_address', list(DOCTORS.keys())[0])  # Default to first doctor
        )

        db.session.add(new_patient)
        db.session.commit()

        # After adding, optimize the route for this day and doctor
        day_filter = data['desired_day']
        doctor_key = data.get('doctor_address', list(DOCTORS.keys())[0])
        patients = Patient.query.filter_by(desired_day=day_filter, doctor_address=doctor_key).all()
        optimize_and_assign_positions(patients, doctor_key)

        return jsonify({"message": "Patient added successfully"}), 201
    except Exception as e:
        print(f"❌ Error adding patient: {e}")
        return jsonify({"error": str(e)}), 500

# Fetch optimized patient list for a specific day and doctor
@app.route('/api/patients', methods=['GET'])
def get_patients():
    try:
        day_filter = request.args.get('desired_day', None)
        doctor_key = request.args.get('doctor_address', list(DOCTORS.keys())[0])

        if doctor_key not in DOCTORS:
            doctor_key = list(DOCTORS.keys())[0]

        if day_filter:
            patients = Patient.query.filter_by(desired_day=day_filter, doctor_address=doctor_key).order_by(Patient.route_position).all()
        else:
            patients = Patient.query.filter_by(doctor_address=doctor_key).order_by(Patient.route_position).all()

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
                "route_position": p.route_position,
                "doctor_address": p.doctor_address
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
        
        # If doctor address changes, we need to re-optimize
        if 'doctor_address' in data and data['doctor_address'] != patient.doctor_address:
            patient.doctor_address = data['doctor_address']
            patients = Patient.query.filter_by(desired_day=patient.desired_day, doctor_address=patient.doctor_address).all()
            optimize_and_assign_positions(patients, patient.doctor_address)
        
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

        patient.seen = not patient.seen
        db.session.commit()

        return jsonify({"message": "Patient seen status updated", "seen": patient.seen}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Re-optimize route for a specific day and doctor
@app.route('/api/optimize-route', methods=['POST'])
def optimize_route():
    try:
        data = request.json
        day_filter = data.get('desired_day')
        doctor_key = data.get('doctor_address', list(DOCTORS.keys())[0])
        
        if not day_filter:
            return jsonify({"error": "desired_day is required"}), 400
            
        patients = Patient.query.filter_by(desired_day=day_filter, doctor_address=doctor_key).all()
        optimized_patients = optimize_and_assign_positions(patients, doctor_key)
        
        return jsonify({
            "message": f"Route optimized for {day_filter} with {len(optimized_patients)} patients",
            "doctor": DOCTORS.get(doctor_key, {}).get('name')
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
