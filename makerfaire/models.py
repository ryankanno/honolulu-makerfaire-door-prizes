from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from database import Base


class PhoneNumber(Base):
    __tablename__ = 'PhoneNumber'
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(32), unique=True)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class PhoneNumberRaffleNumber(Base):
    __tablename__ = 'PhoneNumberRaffleNumber'
    id = Column(Integer, primary_key=True)
    phone_number_id = Column(Integer, ForeignKey('PhoneNumber.id'))
    raffle_number = Column(String(8))
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class RaffleNumber(Base):
    __tablename__ = 'RaffleNumber'
    id = Column(Integer, primary_key=True)
    raffle_number = Column(String(8), unique=True)
    raffle_time = Column(DateTime)
    is_claimed = Column(Boolean)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)
