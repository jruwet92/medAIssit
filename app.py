from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS  
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  

# Database Configuration
db_path = "patients.db"
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True)  # NEW FIELD
    longitude = db.Column(db.Float, nullable=True)  # NEW FIELD
    desired_day = db.Column(db.String(20), nullable=False)
    desired_time = db.Column(db.String(50), nullable=False)
    call_time = db.Column(db.String(50), nullable=True)
    reason = db.Column(db.String(300), nullable=True)
    questions = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
 

# Ensure the database is created before handling requests
with app.app_context():
    if not os.path.exists(db_path):
        db.create_all()
        print("✅ Database initialized: patients.db")  

@app.route('/')
def home():
    return render_template('frontend.html')

# Add a patient (Updated to include `call_time`)
@app.route('/api/patients', methods=['POST'])
def add_patient():
    try:
        data = request.json
        if not all(key in data for key in ('name', 'address', 'desired_day', 'desired_time')):
            return jsonify({"error": "Missing required fields"}), 400

        new_patient = Patient(
            name=data['name'],
            address=data['address'],
            latitude=data.get('latitude', None),  # NEW FIELD
            longitude=data.get('longitude', None),  # NEW FIELD
            desired_day=data['desired_day'],
            desired_time=data['desired_time'],
            call_time=data.get('call_time', ''),
            reason=data.get('reason', ''),
            questions=data.get('questions', ''),
            phone=data.get('phone', '')
        )
        db.session.add(new_patient)
        db.session.commit()
        return jsonify({"message": "Patient added"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Fetch patients for a specific day
@app.route('/api/patients', methods=['GET'])
def get_patients():
    try:
        day_filter = request.args.get('desired_day', None)

        if day_filter:
            patients = Patient.query.filter_by(desired_day=day_filter).order_by(Patient.desired_time).all()
        else:
            patients = Patient.query.order_by(Patient.desired_day, Patient.desired_time).all()

        return jsonify([
            {
                "id": p.id,
                "name": p.name,
                "address": p.address,
                "latitude": p.latitude,  # NEW FIELD
                "longitude": p.longitude,  # NEW FIELD
                "desired_day": p.desired_day,
                "desired_time": p.desired_time,
                "call_time": p.call_time,
                "reason": p.reason,
                "questions": p.questions,
                "phone": p.phone
            }
            for p in patients
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Update a patient's details, including call time
@app.route('/api/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    try:
        data = request.json
        patient = Patient.query.get(patient_id)

        if not patient:
            return jsonify({"error": "Patient not found"}), 404
        
        # Update fields if provided
        patient.call_time = data.get('call_time', patient.call_time)  # NEW FIELD
        patient.reason = data.get('reason', patient.reason)
        patient.questions = data.get('questions', patient.questions)
        patient.phone = data.get('phone', patient.phone)

        db.session.commit()
        return jsonify({"message": "Patient details updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
