import json
from webapp import app,db,bcrypt
from flask import redirect, render_template, request, url_for,flash,session
from webapp.models import Company, SavedPortfolios, User
from webapp.forms import SignUpForm,LoginForm, SavePortfolioForm
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
            flash('You have signed in successfully',category='successful')
            return redirect(url_for('home'))
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

@app.route("/assess-personalized-portfolio")
@login_required
def assess_personalized_portfolio():
    form=SavePortfolioForm()
    if form.validate_on_submit():  
        stocks=[]
        for i in range(1,int(request.form['stockCount'])+1):                        
            if request.form['stock'+str(i)]=="" or request.form['weight'+str(i)]=="":
                flash('Some fields are not selected!', 'error')
                return render_template('create_faculty.html',form=form)
            elif request.form['stock'+str(i)] in stocks:
                flash('Some stocks are repeated!', 'error')
                return render_template('create_faculty.html',form=form)
            else:
                stocks.append(request.form['stock'+str(i)])
        portfolio_stocks={}
        for i in range(1,int(request.form['stockCount'])+1): 
            portfolio_stocks[request.form['stock'+str(i)]]=request.form['weight'+str(i)]      
        save_portfolio=SavedPortfolios(user_id=session['id'],portfolio_name=request.form['name'],portfolio_stocks=portfolio_stocks)
        db.session.add(save_portfolio)
        db.session.commit()

    return render_template('assess_personalized_portfolio.html',form=form)

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

   
    newpreds={}
    for ticker in preds:
        newpreds[ticker]={
            "ds":preds[ticker]['ds'].astype(str).tolist(), 
            "yhat_lower":preds[ticker]['yhat_lower'].tolist(),
            "yhat_upper":preds[ticker]['yhat_upper'].tolist(),                   
            "yhat":preds[ticker]['yhat'].tolist(),
            "actual":df[ticker].dropna().tolist()
        }      
        

    return json.dumps({"sharpe_ratio":sharpe_ratio,"chart_data":chart_data,"ef_er":ef_er,"ef_ev":ef_ev,"newpreds":newpreds})
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

@app.route("/saved-portfolios")
@login_required
def saved_portfolios():
    print()
    return render_template('saved_portfolios.html')

@app.route("/search-company",methods=['GET','POST'])
@login_required
def search_company():
    if request.method=="POST":       
        symbol=list(filter(lambda x: x['name'] == request.form['company'] , companies))[0]['symbol']+".NS"
        company=Company.query.filter_by(ticker=symbol).first()
    else:
        symbol="RELIANCE.NS"
        company=Company.query.filter_by(ticker=symbol).first()
    
    return render_template('search_company.html',company=company,symbol=symbol)




