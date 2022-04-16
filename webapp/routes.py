import json
from webapp import app,db,bcrypt
from flask import redirect, render_template, request, url_for,flash
from webapp.models import User
from webapp.forms import SignUpForm,LoginForm, SavePortfolioForm
from flask_login import current_user, login_required, login_user, logout_user
from webapp.global_constants import companies
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
from fbprophet import Prophet


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
    return render_template('assess_personalized_portfolio.html',companies=companies,form=SavePortfolioForm())

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
    weights=request.form.getlist('weights[]')
    weights=[int(x) for x in weights]
    tickers=[]
    for name in stocks:
        symbol=list(filter(lambda x: x['name'] == name, companies))[0]['symbol']
        tickers.append(symbol+".NS")
    df=yf.download(tickers, start="2014-01-01")   
    print(df)  
    df = df['Adj Close']
    log_returns = np.log(df/df.shift())

    #Sharpe ratio according to given weights
    print(type(weights[0]))
    weight = np.array(weights)
    print("Summmmmm")
    print(weight.sum())
    weight = weight/weight.sum()
    print(weight)
    exp_rtn = np.sum(log_returns.mean()*weight)*252
    exp_vol = np.sqrt(np.dot(weight.T, np.dot(log_returns.cov()*252, weight)))
    sharpe_ratio = exp_rtn / exp_vol
    print("sharpe_ratio")
    print(sharpe_ratio)

    #Monte-Carlo simulation
    n = 10000
    weights = np.zeros((n, len(tickers)))
    exp_rtns = np.zeros(n)
    exp_vols = np.zeros(n)
    sharpe_ratios = np.zeros(n)

    for i in range(n):
        weight = np.random.random(len(tickers))
        weight /= weight.sum()
        weights[i] = weight
        
        exp_rtns[i] = np.sum(log_returns.mean()*weight)*252
        exp_vols[i] = np.sqrt(np.dot(weight.T, np.dot(log_returns.cov()*252, weight)))
        sharpe_ratios[i] = exp_rtns[i] / exp_vols[i]

    def normalize(arr, t_min, t_max):
        norm_arr = []
        diff = t_max - t_min
        diff_arr = max(arr) - min(arr)
        for i in arr:
            temp = (((i - min(arr))*diff)/diff_arr) + t_min
            norm_arr.append(temp)
        return np.asarray(norm_arr)
    
    index = np.where(normalize(exp_vols,0,1) <= 1) 
    chart_data={
        "expected_return":exp_rtns.tolist(),
        "expected_volatility":exp_vols.tolist()
    }
    ef_er=(exp_rtns[np.where(sharpe_ratios == sharpe_ratios[index].max())]).tolist()
    ef_ev=(exp_vols[np.where(sharpe_ratios == sharpe_ratios[index].max())]).tolist()

    preds = {}
    for ticker in df.columns:
        stock = df[[ticker]]
        stock.reset_index(inplace=True)
        stock = stock.rename(columns={"Date": "ds", ticker: "y"})
        stock.dropna(axis=0,inplace=True)
        print(ticker)
        model=Prophet()
        model.fit(stock)
        future_dates=model.make_future_dataframe(periods=1095)
        prediction=model.predict(future_dates)
        preds[ticker]=prediction
        # preds[ticker] = [prediction,model.plot(prediction)]
    print("-------------------")
    print(preds)
    # preds['ds'] = preds['ds'].astype(str)
    # print(prediction['Date'])
    # prediction['Date'] = prediction['Date'].astype(str)
    # prediction.index = prediction.index.astype(str)
    newpreds={}
    for ticker in preds:
        newpreds[ticker]={
            "ds":preds[ticker]['ds'].astype(str).tolist(),
            "trend":preds[ticker]['trend'].tolist(),
            "yhat_lower":preds[ticker]['yhat_lower'].tolist(),
            "yhat_upper":preds[ticker]['yhat_upper'].tolist(),
            "trend_lower":preds[ticker]['trend_lower'].tolist(),
            "trend_upper":preds[ticker]['trend_upper'].tolist(),
            "additive_terms":preds[ticker]['additive_terms'].tolist(),
            "additive_terms_lower":preds[ticker]['additive_terms_lower'].tolist(),
            "additive_terms_upper":preds[ticker]['additive_terms_upper'].tolist(),
            "weekly":preds[ticker]['weekly'].tolist(),
            "weekly_lower":preds[ticker]['weekly_lower'].tolist(),
            "weekly_upper":preds[ticker]['weekly_upper'].tolist(),
            "yearly":preds[ticker]['yearly'].tolist(),
            "yearly_lower":preds[ticker]['yearly_lower'].tolist(),
            "yearly_upper":preds[ticker]['yearly_upper'].tolist(),
            "multiplicative_terms":preds[ticker]['multiplicative_terms'].tolist(),
            "multiplicative_terms_lower":preds[ticker]['multiplicative_terms_lower'].tolist(),
            "multiplicative_terms_upper":preds[ticker]['multiplicative_terms_upper'].tolist(),
            "yhat":preds[ticker]['yhat'].tolist(),
            "actual":df[ticker].tolist()
        }
        

    return json.dumps({"sharpe_ratio":sharpe_ratio,"chart_data":chart_data,"ef_er":ef_er,"ef_ev":ef_ev,"newpreds":newpreds})

@app.route("/save-portfolio/<int:user_id>")
@login_required
def save_portfolio(user_id):
    return render_template('assess_personalized_portfolio.html',companies=companies,form=SavePortfolioForm())




