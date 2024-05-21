from functools import wraps
from flask import Flask, render_template, request, session, send_file, redirect
from flask_session import Session
from database_helper import Database
from errors import error

DATABASE = Database()

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        session['last_visited'] = request.base_url
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def check_access(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not DATABASE.has_read_access(kwargs['form_id'], session['user_id']):
            return error('No Access')
        return f(*args, **kwargs)
    return decorated_function