from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS  # Import CORS to handle cross-origin requests
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS globally

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///patients.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Patient(db.Model):
    __tablename__ = 'patients'  # Explicitly define table name

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    desired_time = db.Column(db.String(50), nullable=False)

# Serve frontend.html when accessing the root URL
@app.route('/')
def home():
    return render_template('frontend.html')

# Add a patient
@app.route('/api/patients', methods=['POST'])
def add_patient():
    try:
        data = request.json
        if not all(key in data for key in ('name', 'address', 'desired_time')):
            return jsonify({"error": "Missing fields"}), 400
        
        new_patient = Patient(name=data['name'], address=data['address'], desired_time=data['desired_time'])
        db.session.add(new_patient)
        db.session.commit()
        return jsonify({"message": "Patient added"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Fetch patients with optional sorting
@app.route('/api/patients', methods=['GET'])
def get_patients():
    try:
        sort_by = request.args.get('sort_by', 'id')  # Default sorting by ID
        if sort_by not in ['id', 'name', 'address', 'desired_time']:
            return jsonify({"error": "Invalid sort parameter"}), 400

        patients = Patient.query.order_by(getattr(Patient, sort_by)).all()
        return jsonify([{"name": p.name, "address": p.address, "desired_time": p.desired_time} for p in patients])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure the database exists before running the app
    with app.app_context():
        db.create_all()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
