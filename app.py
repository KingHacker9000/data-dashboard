from flask import Flask, render_template, request, session, send_file, redirect
from flask_session import Session
from tempfile import mkdtemp
from helpers import login_required, error
import csv
import os
import threading
import time
import requests
from pip._vendor import cachecontrol
import pathlib

from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests

import pandas as pd

from database_helper import Database

import datetime
from io import BytesIO
import base64
import imghdr

# Create Flask Application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

GOOGLE_CLIENT_ID = '1057751202385-pj5q05o3kobbsbujjg15lnt9iim0ps11.apps.googleusercontent.com'
app.secret_key = os.environ['client_secret']

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # to allow Http traffic for local dev

client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)


DATABASE = Database()


# Home Directory
@app.route("/")
def index():
    session['last_visited'] = '/'
    return render_template("index.html")


@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        return error('Login Error')

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    print(id_info.get("email"), id_info.get('picture'), id_info.get("name"), id_info.get("sub"))

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    user = DATABASE.get_user_id(id_info.get("sub"))
    if user is None:
        DATABASE.sign_up_user(id_info.get("sub"), id_info.get('picture'), id_info.get("email"), id_info.get("name"))
        user = DATABASE.get_user_id(id_info.get("sub"))
    session["user_id"] = user
    session['photo_uri'] = id_info.get('picture')

    return redirect(session['last_visited'] if 'last_visited' in session else '/')


@app.route("/<form_id>/dashboard")
@login_required
def dashboard(form_id):
    session['last_visited'] = f'/{form_id}/dashboard'

    qns, res = DATABASE.get_all_responses(form_id, session['user_id'])

    form_name = DATABASE.get_form_name(form_id)

    return render_template("dashboard.html", form_id=form_id, site_url='http://127.0.0.1:5000', photo_uri=session['photo_uri'],
                           form_name=form_name, questions=qns, responses=res)


@app.route("/<form_id>/<submission_id>")
@login_required
def view_entry(form_id, submission_id):
    session['last_visited'] = f'/{form_id}/{submission_id}'

    qns, res, sub_details = DATABASE.get_response(form_id, session['user_id'], submission_id)
    form_name = DATABASE.get_form_name(form_id)

    return render_template("entry.html", form_id=form_id, site_url='http://127.0.0.1:5000', photo_uri=session['photo_uri'],
                           form_name=form_name, questions=qns, response=res, submission_details=sub_details)


@app.route("/<form_id>/image/<answer_id>")
@login_required
def get_image(form_id, answer_id):
    session['last_visited'] = f'/{form_id}/image/{answer_id}'
    
    # Decode the base64 string
    image_str = DATABASE.get_image(session['user_id'], form_id, answer_id)
    
    # Convert the bytes to a BytesIO object
    image_data = base64.b64decode(image_str)
    image = BytesIO(image_data)
    image_type = imghdr.what(None, h=image_data)

    # Send the image as a response
    return send_file(image, mimetype=f'image/{image_type}')


@app.route("/<form_id>/export")
@login_required
def export(form_id):
    session['last_visited'] = f'/{form_id}/export'
    return render_template("export.html", form_id=form_id)

@app.route("/<form_id>/exportfile")
@login_required
def exportfile(form_id):

    qns, res = DATABASE.get_all_responses(form_id, session['user_id'])

    form_name = DATABASE.get_form_name(form_id)

    fname = f'tmp/{session["user_id"]}-{form_name}.csv'
    file = open(fname, 'w', newline='')

    writer = csv.writer(file)
    writer.writerow(qns)

    for row in res:
        answers = []
        for answer in row['answers']:
            if not isinstance(answer, str) and 'value' in answer:
                if answer['type'] == 'text':
                    answers.append(answer['value'])
                elif answer['type'] == 'image':
                    url = 'http://127.0.0.1:5000/'
                    answers.append(f"{url}{form_id}/image/{answer['answer_id']}")
            else:
                answers.append('')
        writer.writerow(answers)

    file.close()

    file_out = f'tmp/{session["user_id"]}-{form_name}.xlsx'

    df = pd.read_csv(fname)
    df.to_excel(file_out, index=False)


    def thread():
        time.sleep(15)
        os.remove(fname)
        os.remove(file_out)

    t = threading.Thread(target=thread)
    t.start()

    return send_file(file_out)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/<form_id>/form", methods=['POST', 'GET'])
@login_required
def answer_form(form_id):
    
    if request.method == 'GET':

        form_name = DATABASE.get_form_name(form_id)

        questions = DATABASE.get_questions(form_id, session['user_id'])
        session['last_visited'] = f'/{form_id}/form'

        if not questions:
            return error('Form Does Not Exist or No Access')
        return render_template('form.html', questions=questions, form_name=form_name, form_id=form_id, photo_uri=session['photo_uri'])
    
    print('FILES:', request.files['26'])
    DATABASE.submit_form(int(form_id), session['user_id'], request.form, request.files)

    return render_template('form_submitted.html', photo_uri=session['photo_uri'])


# Run The Application
if __name__ == "__main__":
    app.run(host="0.0.0.0")