from ast import Pass
from tokenize import String
from xml.dom import ValidationErr
from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SubmitField
from wtforms.validators import InputRequired,Email,EqualTo,ValidationError
from webapp.models import User

class SignUpForm(FlaskForm):
    email=StringField(label='Email',validators=[InputRequired(),Email()])
    password1=PasswordField(label='Password',validators=[InputRequired()])
    password2=PasswordField(label='Confirm Password',validators=[InputRequired(),EqualTo('password1', message="Password did not match")])    

    def validate_email(self,email):
        user=User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different email')

class LoginForm(FlaskForm):
    email=StringField(label='Email',validators=[InputRequired(),Email()])
    password=PasswordField(label='Password',validators=[InputRequired()])
