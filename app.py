from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure CORS
CORS(app, resources={
    r"/api/*": {
        "origins": os.getenv('ALLOWED_ORIGINS', '*'),
        "methods": ["GET", "POST", "PUT"],
        "allow_headers": ["Content-Type"]
    }
})

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Ensure the database is created before handling requests
with app.app_context():
    db.create_all()
    print("✅ Connected to PostgreSQL and initialized database!")



# Define Starting Location for Optimization
START_LAT, START_LON = 50.653618, 5.870655  

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
    seen = db.Column(db.Boolean, default=False)  # NEW COLUMN


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
def optimize_route(patients, start_lat=START_LAT, start_lon=START_LON):
    if not patients:
        return []

    optimized_route = []
    remaining_patients = patients[:]
    current_location = (start_lat, start_lon)

    while remaining_patients:
        next_patient = min(remaining_patients, key=lambda p: haversine(
            current_location[0], current_location[1], p.latitude, p.longitude
        ))

        optimized_route.append(next_patient)
        remaining_patients.remove(next_patient)
        current_location = (next_patient.latitude, next_patient.longitude)

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
    return render_template('frontend.html')

# Add a patient and return updated list in optimized order
@app.route('/api/patients', methods=['POST'])
def add_patient():
    try:
        data = request.json

        # Ensure all required fields exist
        required_fields = ["name", "address", "desired_day", "desired_time"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400  # Return HTTP 400 Bad Request

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

        return jsonify({"message": "Patient added successfully"}), 201  # Return HTTP 201 Created
    except Exception as e:
        print(f"❌ Error adding patient: {e}")  # Log error for debugging
        return jsonify({"error": str(e)}), 500  # Return HTTP 500 Internal Server Error

# Fetch optimized patient list for a specific day
@app.route('/api/patients', methods=['GET'])
def get_patients():
    try:
        day_filter = request.args.get('desired_day', None)

        if day_filter:
            patients = Patient.query.filter_by(desired_day=day_filter).all()
        else:
            patients = Patient.query.all()

        # Filter out patients without GPS coordinates
        patients_with_coordinates = [p for p in patients if p.latitude and p.longitude]

        # Optimize the order
        optimized_patients = optimize_route(patients_with_coordinates)

        # Combine optimized patients with those missing GPS coordinates
        final_list = optimized_patients + [p for p in patients if not (p.latitude and p.longitude)]

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
                "seen": p.seen  # Include seen status in response
            }
            for p in final_list
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
    port = int(os.environ.get('PORT', 5000))  # Get PORT from Render or default to 5000
    app.run(host='0.0.0.0', port=port)
