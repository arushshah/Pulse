from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, redirect, request
from bson.objectid import ObjectId
from passlib.hash import bcrypt
from pymongo import MongoClient

import pymongo
import datetime
import requests
import json

app = Flask(__name__)
app.secret_key = 'secret'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

client = MongoClient()
db = client.test_db
users = db.users

fhir_ids = ['TSvxrNacr7Cv7KQXd2Y8lFXnKQyRbVPmWyfDobtXFBOsB', 'TU95.eyqsbwjl8jN1XdGRg5xeC6VpHyjhlJIAmBm8UcAB', 
'TVQcsPBShQNmT2M-LjXkd9OMWMUvqtjkGLjM3qohoAyUB']

headers = {'Accept' : 'application/json'}

#User Model
class User(object):
    def __init__(self, _id):
        self._id = _id
        user = users.find_one({'_id' : ObjectId(_id)})

        if (user is not None):
            user = users.find_one({'_id': ObjectId(_id)})
            self.first_name = user['first_name']
            self.last_name = user['last_name']
            self.username = user['username']
    
    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

    def get_id(self):
        return str(self._id)

@login_manager.user_loader
def load_user(_id):
    if id is None:
        redirect('/login')
    user = User(_id)
    if user.is_active():
        return user
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated() and current_user.is_active():
        return redirect('/dashboard')

    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        user = users.find_one({'username': username})

        if userAuth(user, username, password):
            login_user(User(str(user['_id'])))
            return redirect('/dashboard')
        else:
            return render_template('login.html', error='Wrong email or password.')

    return render_template('login.html')

def userAuth(user, username, password):
    if (user == None):
        return False
    return bcrypt.verify(password, user['password'])

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = {}

        #Missing Field
        if not (request.form['first_name'] and request.form['last_name'] and request.form['username'] and request.form['password'] and request.form['verify_password']):
            return render_template('register.html', error='Please fill out all fields.')
        user['first_name'] = request.form['first_name'].strip(" ")
        user['last_name'] = request.form['last_name'].strip(" ")

        #Username already exists
        if users.find_one({'username': request.form['username']}) != None:
            return render_template('register.html', error='This username is already in use.')
        user['username'] = request.form['username'].lower().strip(" ")
        
        #Password verification failed
        if not request.form['password'] == request.form['verify_password']:
            return render_template('register.html', error='Password verification failed.')

        user['password'] = hashPassword(request.form['password'])
        user['patients'] = []
        users.insert(user)
        
        return redirect('/login')
    
    return render_template('register.html')

def hashPassword(password):
    return bcrypt.encrypt(password)

@app.route('/add_symptoms')
def add_symptoms():
    return render_template('add_symptoms.html')

#View/edit details of a patient
@app.route('/view_patient/<patient_index>', methods=['GET', 'POST'])
def view_patient(patient_index):
    user_id = current_user.get_id()
    user = users.find_one({'_id': user_id})
    patient = user['patients'][patient_index]

    if request.method == 'POST':
        dob = str(request.form['dob'])[:10].split("-")
        dob_str = int(dob[1]) + '/' + int(dob[2]) + '/' + int(dob[0])
        start = datetime.date(int(dob[0]), int(dob[1]), int(dob[2]))

        age = 2015 - start.year
        if start.month < 9:
            age += 1

        users.update_one({'_id': ObjectId(user_id)}, {'$set': {'patients.' + str(patient_index): {'name': request.form['name'],
            'gender': request.form['gender'], 'dob': dob_str, 'age': age, 'address': request.form['address'],
            'phone': request.form['phone']}}})

        return redirect('/view_patient/' + str(patient_index))

    return render_template('view_patient.html', name=patient['name'], gender=patient['gender'], dob=patient['dob'],
        age=patient['age'], address=patient['address'], phone=patient['phone'], email=patient['email'])

#Doctor can view all patients and choose to add/delete
@app.route('/dashboard')
def dashboard():
    user_id = current_user.get_id()
    user = users.find_one({'_id': ObjectId(user_id)})

    patients = []
    for patient in user['patients']:
        patients.append(patient)

    for fhir_id in fhir_ids:
        patient = {}
        bio = pullFIHRPatientBio(fhir_id)
        patient['name'] = bio['name'][0]['given'][0] + ' ' + bio['name'][0]['family'][0]
        patient['gender'] = bio['gender']
        date_arr = str(bio['birthDate'])[:10].split('-')

        patient['age'] = find_age(date_arr)
        patient['dob'] = int(date_arr[1]) + '/' + int(date_arr[2]) + '/' + int(date_arr[0])
        patient['address'] = bio['address'][0]['line'][0] + ', ' + patient['address'][0]['city'] + ', ' + patient['address'][0]['state']
        patient['phone'] = bio['telecom'][0]['value']

        allergens = pullFIHRPatientAllergens(fhir_id)
        if allergens['total'] > 0:
            patient['allergens'] = []
            for info in allergens['entry']:
                patient['allergens'].append(info['resource']['AllergyIntolerance']['substance']['text'])

        meds = pullFIHRMedication(fhir_id)
        if meds['total'] > 0:
            patient['meds'] = []
            for info in meds['entry']:
                patient['meds'].append(info['resource']['MedicationPrescription']['medication']['display'])

        patients.append(patient)

    return render_template('dashboard.html', last_name=user['last_name'], patients=patients)

def pullFIHRPatientBio(patient_id):
    bio = requests.get("https://open-ic.epic.com/FHIR/api/FHIR/DSTU2/Patient/%s" % patient_id, headers=headers)
    print(bio.json())
    return bio.json()

def pullFIHRPatientAllergens(patient_id):
    allergen = requests.get("https://open-ic.epic.com/FHIR/api/FHIR/DSTU2/AllergyIntolerance?patient=%s" % patient_id, headers=headers)
    return json.loads(allergen)

def pullFIHRMedication(patient_id):
    medications = requests.get("https://open-ic.epic.com/FHIR/api/FHIR/DSTU2/MedicationPrescription?patient=%s&status=active" % patient_id, headers=headers)
    return json.loads(medications)

def find_age(array):
    start = datetime.date(int(array[0]), int(array[1]), int(array[2]))

    age = 2015 - start.year
    if start.month < 9:
        age += 1

    return age

def getWatsonTreatment(condition_name):
    question = "How to treat %s" % condition_name
    url = "https://gateway.watsonplatform.net/question-and-answer-beta/api/v1/question/healthcare"
    r = requests.post(url,
        data=json.dumps({"question": {"questionText": question, "evidenceRequest": {"items": 1}}}),
        headers={"Content-Type": "application/json", "X-SyncTimeout": 30},
        auth=("a22986ff-f437-42f4-a210-3804023208e3", "skyZSd3GAf9p"))

    return json.loads(r.text)[0]['question']['evidencelist'][0]['text']

if __name__ == '__main__':
    treatment = getWatsonTreatment('diabetes')
    print treatment
    app.run(debug=True, host='0.0.0.0', port=80)
