from flask import Flask, request, jsonify, render_template
import yfinance as yf
from yahoo_fin import news
from openai import OpenAI
import json
import os

openai = OpenAI(
    api_key = os.getenv("OPENAI_API_KEY")
    )

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html') 

@app.route('/process', methods=['POST'])
def process_input():
    data = request.get_json()

    tick = data.get('user_input', '')

    response = central(tick)

    print(response)


    return jsonify(response)




def add_commas(number):
    return f"${number:,.2f}"

def get_altman_z_score(tick,data):
    tick = tick.upper()
    ticker = yf.Ticker(tick)
    
    balance_sheet = ticker.balance_sheet
    income_statement = ticker.financials

    try:
        total_assets = balance_sheet.loc["Total Assets"].dropna().iloc[0] 
        retained_earnings = balance_sheet.loc["Retained Earnings"].dropna().iloc[0] 
        ebit = income_statement.loc["EBIT"].dropna().iloc[0]
        net_sales = income_statement.loc["Total Revenue"].dropna().iloc[0] 
        market_value_equity = ticker.info.get("marketCap") or ticker.info.get("totalAssets")
        long_term_debt = balance_sheet.loc["Long Term Debt And Capital Lease Obligation"].dropna().iloc[0]
        working_capital = balance_sheet.loc["Working Capital"].dropna().iloc[0]
        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets 
        x3 = ebit / total_assets 
        x4 = market_value_equity / long_term_debt if long_term_debt > 0 else 0  
        x5 = net_sales / total_assets
        z_score = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

        if z_score < 1.81:
            status = "<High Risk>"
        elif z_score > 1.81 and z_score < 2.99:
            status = "<Moderate Risk>"
        else:
            status = "<Low Risk>"

        data.update({
            " Altman Z Score " + status: round(z_score)
        })

        return data

    except Exception as e:
        return json.dumps({"error": f"No data at {e}"})
    

def calculate_capm(beta, risk_free_rate, market_return):

    cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)
    return cost_of_equity

def calculate_wacc(equity, debt, cost_of_equity, cost_of_debt, tax_rate):

    total_value = equity + debt
    wacc = (equity / total_value) * cost_of_equity + (debt / total_value) * cost_of_debt * (1 - tax_rate)
    return wacc\
    
def main(ticker, data):
    beta = ticker.info.get("beta") or ticker.info.get("beta3Year") or 1

    risk_free_rate = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1] / 100  # Convert to decimal
    sp500 = yf.Ticker("^GSPC")
    data1 = sp500.history(period="5y")
    start_price = data1['Close'].iloc[0]  
    end_price = data1['Close'].iloc[-1] 
    cumulative_return = (end_price / start_price) - 1
    years = 5  
    annualized_return = (1 + cumulative_return) ** (1 / years) - 1
    market_return = annualized_return 
    cost_of_equity = calculate_capm(beta, risk_free_rate, market_return)
    equity_value = ticker.info.get("marketCap") or ticker.info.get("totalAssets")
    quote_type = ticker.info.get("quoteType")
    legal_type = ticker.info.get("legalType")

    if not quote_type == "ETF" or not legal_type == "Exchange Traded Fund":

        balance_sheet = ticker.balance_sheet
        debt_value = balance_sheet.loc['Long Term Debt And Capital Lease Obligation'].dropna().iloc[0]
        income_statement = ticker.financials
        try:
            interest_expense = income_statement.loc['Interest Expense'].dropna().iloc[0]
        except KeyError:
            interest_expense = 0
        print(interest_expense)
        cost_of_debt = interest_expense / debt_value
        pre_tax_income = income_statement.loc['Pretax Income'].dropna().iloc[0]
        tax_expense = income_statement.loc['Tax Provision'].dropna().iloc[0]
        tax_rate = tax_expense / pre_tax_income

        wacc = calculate_wacc(equity_value, debt_value, cost_of_equity, cost_of_debt, tax_rate)

        data["Beta"] = beta
        data["Cost of Equity (CAPM)"] = round(cost_of_equity, 2)
        data["Tax Rate"] = round(tax_rate, 2)
        data["Cost of Debt"] = round(cost_of_debt, 2)
        data["WACC"] = round(wacc, 2)


    return data

def get_weights(openai, news_articles, tick):
    prompt = f"""
    The following are recent financial news headlines. For each headline, provide:
    1. A defined year duration (from 1 to 5 years) representing how long the impact of the news will last on the stock {tick}.
    2. A multiplier (from -1.00 to 1.00) representing the direction and intensity of the news' impact on FCF (free cash flow) of the stock {tick}.
    - Negative values (-1.00 to 0) indicate negative impact.
    - Positive values (0 to 1.00) indicate positive impact.


    {chr(10).join([f'{i+1}. "{headline}"' for i, headline in enumerate(news_articles)])}

    Please return the response in JSON format, excluding the news title, with the structure:
    [
        {{"title": <string>,"duration_years": <integer>, "fcf_multiplier": <float>}},
        ...
    ]
    """
    try:
        response = openai.chat.completions.create(
            messages = [{"role": "assistant", "content": prompt}],
            model="gpt-4",
            max_tokens=600,
            temperature=0.2 
        )
        output = response.choices[0].message.content.strip()

        print(output)
        
    except Exception as e:
        print(f"Error: {e}")

    return output


def get_fcf_growth(ticker):
    cash_flow = ticker.cashflow
    fcf = cash_flow.loc["Free Cash Flow"]
    fcf = fcf.dropna()  
    fcf_years = fcf[-5:]  
    fcf_values = fcf_years.values[::-1]  
    growth_rates = []
    for i in range(1, len(fcf_values)):
        growth_rate = (fcf_values[i] - fcf_values[i - 1]) / abs(fcf_values[i - 1]) 
        growth_rates.append(growth_rate)
    average_growth = sum(growth_rates) / len(growth_rates)
    return average_growth

def dcf(fcfs, wacc, average_growth, data):
    sumdcf = 0
    for i in range(len(fcfs)):
        pv = fcfs[i]/((1+wacc)**(i+1))
        sumdcf += pv
        data[f"PV {i+1}"] = add_commas(round(pv,2))
    
    tv = (fcfs[-1] * average_growth)/(wacc - average_growth)

    pv = tv/((1+wacc)**(len(fcfs)+1))
    sumdcf += pv
    data['PV-TV'] = add_commas(round(tv,2))
    data['DCF'] = add_commas(round(sumdcf,2))

    return data
    
def main2(tick, data): 
    ticker = yf.Ticker(tick)

    headlines = news.get_yf_rss(tick)

    news_articles = []
    for headline in headlines[:5]:  
        news_articles.append(headline['summary'])

    output = get_weights(openai, news_articles, tick)
    


    try:
        response_data = json.loads(output)
        for i in response_data:
            print(i['title'])
            print(i['fcf_multiplier'] + 1)
    except json.JSONDecodeError:
        print("Error: The API response could not be parsed as JSON. Check the response format.")


    average_growth = get_fcf_growth(ticker)
    data.update({"Average Growth Rate": round(average_growth, 2)})
    present_fcf = ticker.cash_flow.loc['Free Cash Flow'].dropna().iloc[0]
    fcfs = []
    for i in range(4):
        prev_fcf = present_fcf * (1 + average_growth)**(i+1)
        for item in response_data:
            if item['duration_years'] <= i+1:
                prev_fcf = prev_fcf * (item['fcf_multiplier']+1)
        


        fcfs.append(prev_fcf)
        
        data.update({f"Free Cash Flow Year {i+1}": add_commas(round(prev_fcf,2))})

    data = dcf(fcfs, data['WACC'],average_growth,data)

    return data

def central(tick):
    data = {}
    tick = tick.upper()
    ticker = yf.Ticker(tick)
    data = main(ticker,data)
    data = main2(tick,data)
    data = get_altman_z_score(tick,data)
    return(data)




if __name__ == '__main__':
    app.run(debug=True)