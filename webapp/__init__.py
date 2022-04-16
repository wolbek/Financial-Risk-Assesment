import os
from decouple import config
from flask import Flask,render_template
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

app=Flask(__name__)
app.config.from_mapping(
    SQLALCHEMY_DATABASE_URI=config('SQLALCHEMY_DATABASE_URI'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SECRET_KEY=config('SECRET_KEY'),
)

db=SQLAlchemy(app)

bcrypt=Bcrypt(app)
login_manager=LoginManager(app)

login_manager.login_view='login'
login_manager.login_message_category='info'

# register database
from webapp.models import init_db_command, create_users_command,seed_data_command
app.cli.add_command(init_db_command)
app.cli.add_command(create_users_command)
app.cli.add_command(seed_data_command)

from webapp import routes