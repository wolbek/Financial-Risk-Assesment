import json
from webapp import app,db,bcrypt
from flask import redirect, render_template, request, url_for,flash
from webapp.models import User
from webapp.forms import SignUpForm,LoginForm
from flask_login import current_user, login_required, login_user, logout_user
from webapp.global_constants import companies
import yfinance as yf

@app.route('/sign_up',methods=['GET','POST'])
def sign_up():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form=SignUpForm()
    if form.validate_on_submit():
        user=User(
            email=form.email.data,
            password=bcrypt.generate_password_hash(form.password1.data).decode('utf-8'),            
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Registered Successfully.You have logged into the website',category='successful')
        return redirect(url_for('home'))
    # Forms will handle the validations. So if it's not validated, the errors will be stored in form.errors and will be passed to the register.html
    return render_template('sign_up.html',form=form)

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password,form.password.data):
            login_user(user)
            flash('You have logged in successfully',category='successful')
            return redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check email and password',category='danger')
    # Forms will handle the validations. So if it's not validated, the errors will be stored in form.errors and will be passed to the register.html
    return render_template('login.html',form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/")
def home():
    return render_template('home.html')

@app.route("/features")
@login_required
def features():
    return render_template('features.html')

@app.route("/assess-personalized-portfolio")
@login_required
def assess_personalized_portfolio():
    return render_template('assess_personalized_portfolio.html',companies=companies)

@app.route("/assess-suggested-portfolio")
@login_required
def assess_suggested_portfolio():
    return render_template('assess_suggested_portfolio.html')

@app.route("/assess-automated-portfolio")
@login_required
def assess_automated_portfolio():
    return render_template('assess_automated_portfolio.html')

@app.route("/api/f1/line-chart",methods=['GET','POST'])
@login_required
def line_chart(): 
    stocks=request.form.getlist('stocks[]')
    chart_data={
        "dates":[],
        "stock_prices":{}
    }
    for name in stocks:
        # x is object. So give that object which has 'name'==name. You'll get a list. Access its 1st element. Use its 'symbol'
        symbol=list(filter(lambda x: x['name'] == name, companies))[0]['symbol']
        stock_prices_data=yf.download(symbol+".NS", period="3mo")['Close']
        # .astype(str) to convert timestamp to string so that it becomes JSON serializable
        chart_data['dates']=list(stock_prices_data.index.astype(str))
        chart_data['stock_prices'][name]=list(stock_prices_data/stock_prices_data[0]*100)
    # print(chart_data)
    return json.dumps({"chart_data":chart_data})





