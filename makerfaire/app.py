from database import db_session

from flask import Flask
from flask import Response
from flask import render_template
from flask import url_for
from flask import request
from flask import current_app
from flask_admin import Admin
from flask_admin import BaseView
from flask_admin import expose
from flask_admin.contrib.sqla import ModelView

from functools import wraps

from models import PhoneNumber
from models import RaffleNumber

import re

from twilio import twiml
from twilio.util import TwilioCapability
from twilio.util import RequestValidator
from urlobject import URLObject

# Declare and configure application
app = Flask(__name__, static_url_path='/static')
app.config.from_pyfile('local_settings.py')

def twilio_secure(func):
    """Wrap a view function to ensure that every request comes from Twilio."""
    @wraps(func)
    def wrapper(*a, **kw):
        if validate_twilio_request():
            return func(*a, **kw)
        return Response("Not a valid Twilio request", status=403)
    return wrapper


# raffle_check
@app.route('/raffle_check', methods=['GET', 'POST'])
@twilio_secure
def check_raffle():
    response = twiml.Response()
    try:
        sms_from = request.values.get('From', None)
        sms_body = request.values.get('Body', None)
    except:
        pass
    return str(response)


# default view
@app.route('/', methods=['GET'])
def show_raffle_numbers():
    return render_template('slash.html')


class RaffleView(BaseView):

    @expose('/')
    def index(self):
        return self.render('admin_index.html')

    @expose('/raffle', methods=['GET'])
    def add_raffle_view():
        return render_template('admin_add_raffle.html')

    @expose('/raffle', methods=['POST'])
    def add_raffle_action():
        pass


def validate_twilio_request():
    """Ensure a request is coming from Twilio by checking the signature."""
    validator = RequestValidator(current_app.config['TWILIO_AUTH_TOKEN'])
    if 'X-Twilio-Signature' not in request.headers:
        return False
    signature = request.headers['X-Twilio-Signature']
    if 'CallSid' in request.form:
        # See: http://www.twilio.com/docs/security#notes
        url = URLObject(url_for('.voice', _external=True)).without_auth()
        if request.is_secure:
            url = url.without_port()
    elif 'SmsSid' in request.form:
        url = url_for('.sms', _external=True)
    else:
        return False
    return validator.validate(url, request.form, signature.encode('UTF-8'))


admin = Admin(app)
admin.add_view(RaffleView(name="Raffle"))
