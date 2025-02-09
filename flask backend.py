from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///patients.db'
db = SQLAlchemy(app)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    desired_time = db.Column(db.String(50), nullable=False)

@app.route('/api/patients', methods=['POST'])
def add_patient():
    data = request.json
    new_patient = Patient(name=data['name'], address=data['address'], desired_time=data['desired_time'])
    db.session.add(new_patient)
    db.session.commit()
    return jsonify({"message": "Patient added"}), 201

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)