import os
import pathlib
import re

import requests
from flask import Flask, session, abort, redirect, request, render_template, url_for, flash, get_flashed_messages
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime

from sqlalchemy.sql import func
import datetime

basedir = os.path.abspath(os.path.dirname(__file__))


f = open('client_secret.json')
data = json.load(f)

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] =\
        'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


app.secret_key = data['web']['client_secret']
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = data['web']['client_id']
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://localhost/callback"
)

def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Authorization required
        else:
            return function()
    wrapper.__name__ = function.__name__
    return wrapper

@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)
    try:
        if not session["state"] == request.args["state"]:
            # abort(500)  # State does not match!
            return redirect("/logout")
    except:
        return redirect("/logout")



    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )
    add_session_login(id_info.get('given_name'),id_info.get('family_name'),id_info.get('sub'))

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    return redirect("/home")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

class LoginSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    google_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=func.now())
    def __repr__(self):
        return f'<LoginSession {self.firstname}>'

class HuggingFaceModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=func.now())
    def __repr__(self):
        return f'<HuggingFaceModel {self.model}>'

class ProjectInputs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), nullable=False)
    input_name = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    input_type = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=func.now())
    def __repr__(self):
        return f'<ProjectInputs {self.model}>'

@app.route("/")
def index():
    return "Hello World <a href='/login'><button>Login</button></a>"

@app.route("/home")
@login_is_required
def protected_area():
    first_name = session['name'].split(" ")[0]
    num_models = get_num_models(session['google_id'])
    return render_template(
        "index.html", 
        name=first_name, 
        num_models=num_models
    )

    # return f"Hello {session['name']}! <br/> <a href='/logout'><button>Logout</button></a>"

@app.route("/models")
@login_is_required
def models():
    return render_template("models.html")

@app.route("/projects", methods= ['POST', 'GET'])
@login_is_required
def projects():
    google_id = session["google_id"]
    model_list = get_model_list(google_id)
    json_model_list = json.dumps([x.model for x in model_list])
            
    return render_template("projects.html", models=model_list, json_models=json_model_list)

@app.route("/projects/test", methods=['POST','GET'])
@login_is_required
def projects_test():
    if request.method == 'POST':
        results = []
        counter = 0
        while True:
            input_name = request.form.get('inputName' + str(counter))
            input_type = request.form.get('selectInput' + str(counter))
            model = request.form.get('selectModel' + str(counter))
            source = request.form.get('selectSource' + str(counter))
            if input_name == None:
                break
            else:
                temp_out = [input_name, model, input_type, source]
                results.append(temp_out)
                counter += 1
        print(results)
        # for result in results:
        #     add_project_row(result[0], result[1], result[2], result[3])
    return render_template("test.html")

def check_hf_value(model, token, google_id):
    # if token == '':
    #     API_TOKEN = 'hf_'
    # else:
    #     API_TOKEN = token
    API_TOKEN = token
    API_URL = 'https://api-inference.huggingface.co/models/{}'.format(str(model).lower())
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = requests.request("GET", API_URL, headers=headers)
    output = json.loads(response.content.decode("utf-8"))
    model_exists = check_model_exists(model, google_id)
    if 'error' in output:
        return [0, output['error']]
    elif model_exists:
        return [1, "Model already added"]
    else:
        add_hf_model(model, token, google_id)
        return [2, "Model added"]

def add_hf_model(model, token, google_id):
    if token == '':
        hf_model_row = HuggingFaceModel(
        google_id=google_id,
        model=model,
        )
    else:
        hf_model_row = HuggingFaceModel(
        google_id=google_id,
        model=model,
        token=token
        )
    db.session.add(hf_model_row)
    db.session.commit()

def add_session_login(firstname, lastname, google_id):
    session_login_row = LoginSession(
        firstname=firstname, 
        lastname=lastname,
        google_id=google_id
        )
    db.session.add(session_login_row)
    db.session.commit()

def add_project_inputs(input_name, model, input_type, source):
    project_inputs = ProjectInputs(
        google_id=session["google_id"], 
        input_name=input_name,
        model=model,
        input_type=input_type,
        source=source
        )
    db.session.add(project_inputs)
    db.session.commit()


def check_model_exists(model, google_id):
    model_exists = HuggingFaceModel.query.filter_by(
        google_id=google_id, 
        model=model
        )
    if len(list(model_exists)) > 0:
        return True
    return False

def get_model_list(google_id):
    models_query = HuggingFaceModel.query.filter_by(google_id=google_id)
    models_list = list(models_query)
    return models_list

def get_num_models(google_id):
    models_query = get_model_list(google_id)
    num_models = len(models_query)
    return num_models

@app.route("/huggingface", methods= ['POST', 'GET'])
@login_is_required
def hf_result():
    if request.method == 'POST':
        model = request.form.get('model')
        token = request.form.get('token')
        google_id = session["google_id"]
        result_code, result_message = check_hf_value(model, token, google_id)
        if result_code <= 1:
            flash('Error: {}'.format(result_message), 'error')
        else:
            flash('Success: {}'.format(result_message), 'success')
            return redirect('home')
        return redirect('huggingface')
    return render_template('huggingface.html')
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)

