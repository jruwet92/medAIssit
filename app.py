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
    desired_day = db.Column(db.String(20), nullable=False)  # NEW FIELD
    desired_time = db.Column(db.String(50), nullable=False)

# Ensure the database is created before requests
with app.app_context():
    if not os.path.exists(db_path):
        db.create_all()
        print("✅ Database initialized: patients.db")  

@app.route('/')
def home():
    return render_template('frontend.html')

# Add a patient (Now includes desired_day)
@app.route('/api/patients', methods=['POST'])
def add_patient():
    try:
        data = request.json
        if not all(key in data for key in ('name', 'address', 'desired_day', 'desired_time')):
            return jsonify({"error": "Missing fields"}), 400
        
        new_patient = Patient(
            name=data['name'], 
            address=data['address'], 
            desired_day=data['desired_day'],  # NEW FIELD
            desired_time=data['desired_time']
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
        day_filter = request.args.get('desired_day', None)  # Get the day from the request

        if day_filter:
            patients = Patient.query.filter_by(desired_day=day_filter).order_by(Patient.desired_time).all()
        else:
            patients = Patient.query.order_by(Patient.desired_day, Patient.desired_time).all()

        return jsonify([
            {
                "name": p.name, 
                "address": p.address, 
                "desired_day": p.desired_day, 
                "desired_time": p.desired_time
            } 
            for p in patients
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
