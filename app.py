from flask import Flask, render_template, request, session, send_file
from flask_session import Session
from tempfile import mkdtemp, mkstemp, NamedTemporaryFile
from helpers import login_required
import csv
import os
import threading
import time

# Create Flask Application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Home Directory
@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/<form_id>/dashboard")
@login_required
def dashboard(form_id):
    return render_template("dashboard.html", form_id=form_id)

@app.route("/<form_id>/export")
@login_required
def export(form_id):
    return render_template("export.html", form_id=form_id)

@app.route("/<form_id>/exportfile")
@login_required
def exportfile(form_id):

    fname = f'tmp/data{os.urandom(16).hex()}.csv'
    file = open(fname, 'w')

    writer = csv.writer(file)
    writer.writerow([1,2,3, "DataPoint"])
    file.close()

    def thread():
        time.sleep(5)
        os.remove(fname)

    t = threading.Thread(target=thread)
    t.start()

    return send_file(fname)
    

# Run The Application
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)