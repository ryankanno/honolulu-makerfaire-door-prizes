# Honolulu Makerfaire Door Prize

**Note**: This started as a copy and paste of https://github.com/RobSpectre/Twilio-Hackpack-for-Heroku-and-Flask/ (production branch)

# Dependencies

  * Python 2.7.9

# Installation

`pip install -r requirements.txt`

# Running the App

`python app.py`

# User flows

## User texts raffle number

  - Text xxx-xxx-xxxx your 5-digit raffle ticket
  - System saves your phone number and ticket to a sqlite database
  - System looks up the number against a datastore that has all the winning raffle
    numbers.
  - If number matches winning raffle number:
    - Text user: winning_copy
  - If number does not match winning raffle number:
    - Text user: not_winning_copy

## Admin adds a winning raffle number

  - Real life drawing has occurred, raffle number has been selected.
  - Admin enters raffle ticket into the admin site.
  - After admin has saved number, system triggers an event to search all saved
    numbers for the ticket number.
  - If a number matches an existing saved number, play yoda voice indicating
    the user has won and should report to the front desk.

# TODO

  - Add admin security
