from functools import wraps
from flask import Flask, render_template, request, session, send_file, redirect
from flask_session import Session

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        session['last_visited'] = request.base_url
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def error(s, code=''):

    return f"ERROR {code}: {s}"