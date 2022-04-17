from webapp import db,login_manager
from flask_login import UserMixin
import click
from bcrypt import checkpw, hashpw, gensalt
from flask.cli import with_appcontext

import json
from time import sleep
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model,UserMixin):
    id=db.Column(db.Integer(),primary_key=True)
    email=db.Column(db.String(length=255),nullable=False,unique=True)
    password=db.Column(db.String(length=60),nullable=False)
    saved_portfolios=db.relationship('SavedPortfolios',cascade="all,delete",backref='User',lazy=True)
    def set_password(self, password):
        self.password = hashpw(password.encode('utf-8'), gensalt()).decode('ascii')

    def check_password(self, password):
        return checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

class Company(db.Model):
    ticker = db.Column(db.String(500), nullable=False, primary_key=True)
    info = db.Column(db.JSON, nullable=False,server_default="{}")

class SavedPortfolios(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, primary_key=True)
    portfolio_name= db.Column(db.String(500), nullable=False, server_default="")
    portfolio_stocks=db.Column(db.JSON, nullable=False,server_default="{}")

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

    var = Fetch(['WIPRO.NS','ZOMATO.NS','RELIANCE.NS'])
    print(json.dumps(var.scraped))
    click.echo('Seeded data.')