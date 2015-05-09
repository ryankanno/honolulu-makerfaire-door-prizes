from datetime import datetime
from flask import flash
from flask import Flask
from flask import Response
from flask import render_template
from flask import url_for
from flask import redirect
from flask import request
from flask import current_app
from flask_wtf import Form
from functools import wraps
from pytz import timezone
import pytz
import re
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.sql import and_
from sqlalchemy.ext.declarative import declarative_base

from twilio import twiml
from twilio.rest import TwilioRestClient
from twilio.util import RequestValidator
from urlobject import URLObject
from wtforms import StringField
from wtforms import TextAreaField
from wtforms import IntegerField
from wtforms_alchemy import ModelFieldList
from wtforms_alchemy import model_form_factory
from wtforms.fields import FormField
from wtforms_components import DateRange
from wtforms_components import DateTimeField
from wtforms.validators import DataRequired
from wtforms.validators import Optional
from wtforms.widgets import HiddenInput
from wtforms.widgets import ListWidget
from wtforms.widgets import TableWidget
from wtforms.widgets import TextInput

WINNER_COPY = """ You may have won a prize at the Honolulu Makerfaire! Please report to the prize booth immediately.\n\nPowered by hicapacity.org"""
LOSER_COPY = """ You haven't won yet, but who knows what the future holds for you at the Honolulu Makerfaire?\n\nPowered by hicapacity.org"""

# Application

app = Flask(__name__, static_url_path='/static')
app.config.from_pyfile('local_settings.py')
app.debug = app.config.get('ENVIRONMENT', None) == 'Development'


# Database

engine = create_engine('sqlite:///' + app.config.get('DATABASE'),
                       convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

BaseModelForm = model_form_factory(Form)

class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db_session



# Basic Auth

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return (username == current_app.config['HNLMAKERFAIRE_USERNAME']) and \
           (password == current_app.config['HNLMAKERFAIRE_PASSWORD'])


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response('Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# Models

class PhoneNumber(Base):
    __tablename__ = 'PhoneNumber'
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(32), unique=True, info={'label': 'Phone Number', 'validators': [DataRequired()]})
    raffle_numbers = relationship(
        'PhoneNumberRaffleNumber',
        backref='phone_number'
    )
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    def __init__(self, phone_number=None, created_at=None, updated_at=None):
        self.phone_number = phone_number
        self.created_at = created_at
        self.updated_at = updated_at

    def __repr__(self):
        return '<Phone Number %r>' % (self.phone_number)


class PhoneNumberRaffleNumber(Base):
    __tablename__ = 'PhoneNumberRaffleNumber'
    __table_args__ = (
        UniqueConstraint('raffle_number', 'phone_number_id', name='uix_1'),
    )
    id = Column(Integer, primary_key=True)
    raffle_number = Column(String(8), nullable=False, info={'label': 'Raffle Number' })
    phone_number_id = Column(Integer, ForeignKey('PhoneNumber.id'))
    num_system_notified = Column(Integer, default=0)
    num_admin_notified = Column(Integer, default=0)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


def get_hst_time():
    return datetime.now(tz=pytz.utc).astimezone(timezone('US/Hawaii')).replace(tzinfo=None)


class RaffleWinner(Base):
    __tablename__ = 'RaffleWinner'
    id = Column(Integer, primary_key=True)
    raffle_number = Column(String(8), nullable=False, unique=True, info={'label': 'Raffle Number'})
    raffle_time = Column(DateTime, nullable=False,
        info={'label':'Raffle Time',
        'widget': TextInput(),
        'min': datetime(2015, 5, 15, 0, 0, 0).replace(tzinfo=None),
        'max': datetime(2015, 5, 15, 23, 59, 59).replace(tzinfo=None)})
    item = Column(String(256), nullable=False, info={'label': 'Raffle Prize'})
    is_claimed = Column(Boolean)
    num_system_notified = Column(Integer, default=0)
    num_admin_notified = Column(Integer, default=0)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)

    def __init__(self, raffle_number=None, raffle_time=None, item=None,
                 is_claimed=False, num_system_notified=0, num_admin_notified=0, created_at=None, updated_at=None):
        self.raffle_number = raffle_number
        self.raffle_time = raffle_time
        self.item = item
        self.is_claimed = is_claimed
        self.num_system_notified = num_system_notified
        self.num_admin_notified = num_admin_notified
        self.updated_at = updated_at
        self.created_at = created_at

    def __repr__(self):
        return '<Raffle Winner %r>' % (self.raffle_number)

class Audit(Base):
    __tablename__ = 'Audit'
    id = Column(Integer, primary_key=True)
    description = Column(String(256))
    created_at = Column(DateTime)

    def __init__(self, description, created_at=None):
        self.description = description
        self.created_at = created_at or get_hst_time()

    def __repr__(self):
        return '<Audit %r>' % (self.description)


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
@twilio_secure
def check_raffle():
    response = twiml.Response()
    response_msg = ""
    try:
        sms_body = request.values.get('Body', None)
        if sms_body:
            searches = re.search(r'^[0-9]{1,4}$', sms_body.strip())
            if searches:
                raffle_number = searches.group()
                sms_from = request.values.get('From', None)

                if sms_from:
                    # retrieve phone number
                    number = PhoneNumber.query.filter(
                        PhoneNumber.phone_number == sms_from.strip()).first()

                    # if number found
                    if number:
                        found_number = [num for num in number.raffle_numbers
                                        if num.raffle_number == raffle_number]
                        if found_number:
                            response_msg = \
                                "You've already submitted this number."
                            response.sms(response_msg)
                            return str(response)
                        else:
                            phone_number_raffle_number = \
                                PhoneNumberRaffleNumber(
                                    raffle_number=raffle_number,
                                    phone_number_id=number.id,
                                    updated_at=datetime.utcnow(),
                                    created_at=datetime.utcnow())
                            number.raffle_numbers.append(
                                phone_number_raffle_number)
                            db_session.add(number)

                            audit = Audit("{0} (existing) has saved {1}".format(sms_from.strip(), raffle_number))

                            db_session.add(audit)
                            db_session.commit()
                    else:
                        # save from and number
                        phone_number = PhoneNumber(
                            sms_from.strip(),
                            datetime.utcnow(), datetime.utcnow())
                        phone_number_raffle_number = PhoneNumberRaffleNumber(
                            raffle_number=raffle_number,
                            updated_at=datetime.utcnow(),
                            created_at=datetime.utcnow())
                        phone_number.raffle_numbers.append(
                            phone_number_raffle_number)

                        audit = Audit("{0} (new) has saved {1}".format(sms_from.strip(), raffle_number))

                        db_session.add(audit)
                        db_session.add(phone_number)
                        db_session.commit()

                    winner = RaffleWinner.query.filter(
                        RaffleWinner.raffle_number == raffle_number).first()

                    if winner:
                        winner.num_system_notified += 1
                        db_session.add(winner)

                        try:
                            phone_number_raffle_number = PhoneNumberRaffleNumber.query.filter(and_(PhoneNumberRaffleNumber.raffle_number == raffle_number, PhoneNumberRaffleNumber.phone_number_id == number.id)).one()

                            if phone_number_raffle_number:
                                phone_number_raffle_number.num_system_notified += 1
                                db_session.add(phone_number_raffle_number)

                            audit = Audit("System notified {0} that they've won a prize for {1}".format(number.phone_number, raffle_number))
                            db_session.add(audit)

                        except MultipleResultsFound, e:
                            pass
                        except NoResultFound, e:
                            pass

                        db_session.commit()

                    response_msg = WINNER_COPY if winner else LOSER_COPY
                else:
                    return
            else:
                response_msg = "Please submit a valid 4-digit raffle number!"
        else:
            response_msg = "Please submit a valid 4-digit raffle number!"
    except Exception as e:
        current_app.logger.exception(e)
    response.sms(response_msg)
    return str(response)


# admin index
@app.route('/admin/', methods=['GET'])
@requires_auth
def admin_index():
    return render_template('admin/index.html')


# admin view_raffle_winners
@app.route('/admin/raffle_winners/', methods=['GET'])
@requires_auth
def admin_view_raffle_winners():
    raffle_winners = RaffleWinner.\
        query.all()
    return render_template('admin/raffle_winners/view_raffle_winners.html',
                           raffle_winners=raffle_winners)


# admin add_raffle_winner
@app.route('/admin/raffle_winners/add', methods=['GET', 'POST'])
@requires_auth
def admin_add_raffle_winner():
    form = RaffleWinnerForm()
    if request.method == 'GET':
        form.raffle_time.data = get_hst_time()
    else:
        if form.validate_on_submit():
            raffle_winner = RaffleWinner()
            form.populate_obj(raffle_winner)
            raffle_winner.is_claimed = False
            raffle_winner.updated_at = datetime.utcnow()
            raffle_winner.created_at = datetime.utcnow()

            audit = Audit("Admin has drawn number {0} for prize {1}".format(raffle_winner.raffle_number, raffle_winner.item))

            db_session.add(audit)
            db_session.add(raffle_winner)
            db_session.commit()
            return redirect(url_for('admin_view_raffle_winners'))

    return render_template('admin/raffle_winners/add_raffle_winner.html', form=form)


# admin edit_raffle_winner
@app.route('/admin/raffle_winners/<int:raffle_winner_id>/edit',
           methods=['GET', 'POST'])
@requires_auth
def admin_edit_raffle_winner(raffle_winner_id):
    raffle_winner = RaffleWinner.query.get(raffle_winner_id)
    if request.method == 'GET':
        form = RaffleWinnerForm(obj=raffle_winner)
    else:
        form = RaffleWinnerForm(obj=raffle_winner)
        if form.validate_on_submit():
            form.populate_obj(raffle_winner)
            raffle_winner.updated_at = datetime.utcnow()
            db_session.add(raffle_winner)
            db_session.commit()
            return redirect(url_for('admin_view_raffle_winners'))

    return render_template('admin/raffle_winners/edit_raffle_winner.html',
                           form=form, raffle_winner=raffle_winner)


# admin delete_raffle_winner
@app.route('/admin/raffle_winners/<int:raffle_winner_id>/delete',
           methods=['POST'])
@requires_auth
def admin_delete_raffle_winner(raffle_winner_id):
    raffle_winner = RaffleWinner.query.get(raffle_winner_id)
    db_session.delete(raffle_winner)
    db_session.commit()
    return redirect(url_for('admin_view_raffle_winners'))


# admin claim_raffle_winner
@app.route('/admin/raffle_winners/claim', methods=['POST'])
@requires_auth
def admin_claim_raffle_winner():
    _claim_unclaim_raffle_winner(True)
    return redirect(url_for('admin_view_raffle_winners'))


# admin unclaim_raffle_winner
@app.route('/admin/raffle_winners/unclaim', methods=['POST'])
@requires_auth
def admin_unclaim_raffle_winner():
    _claim_unclaim_raffle_winner(False)
    return redirect(url_for('admin_view_raffle_winners'))


def _claim_unclaim_raffle_winner(claim):
    raffle_winner_id = request.values.get('raffle_id', None)
    if raffle_winner_id:
        raffle_winner = RaffleWinner.query.get(raffle_winner_id)
        if raffle_winner:
            raffle_winner.is_claimed = claim
            db_session.add(raffle_winner)
            db_session.commit()


# admin notify_raffle_winner
@app.route('/admin/raffle_winners/notify', methods=['POST'])
@requires_auth
def admin_notify_raffle_winner():
    raffle_winner_id = request.values.get('raffle_id', None)
    if raffle_winner_id:
        raffle_winner = RaffleWinner.query.get(raffle_winner_id)
        winners = PhoneNumber.query.join(PhoneNumberRaffleNumber).filter(PhoneNumberRaffleNumber.raffle_number == raffle_winner.raffle_number).all()
        if winners:
            for winner in winners:
                _notify_via_twilio(winner.phone_number, WINNER_COPY)

                audit = Audit("Admin notified {0} that they've won a prize for claiming {1}".format(winner.phone_number, raffle_winner.raffle_number))
                db_session.add(audit)

                for raffle_number in winner.raffle_numbers:
                    if raffle_number.raffle_number == raffle_winner.raffle_number:
                        raffle_number.num_admin_notified += 1
                        db_session.add(raffle_number)

            raffle_winner.num_admin_notified += 1
            db_session.add(raffle_winner)
            db_session.commit()
        else:
            flash('No phone number has claimed this raffle number, so a notification at this time is unnecessary.')
    return redirect(url_for('admin_view_raffle_winners'))


def _notify_via_twilio(to, message):
    account_sid = current_app.config['TWILIO_ACCOUNT_SID']
    auth_token = current_app.config['TWILIO_AUTH_TOKEN']
    from_number = current_app.config['TWILIO_NUMBER']
    client = TwilioRestClient(account_sid, auth_token)
    client.messages.create(to=to, from_=from_number, body=message)


# admin view_phone_numbers
@app.route('/admin/phone_numbers', methods=['GET'])
@requires_auth
def admin_view_phone_numbers():
    phone_numbers = PhoneNumber.query.all()
    raffle_winners = RaffleWinner.query.all()
    raffle_winners_as_dict = {}
    for winner in raffle_winners:
        raffle_winners_as_dict[winner.raffle_number] = winner
    return render_template('admin/phone_numbers/view_phone_numbers.html',
                           phone_numbers=phone_numbers,
                           raffle_winners=raffle_winners_as_dict)


# admin add_phone_number
@app.route('/admin/phone_numbers/add', methods=['GET', 'POST'])
@requires_auth
def admin_add_phone_number():
    form = PhoneNumberForm()

    if form.validate_on_submit():
        phone_number = PhoneNumber()
        form.populate_obj(phone_number)
        phone_number.updated_at = datetime.utcnow()
        phone_number.created_at = datetime.utcnow()
        db_session.add(phone_number)
        db_session.commit()
        return redirect(url_for('admin_view_phone_numbers'))

    return render_template('admin/phone_numbers/add_phone_number.html', form=form)


# admin edit_phone_number
@app.route('/admin/phone_numbers/<int:phone_number_id>/edit',
           methods=['GET', 'POST'])
@requires_auth
def admin_edit_phone_number(phone_number_id):
    phone_number = PhoneNumber.query.get(phone_number_id)
    if request.method == 'GET':
        form = PhoneNumberForm(obj=phone_number)
    else:
        form = PhoneNumberForm(obj=phone_number)
        if form.validate_on_submit():
            form.populate_obj(phone_number)
            phone_number.updated_at = datetime.utcnow()
            db_session.add(phone_number)
            db_session.commit()
            return redirect(url_for('admin_view_phone_numbers'))

    return render_template('admin/phone_numbers/edit_phone_number.html',
                           form=form, phone_number=phone_number)


# admin delete_phone_number
@app.route('/admin/phone_numbers/<int:phone_number_id>/delete',
           methods=['POST'])
@requires_auth
def admin_delete_phone_number(phone_number_id):
    phone_number = PhoneNumber.query.get(phone_number_id)
    db_session.delete(phone_number)
    db_session.commit()
    return redirect(url_for('admin_view_phone_numbers'))


# admin view_phone_number_raffle_number
@app.route('/admin/phone_number_raffle_numbers/<string:raffle_number>', methods=['GET'])
@requires_auth
def admin_view_phone_number_raffle_number_by_raffle_number(raffle_number):
    phone_number_raffle_numbers = PhoneNumberRaffleNumber.query.filter(PhoneNumberRaffleNumber.raffle_number == raffle_number)
    return render_template('admin/phone_numbers_raffle_numbers/view_phone_numbers_raffle_numbers_by_raffle_number.html',
                           phone_number_raffle_numbers=phone_number_raffle_numbers,
                           raffle_number=raffle_number)


# admin add_phone_number_raffle_number
@app.route('/admin/phone_numbers/<int:phone_number_id>/raffle_numbers/add',
           methods=['GET', 'POST'])
@requires_auth
def admin_add_phone_number_raffle_number(phone_number_id):
    phone_number = PhoneNumber.query.get(phone_number_id)
    form = PhoneNumberRaffleNumberForm()

    if form.validate_on_submit():
        pn_rn = PhoneNumberRaffleNumber()
        form.populate_obj(pn_rn)
        pn_rn.phone_number_id = phone_number_id
        pn_rn.updated_at = datetime.utcnow()
        pn_rn.created_at = datetime.utcnow()
        db_session.add(pn_rn)
        db_session.commit()
        return redirect(url_for('admin_view_phone_numbers'))

    return render_template('admin/phone_numbers/add_raffle_number.html',
            form=form, phone_number=phone_number)


# admin delete_phone_number_raffle_number
@app.route('/admin/phone_numbers/<int:phone_number_id>/raffle_numbers/<int:phone_number_raffle_number_id>/delete',
           methods=['POST'])
@requires_auth
def admin_delete_phone_number_raffle_number(phone_number_id, phone_number_raffle_number_id):
    phone_number_raffle_number = PhoneNumberRaffleNumber.query.get(phone_number_raffle_number_id)
    phone_number_id = phone_number_raffle_number.phone_number.id
    db_session.delete(phone_number_raffle_number)
    db_session.commit()
    return redirect(url_for('admin_edit_phone_number',
        phone_number_id=phone_number_id))


# admin view_audits
@app.route('/admin/audits', methods=['GET'])
@requires_auth
def admin_view_audits():
    audits = Audit.query.order_by(Audit.created_at.desc())
    return render_template('admin/audits/view_audits.html',
                           audits=audits)


# default view
@app.route('/', methods=['GET'])
def show_raffle_numbers():
    unclaimed_raffle_winners = RaffleWinner.\
        query.filter(RaffleWinner.is_claimed == False)
    claimed_raffle_winners = RaffleWinner.\
        query.filter(RaffleWinner.is_claimed == True)
    return render_template('slash.html',
                           unclaimed_raffle_winners=unclaimed_raffle_winners,
                           claimed_raffle_winners=claimed_raffle_winners)


# 500
@app.errorhandler(500)
def internal_error(exception):
    current_app.logger.exception(exception)
    return render_template('500.html'), 500


# shutdown database
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


def init_db():
    Base.metadata.create_all(engine)


# forms
class RaffleWinnerForm(ModelForm):
    class Meta:
        model = RaffleWinner
        include_primary_key = True
        only = ['raffle_time', 'raffle_number', 'item']


class PhoneNumberRaffleNumberForm(ModelForm):
    class Meta:
        model = PhoneNumberRaffleNumber
        only = ['raffle_number']


class PhoneNumberForm(ModelForm):
    class Meta:
        model = PhoneNumber
        include_primary_key = True
        only = ['phone_number']

    raffle_numbers = ModelFieldList(FormField(PhoneNumberRaffleNumberForm), min_entries=1)


def validate_twilio_request():
    """Ensure a request is coming from Twilio by checking the signature."""
    validator = RequestValidator(current_app.config['TWILIO_AUTH_TOKEN'])
    if 'X-Twilio-Signature' not in request.headers:
        return False
    signature = request.headers['X-Twilio-Signature']
    if 'SmsSid' in request.form:
        url = url_for('check_raffle', _external=True)
    else:
        return False
    return validator.validate(url, request.form, signature.encode('UTF-8'))
