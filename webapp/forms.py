from ast import Pass
from tokenize import String
from xml.dom import ValidationErr
from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SubmitField
from wtforms.validators import InputRequired,Email,EqualTo,ValidationError,Regexp,Length
from webapp.models import User

class SignUpForm(FlaskForm):
    email=StringField(label='Email',validators=[InputRequired(),Email()],render_kw={"placeholder": "Email"})
    password1=PasswordField(label='Password',validators=[InputRequired(),Length(max=255), Regexp('^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', message='There must be at minumum 8 characters, at least one uppercase and one lowercase letter, one digit and one special character from @$!%*?&')],render_kw={"placeholder": "Password"})
    password2=PasswordField(label='Confirm Password',validators=[InputRequired(),EqualTo('password1', message="Password did not match")],render_kw={"placeholder": "Confirm Password"})    

    def validate_email(self,email):
        user=User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different email')

class LoginForm(FlaskForm):
    email=StringField(label='Email',validators=[InputRequired(),Email()],render_kw={"placeholder": "Email"})
    password=PasswordField(label='Password',validators=[InputRequired()],render_kw={"placeholder": "Password"})

class SavePortfolioForm(FlaskForm):
    name=StringField(label='Portfolio Name',validators=[InputRequired(),Length(min=1,max=100)])