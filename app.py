import os
import pathlib
import re

import requests
from flask import Flask, session, abort, redirect, request, render_template
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import json

f = open('client_secret.json')
data = json.load(f)

app = Flask(__name__)
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

    return wrapper


@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)
    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    return redirect("/home")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/")
def index():
    return "Hello World <a href='/login'><button>Login</button></a>"

@app.route("/home")
@login_is_required
def protected_area():
    return render_template("index.html")

    # return f"Hello {session['name']}! <br/> <a href='/logout'><button>Logout</button></a>"


@app.route("/models")
def models():
    return render_template("models.html")

@app.route("/models/hf")
def hf():
    return render_template("huggingface.html")

def check_hf_value(model, token):
    if token == '':
        API_TOKEN = 'hf_'
    else:
        API_TOKEN = token
    API_URL = 'https://api-inference.huggingface.co/models/{}'.format(str(model).lower())
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = requests.request("GET", API_URL, headers=headers, data=data)
    output = json.loads(response.content.decode("utf-8"))
    if 'error' in output:
        return output['error']
    return output['id']

@app.route("/models/hf/result", methods= ['POST', 'GET'])
def hf_result():
    model = request.form.get('model')
    token = request.form.get('token')
    result = check_hf_value(model, token)
    return render_template("hf_result.html", result=result)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)
