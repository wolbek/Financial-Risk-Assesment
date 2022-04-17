import json
from webapp import app,db,bcrypt
from flask import redirect, render_template, request, url_for,flash,session
from webapp.models import Company, User
from webapp.forms import SignUpForm,LoginForm
from flask_login import current_user, login_required, login_user, logout_user
from webapp.global_constants import companies
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
from fbprophet import Prophet

@app.context_processor
def inject_companies():
    return dict(companies=companies)

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
        flash('Registered Successfully.You have signed into the website',category='successful')
        return redirect(url_for('assess_personalized_portfolio'))
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
            flash('You have signed in successfully',category='successful')
            return redirect(url_for('assess_personalized_portfolio'))
        else:
            flash('Login unsuccessful. Please check email and password',category='danger')
    # Forms will handle the validations. So if it's not validated, the errors will be stored in form.errors and will be passed to the register.html
    return render_template('login.html',form=form)

@app.route("/logout")
def logout():
    logout_user()
    flash('You have signed out successfully',category='successful')
    return redirect(url_for('home'))

@app.route("/")
def home():
    return render_template('home.html')

@app.route("/assess-personalized-portfolio",methods=['GET','POST'])
@login_required
def assess_personalized_portfolio():  
    return render_template('assess_personalized_portfolio.html')

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
    # print(df)  
    df = df['Adj Close']
    log_returns = np.log(df/df.shift())

    #Sharpe ratio according to given weights
    weight = np.array(weights)   
    weight = weight/weight.sum() 
    exp_rtn = np.sum(log_returns.mean()*weight)*252
    exp_vol = np.sqrt(np.dot(weight.T, np.dot(log_returns.cov()*252, weight)))
    sharpe_ratio = exp_rtn / exp_vol

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

    #Fbprophet
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

    f_preds_changes = []
    for x in preds:
        f_predict = preds[x][-30:][['yhat','yhat_upper']].mean().mean()
        now = df[x][-1]
        print(x,f"percentage change %:{(f_predict-now)/now*100}")
        f_preds_changes.append((f_predict-now)/now)

   
    f_preds_data={}
    for ticker in preds:
        f_preds_data[ticker]={
            "ds":preds[ticker]['ds'].astype(str).tolist(), 
            "yhat_lower":preds[ticker]['yhat_lower'].tolist(),
            "yhat_upper":preds[ticker]['yhat_upper'].tolist(),                   
            "yhat":preds[ticker]['yhat'].tolist(),
            "actual":df[ticker].dropna().tolist()
        }      

    hybrid_ratios = np.array([sum(x) for x in weights*f_preds_changes]) + sharpe_ratios
    index = np.where(normalize(exp_vols,0,1) <= 1) 
    risk_return_chart_data={
        "expected_return":exp_rtns.tolist(),
        "expected_volatility":exp_vols.tolist(),
        "ev_hb":exp_vols[np.where(hybrid_ratios == hybrid_ratios[index].max())].tolist(),
        "er_hb":exp_rtns[np.where(hybrid_ratios == hybrid_ratios[index].max())].tolist()
    }
    # ef1_ev=(exp_vols[np.where(sharpe_ratios == sharpe_ratios[index].max())]).tolist()
    # ef1_er=(exp_rtns[np.where(sharpe_ratios == sharpe_ratios[index].max())]).tolist()
    future_prediction_chart_data={
        "f_preds_changes":f_preds_changes,
        "f_preds_data":f_preds_data
    }

    return json.dumps({"sharpe_ratio":sharpe_ratio,"risk_return_chart_data":risk_return_chart_data,"future_prediction_chart_data":future_prediction_chart_data})
    # chart_data={
    #     "expected_return":[1,2,3],
    #     "expected_volatility":[1,2,3],
    # }
    # newpreds={
    #     "WIPRO.NS":{
    #         "ds":['2013-12-31', '2014-01-02', '2014-01-03'],
    #         "yhat":[1,2,3],
    #         "actual":[2,3,5]
    #     },
    #     "JUBS.NS":{
    #         "ds":['2013-12-31', '2014-01-02', '2014-01-03'],
    #         "yhat":[1,2,3],
    #         "actual":[2,3,5]
    #     }
    # }
    # return json.dumps({"sharpe_ratio":1.2,"chart_data":chart_data,"ef_er":2,"ef_ev":2,"newpreds":newpreds})

@app.route("/search-company",methods=['GET','POST'])
@login_required
def search_company():    
    ticker=request.args.get('company','RELIANCE.NS')
    company=Company.query.filter_by(ticker=ticker).first()   
    return render_template('search_company.html',company=company,ticker=ticker)




