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

import json
from time import sleep
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

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
    weights=[float(x) for x in weights]
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

    #Monte-Carlo simulation (in here we find the most efficient sharpe ratio)
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
        model=Prophet()
        model.fit(stock)
        future_dates=model.make_future_dataframe(periods=1095)
        prediction=model.predict(future_dates)        
        preds[ticker]=prediction
        # print(ticker)


    f_preds_changes = []
    for x in preds:
        f_predict = preds[x][-30:][['yhat','yhat_upper']].mean().mean()
        now = df[x][-1]
        # print(x,f"percentage change %:{(f_predict-now)/now*100}")
        f_preds_changes.append(round((f_predict-now)/now*100,2))

   
    f_preds_data={}
    for ticker in preds:
        f_preds_data[ticker]={
            "ds":preds[ticker]['ds'].astype(str).tolist(), 
            "yhat_lower":preds[ticker]['yhat_lower'].tolist(),
            "yhat_upper":preds[ticker]['yhat_upper'].tolist(),                   
            "yhat":preds[ticker]['yhat'].tolist(),
            "actual":df[ticker].dropna().tolist()
        }      

    hybrid_ratios = np.array([sum(x)/120 for x in weights*f_preds_changes]) + sharpe_ratios
    # hybrid_ratios = sharpe_ratios
    # print(hybrid_ratios)
    index = np.where(normalize(exp_vols,0,1) <= 1) 

    hybrid_ratio=hybrid_ratios[index].max()

    ev_hb=exp_vols[np.where(hybrid_ratios == hybrid_ratios[index].max())].tolist()
    er_hb=exp_rtns[np.where(hybrid_ratios == hybrid_ratios[index].max())].tolist()

    hybrid_ratios=hybrid_ratios.tolist()
    best_weight_combination_list=(weights[hybrid_ratios.index(hybrid_ratio)]*100).tolist()
    best_weight_combination_dictionary={}
    for i,ticker in enumerate(df.columns):
        best_weight_combination_dictionary[ticker]=best_weight_combination_list[i]

    # print(f"SHARPE RATIO: {sharpe_ratio}")
    # print(f"HYBRID RATIO: {hybrid_ratio}")
    # print(f"EXPECTED RETURN: {er_hb}")
    # print(f"EXPECTED VOLATILITY: {ev_hb}")
    # print(f"BEST WEIGHT COMBINATION: {best_weight_combination_dictionary}")

    risk_return_chart_data={
        "expected_return":exp_rtns.tolist(),
        "expected_volatility":exp_vols.tolist(),
        "ev_hb":ev_hb,
        "er_hb":er_hb
    }
    
    future_prediction_chart_data={
        "f_preds_changes":f_preds_changes,
        "f_preds_data":f_preds_data
    }

    

    return json.dumps({"sharpe_ratio":sharpe_ratio,"hybrid_ratio":hybrid_ratio,"risk_return_chart_data":risk_return_chart_data,"best_weight_combination_dictionary":best_weight_combination_dictionary,"future_prediction_chart_data":future_prediction_chart_data})
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
    if not company:
        class Fetch:
            def __init__(self, companies):
                for company in companies:
                    self.company = company
                    self.details = {
                        "logo": "https://www.google.com/search?q={}",
                        "summary": "https://finance.yahoo.com/quote/{}?p={}",
                        "stats": "https://finance.yahoo.com/quote/{}/key-statistics?p={}",
                        "profile": "https://finance.yahoo.com/quote/{}/profile?p={}",               
                        "holders": "https://finance.yahoo.com/quote/{}/holders?p={}",              
                        "income": "https://finance.yahoo.com/quote/{}/financials?p={}",
                        "cash_flow": "https://finance.yahoo.com/quote/{}/cash-flow?p={}",
                        "bl_sheet": "https://finance.yahoo.com/quote/{}/balance-sheet?p={}"
                    }
                    self.scraped = {}
                    options = webdriver.ChromeOptions()
                    options.add_argument("--start-maximized")   
                    options.add_argument("--headless")                   
                    # options.add_argument("--disable-gpu")                   
                    s = Service(r'webapp\chromedriver.exe')        
                    self.driver = webdriver.Chrome(
                        service=s,
                        options=options)

                    for key,value in self.details.items():
                        if key == "logo":
                            self.driver.execute_script('window.open("{}")'.format(value.replace("{}", self.company.split(".")[0].lower())))
                        else:
                            self.driver.execute_script('window.open("{}")'.format(value.replace("{}", self.company)))

                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.driver.close()

                    list_pages = {
                        1: self.logo,
                        2: self.summary,
                        3: self.stats,
                        4: self.profile,
                        5: self.holders,
                        6: self.income,
                        7: self.cash_flow,
                        8: self.bl_sheet,
                    }

                    for key,value in list_pages.items():
                        self.driver.switch_to.window(self.driver.window_handles[-key])
                        for _ in range(3):
                            try:
                                key = value()                       
                                break
                            except:
                                continue
        
                    self.driver.quit()              
                    ticker_info=Company(
                        ticker=company,
                        info=self.scraped
                    )
                    db.session.add(ticker_info)
                    db.session.commit()

            def logo(self):        
                try:
                    self.scraped['logo'] = BeautifulSoup(self.driver.find_element(by=By.XPATH,value='/html/body/div[7]/div/div[10]/div[2]/div/div/div[2]/div/div[1]/div/div[2]/div').get_attribute('innerHTML'), 'html.parser').find('img').get('src')
                except:
                    self.scraped['logo'] = []

            def summary(self):
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                overview = soup.find("div", {"id": "quote-summary"})
                self.driver.execute_script("window.scrollTo(0, 800);")
                sleep(5)
                news = soup.find("div", {"id": "quoteNewsStream-0-Stream"})
                also_watch = BeautifulSoup(
                    self.driver.find_element(by=By.CSS_SELECTOR, value='#recommendations-by-symbol > table > tbody').get_attribute('innerHTML'), 'html.parser')

                def data_table(*table, type="normal"):
                    table_data = []
                    for t in table:
                        soup = t.find_all('tr')
                        if type == "also":
                            for sou in soup:
                                v = list(x.text for x in sou.find_all('td'))
                                v.insert(0, sou.find('a').text)
                                v.insert(0, sou.find('p').text)
                                v.pop(2)
                                table_data.append(v)
                        else:
                            for sou in soup:
                                table_data.append([x.text for x in sou.find_all('td')])
                        return table_data

                def data_news(soup):
                    news = []
                    for sou in soup.findAll('li'):
                        try:
                            node = []
                            link=sou.find('a')['href']
                            node.append(link)  
                            img = sou.find('img')
                            if img:
                                node.append(img.get('src'))
                            else:
                                node.append("https://elegalmetrology.jharkhand.gov.in/japnet/images/news.jpg")
                            time = sou.find('div', {"class": 'C(#959595) Fz(11px) D(ib) Mb(6px)'}).find_all('span')[1].text
                            
                            heading = sou.find('a').text
                            para = sou.find('p').text
                            node.append(time)                   
                            node.append(heading)
                            node.append(para)
                            news.append(node)

                        except:
                            continue
                    return news

                try:
                    self.scraped['overview'] = data_table(overview)
                except:
                    self.scraped['overview'] = []
                try:
                    self.scraped['also_watch'] = data_table(also_watch, type="also")
                except:
                    self.scraped['also_watch'] = []
                try:
                    self.scraped['news'] = data_news(news)
                except:
                    self.scraped['news'] =[]

            def stats(self):
                def data_table(xpath_value):
                    table_data = {}
                    table=BeautifulSoup(self.driver.find_element(by=By.XPATH,value=xpath_value).get_attribute('innerHTML'), 'html.parser')
                    for t in table:
                        rows= t.find_all('tr')
                        for row in rows:
                            try:
                                table_data[row.td.span.text]=row.find_all("td")[1].text
                            except:
                                continue
                    return table_data
                try:
                    stat={
                        "valuation measures":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[1]/div/div/div/div/table'),
                        "fiscal year":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[3]/div/div[1]/div/div/table'),
                        "profitability":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[3]/div/div[2]/div/div/table'),
                        "management effectiveness":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[3]/div/div[3]/div/div/table'),
                        "income statement":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[3]/div/div[4]/div/div/table'),
                        "balance sheet":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[3]/div/div[5]/div/div/table'),
                        "cash flow statement":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[3]/div/div[6]/div/div/table'),
                        "stock price history":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[2]/div/div[1]/div/div/table'),
                        "share statistics":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[2]/div/div[2]/div/div/table'),
                        "dividends & splits":data_table('//*[@id="Col1-0-KeyStatistics-Proxy"]/section/div[2]/div[2]/div/div[3]/div/div/table')
                    }
                    self.scraped['stats']=stat   
                except:
                    self.scraped['stats']=[]     

            def profile(self):
                def data_table(*table):            
                    table_data = []
                    for t in table:
                        soup = t.find_all('tr')
                        for sou in soup:                    
                            tr=[x.text for x in sou.find_all('td')]
                            if tr:
                                table_data.append(tr)
                    return table_data

                self.driver.execute_script("window.scrollTo(0, 800);")
                sleep(1)
                try:
                    prof = {
                        "company_name": self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-0-Profile-Proxy"]/section/div[1]/div/h3').text, 
                        'address': self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-0-Profile-Proxy"]/section/div[1]/div/div/p[1]').text,
                        'sector': self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-0-Profile-Proxy"]/section/div[1]/div/div/p[2]').text,
                        'key_exe':data_table(BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-0-Profile-Proxy"]/section/section[1]/table').get_attribute('innerHTML'), 'html.parser')),
                        'map':self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-0-Profile-Proxy"]/section/div[3]').get_attribute('outerHTML'),
                        'description':BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-0-Profile-Proxy"]/section/section[2]').get_attribute('innerHTML'), 'html.parser').find('p').text,
                        'corporate_governance':self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-0-Profile-Proxy"]/section/section[3]').get_attribute('innerHTML')
                        }        
                    self.scraped['profile'] = prof
                except:
                    self.scraped['profile'] = []

            def holders(self):
                def data_table(*table):
                    table_data = []
                    for t in table:
                        soup = t.find_all('tr')
                        for sou in soup:
                            tr=[x.text for x in sou.find_all('td')]
                            if tr:
                                table_data.append(tr)
                    return table_data

                try:
                    self.scraped['major_holders'] = data_table(BeautifulSoup(self.driver.find_element(by=By.XPATH, value='//*[@id="Col1-1-Holders-Proxy"]/section/div[2]/div[2]/div/table').get_attribute('innerHTML'), 'html.parser'))
                except:
                    self.scraped['major_holders']=[]
                try:
                    self.scraped['top_mutual_fund_holders'] = data_table(BeautifulSoup(self.driver.find_element(by=By.XPATH, value='//*[@id="Col1-1-Holders-Proxy"]/section/div[2]/div[3]/table').get_attribute('innerHTML'), 'html.parser'))
                except:
                    self.scraped['top_mutual_fund_holders']=[]

            def income(self):
                def give_data(table):
                    data = []
                    for soup in table:
                        try:
                            data.append([i.text for i in soup.div])
                        except:
                            continue
                    return data
                try:
                    incom = [
                        [x.text for x in BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-1-Financials-Proxy"]/section/div[3]/div[1]/div/div[1]/div').get_attribute('innerHTML'), 'html.parser')],
                        give_data(BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-1-Financials-Proxy"]/section/div[3]/div[1]/div/div[2]').get_attribute('innerHTML'), 'html.parser'))
                    ]
                    self.scraped["income"] = incom
                except:
                    self.scraped["income"] = []

            def cash_flow(self):
                def give_data(table):
                    data = []
                    for soup in table:
                        try:
                            data.append([i.text for i in soup.div])
                        except:
                            continue
                    return data

                try:
                    incom = [
                        [x.text for x in BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-1-Financials-Proxy"]/section/div[3]/div[1]/div/div[1]/div').get_attribute('innerHTML'), 'html.parser')],
                        give_data(BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-1-Financials-Proxy"]/section/div[3]/div[1]/div/div[2]').get_attribute('innerHTML'), 'html.parser'))
                    ]
                    self.scraped["cash flow"] = incom
                except:
                    self.scraped["cash flow"] = []

            def bl_sheet(self):
                def give_data(table):
                    data = []
                    for soup in table:
                        try:
                            data.append([i.text for i in soup.div])
                        except:
                            continue
                    return data

                try:
                    incom = [
                        [x.text for x in BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-1-Financials-Proxy"]/section/div[3]/div[1]/div/div[1]/div').get_attribute('innerHTML'), 'html.parser')],
                        give_data(BeautifulSoup(self.driver.find_element(by=By.XPATH,value='//*[@id="Col1-1-Financials-Proxy"]/section/div[3]/div[1]/div/div[2]').get_attribute('innerHTML'), 'html.parser'))
                    ]
                    self.scraped["bl sheet"] = incom
                except:
                    self.scraped["bl sheet"] = [] 

        Fetch([ticker])
        company=Company.query.filter_by(ticker=ticker).first()   
        
    company_data=yf.download(ticker, start="2014-01-01")['Adj Close']
    
    return render_template('search_company.html',company=company,ticker=ticker,company_data=company_data)




