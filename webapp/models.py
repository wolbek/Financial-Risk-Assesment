from webapp import db,login_manager
from flask_login import UserMixin
import click
from bcrypt import checkpw, hashpw, gensalt
from flask.cli import with_appcontext

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model,UserMixin):
    id=db.Column(db.Integer(),primary_key=True)
    email=db.Column(db.String(length=255),nullable=False,unique=True)
    password=db.Column(db.String(length=60),nullable=False)
    def set_password(self, password):
        self.password = hashpw(password.encode('utf-8'), gensalt()).decode('ascii')

    def check_password(self, password):
        return checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    db.create_all()   
    click.echo('Initialized the database.')

@click.command('create-users')
@with_appcontext
def create_users_command():
    #Creating a course admin
    user1=User(
        email='user1@gmail.com',      
    )
    user1.set_password('user')
    user2=User(
        email='user2@gmail.com',      
    )
    user2.set_password('user')
    db.session.add(user1)
    db.session.add(user2)
    db.session.commit()
    click.echo('Users created.')

@click.command('seed-data')
@with_appcontext
def seed_data_command():
    click.echo('Seeded data.')