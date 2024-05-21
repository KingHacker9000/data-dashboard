from flask import render_template, session

def error(s, code=''):

    return render_template("error.html", error_message=s, error_code=code)


class AppError(Exception):

    def __init__(self, message, code='') -> None:
        self.message = message
        self.code = code
    
    def render(self) -> str:
        return render_template("error.html", error_message=self.message, error_code=self.code, photo_uri=session['photo_uri'])