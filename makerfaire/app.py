from datetime import datetime
from flask import Flask
from flask import Response
from flask import render_template
from flask import url_for
from flask import redirect
from flask import request
from flask import current_app
from flask_wtf import Form
from functools import wraps
import re
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String

from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from twilio import twiml
from twilio.util import RequestValidator
from urlobject import URLObject
from wtforms import StringField
from wtforms_components import DateRange
from wtforms_components import DateTimeField
from wtforms.validators import DataRequired


WINNER_COPY = """ WINNER! WINNER! CHICKEN DINNER!"""
LOSER_COPY = """ NEXT TIME, USE THE FORCE! """

# Application

app = Flask(__name__, static_url_path='/static')
app.config.from_pyfile('local_settings.py')

# Database

engine = create_engine('sqlite:////tmp/makerfaire.db', convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


# Models

class PhoneNumber(Base):
    __tablename__ = 'PhoneNumber'
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(32), unique=True)
    raffle_numbers = relationship("PhoneNumberRaffleNumber",
                                  backref="phone_number")
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    def __init__(self, phone_number, created_at, updated_at):
        self.phone_number = phone_number
        self.created_at = created_at
        self.updated_at = updated_at

    def __repr__(self):
        return '<Phone Number %r>' % (self.phone_number)


class PhoneNumberRaffleNumber(Base):
    __tablename__ = 'PhoneNumberRaffleNumber'
    id = Column(Integer, primary_key=True)
    raffle_number = Column(String(8), unique=True)
    phone_number_id = Column(Integer, ForeignKey('PhoneNumber.id'))
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class RaffleWinner(Base):
    __tablename__ = 'RaffleWinner'
    id = Column(Integer, primary_key=True)
    raffle_number = Column(String(8), unique=True)
    raffle_time = Column(DateTime)
    item = Column(String(256))
    is_claimed = Column(Boolean)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)

    def __init__(self, raffle_number=None, raffle_time=None, item=None,
                 is_claimed=None, created_at=None, updated_at=None):
        self.raffle_number = raffle_number
        self.raffle_time = raffle_time
        self.item = item
        self.is_claimed = is_claimed
        self.updated_at = updated_at
        self.created_at = created_at

    def __repr__(self):
        return '<Raffle Winner %r>' % (self.raffle_number)


# Views
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
# @twilio_secure
def check_raffle():
    response = twiml.Response()
    response_msg = ""
    try:
        sms_body = request.values.get('Body', None)
        if sms_body:
            searches = re.search(r'^[0-9]{4,5}$', sms_body.strip())
            if searches:
                raffle_number = searches.group()
                sms_from = request.values.get('From', None)

                if sms_from:
                    # retrieve phone number
                    number = PhoneNumber.query.filter(PhoneNumber.phone_number == sms_from.strip()).first()

                    # if number found
                    if number:
                        found_number = [num for num in number.raffle_numbers if num.raffle_number == raffle_number]
                        if found_number:
                            response_msg = "You've already submitted this number."
                            response.sms(response_msg)
                            return str(response)
                        else:
                            phone_number_raffle_number = PhoneNumberRaffleNumber(raffle_number=raffle_number, phone_number_id=number.id, updated_at=datetime.utcnow(), created_at=datetime.utcnow())
                            number.raffle_numbers.append(phone_number_raffle_number)
                            db_session.add(number)
                            db_session.commit()
                    else:
                        # save from and number
                        phone_number = PhoneNumber(sms_from.strip(),
                                datetime.utcnow(), datetime.utcnow())
                        phone_number_raffle_number = PhoneNumberRaffleNumber(raffle_number=raffle_number,
                                updated_at=datetime.utcnow(),
                                created_at=datetime.utcnow())
                        phone_number.raffle_numbers.append(phone_number_raffle_number)
                        db_session.add(phone_number)
                        db_session.commit()

                    winner = RaffleWinner.query.filter(RaffleWinner.raffle_number == raffle_number).first()
                    response_msg = WINNER_COPY if winner else LOSER_COPY
                else:
                    return
            else:
                response_msg = "Please submit a valid raffle number!"
        else:
            response_msg = "Please submit a valid raffle number!"
    except Exception as e:
        print e
    response.sms(response_msg)
    return str(response)


# add_raffle_winner
@app.route('/raffle_winners/add', methods=['GET', 'POST'])
def add_raffle_winner():
    form = RaffleWinnerForm()

    if form.validate_on_submit():
        raffle_winner = RaffleWinner()
        form.populate_obj(raffle_winner)
        raffle_winner.is_claimed = False
        raffle_winner.updated_at = datetime.utcnow()
        raffle_winner.created_at = datetime.utcnow()
        db_session.add(raffle_winner)
        db_session.commit()
        return redirect('/')

    return render_template('add_raffle_winner.html', form=form)


# default view
@app.route('/', methods=['GET'])
def show_raffle_numbers():
    unclaimed_raffle_winners = RaffleWinner.\
        query.filter(RaffleWinner.is_claimed == False)
    return render_template('slash.html',
                           unclaimed_raffle_winners=unclaimed_raffle_winners)


# shutdown database
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


def init_db():
    Base.metadata.create_all(engine)


# forms
class RaffleWinnerForm(Form):
    raffle_time = DateTimeField(
        'raffle_time',
        validators=[DateRange(
            min=datetime(2015, 5, 14),
            max=datetime(2015, 5, 16)
        )]
    )
    raffle_number = StringField('raffle_number', validators=[DataRequired()])
    item = StringField('item', validators=[DataRequired()])


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
