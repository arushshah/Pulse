from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, redirect, request
from bson.objectid import ObjectId
from passlib.hash import bcrypt
from pymongo import MongoClient

import pymongo

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

client = MongoClient()
db = client.test_db

users = db.users

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated() and current_user.is_active():
        return redirect('/')

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
        users.insert(user)
        
        return redirect('/login')
    
    return render_template('register.html')

def hashPassword(password):
    return bcrypt.encrypt(password)

if __name__ == '__main__':
    app.run(debug=True)