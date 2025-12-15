import streamlit as st
import mysql.connector
import pandas as pd
import time
import requests
import numpy as np
import graphviz 
import plotly.express as px
import bcrypt
import re
import json
from io import StringIO
from datetime import datetime, timedelta
from requests.exceptions import RequestException, Timeout

# --- הגדרות דף ---
st.set_page_config(page_title="InvestWise", layout="wide", page_icon="📈")

# --- הזרקת CSS (עיצוב Light Mode + רספונסיביות + RTL) ---
st.markdown("""
<style>
    /* הגדרת כיוון כללית ויישור לימין */
    .stApp { direction: rtl; text-align: right; background-color: #f8f9fa; color: #2c3e50; }
    p, h1, h2, h3, h4, h5, h6, span, div, label { text-align: right !important; font-family: 'Heebo', sans-serif !important; }
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] { direction: rtl; text-align: right; }

    /* Hero Section */
    .hero-title {
        text-align: center !important;
        background: -webkit-linear-gradient(45deg, #6c418c, #9b59b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 4.5em;
        margin-bottom: 0px;
        text-shadow: 0px 2px 5px rgba(108, 65, 140, 0.1);
    }
    .hero-subtitle { text-align: center !important; color: #7f8c8d; font-size: 1.4em; font-weight: 400; margin-top: 5px; margin-bottom: 50px; }

    /* Dashboard Title */
    .dashboard-title {
        text-align: center !important;
        background: -webkit-linear-gradient(45deg, #6c418c, #9b59b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3em;
        margin-bottom: 20px;
    }

    /* Cards & Metrics */
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e9ecef; padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center !important; }
    div[data-testid="stMetricValue"] { color: #6c418c; direction: ltr; }
    
    .news-card { background-color: white; padding: 20px; border-radius: 12px; border-right: 5px solid #6c418c; border: 1px solid #e9ecef; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%; display: flex; flex-direction: column; justify-content: space-between; }
    .news-title { font-weight: 700; font-size: 1.1em; color: #2c3e50; margin-bottom: 10px; direction: rtl; text-align: right; }
    .news-meta { font-size: 0.85em; color: #95a5a6; direction: rtl; text-align: right; margin-bottom: 15px; }
    .news-link { color: #6c418c; font-weight: 600; font-size: 0.9em; align-self: flex-start; direction: rtl; }

    .info-card { background-color: #ffffff; padding: 30px; border-radius: 15px; border: 1px solid #e9ecef; box-shadow: 0 5px 15px rgba(0,0,0,0.03); height: 100%; text-align: right; }
    .info-card:hover { transform: translateY(-5px); border-bottom: 4px solid #6c418c; }
    
    /* Buttons */
    .stButton>button { background-color: #6c418c; color: white; border-radius: 10px; border: none; width: 100%; font-weight: 600; padding: 12px 20px; box-shadow: 0 4px 6px rgba(108, 65, 140, 0.2); }
    .stButton>button:hover { background-color: #512e6b; }

    /* Hide Elements */
    [data-testid="stExpanderToggleIcon"] { display: none; }
    .streamlit-expanderHeader { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; color: #6c418c; font-weight: bold; }
    
    /* Footer */
    .footer { margin-top: 100px; padding: 40px 20px; border-top: 1px solid #e9ecef; background: #ffffff; color: #7f8c8d; text-align: center !important; display: block !important; }
    .footer p { text-align: center !important; width: 100%; }
    
    /* Status Badge */
    .status-badge { font-size: 0.8em; padding: 2px 8px; border-radius: 4px; display: inline-block; margin-bottom: 5px; }
    .status-live { background-color: #d4edda; color: #155724; }
    .status-cached { background-color: #fff3cd; color: #856404; }

    /* Mobile Adjustments */
    @media (max-width: 768px) {
        .hero-title { font-size: 2.5em !important; }
        .hero-subtitle { font-size: 1.1em !important; margin-bottom: 30px; }
        .dashboard-title { font-size: 2em !important; }
        div[data-testid="stMetric"] { padding: 10px !important; margin-bottom: 10px; }
        .info-card { padding: 15px; margin-bottom: 10px; }
        .stButton>button { padding: 8px 10px; font-size: 0.9em; }
    }
</style>
""", unsafe_allow_html=True)

# --- קבועים ---
PORTFOLIOS = {
    "Conservative": { "AGG": 0.60, "VNQ": 0.20, "^GSPC": 0.20 },
    "Balanced": { "^GSPC": 0.50, "VNQ": 0.20, "EIS": 0.15, "AGG": 0.15 },
    "Aggressive": { "QQQ": 0.45, "^GSPC": 0.35, "BTC-USD": 0.20 }
}

ASSET_NAMES = {
    "^GSPC": "S&P 500 (מדד השוק)",
    "QQQ": "Nasdaq 100 (טכנולוגיה)",
    "VNQ": "נדל\"ן מניב (REITs)",
    "BTC-USD": "Bitcoin (קריפטו)",
    "EIS": "מדד ת\"א/ישראל",
    "AGG": "אג\"ח ממשלתי (סולידי)"
}

# --- חיבור לדאטה בייס ---
def init_connection():
    return mysql.connector.connect(**st.secrets["mysql"], use_pure=True)

# --- ולידציה ---
def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def validate_password(password):
    # מינימום 8 תווים, אות אחת לפחות, ספרה אחת לפחות
    return re.match(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{8,}$", password)

def validate_username(username):
    return re.match(r"^[a-zA-Z0-9_]+$", username)

# --- ניהול Cache (LKG - Last Known Good) ---
def save_lkg_to_db(key, data):
    """שומר את המידע העדכני ביותר בטבלת הגיבוי בדאטה-בייס"""
    try:
        conn = init_connection()
        cursor = conn.cursor()
        
        # המרה ל-JSON (אם זה DataFrame משתמשים בפונקציה ייעודית)
        if isinstance(data, pd.DataFrame):
            payload = data.to_json(orient='split', date_format='iso')
        else:
            payload = json.dumps(data)
            
        sql = """
            INSERT INTO market_cache (cache_key, data_payload) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE data_payload = VALUES(data_payload), updated_at = NOW()
        """
        cursor.execute(sql, (key, payload))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"LKG Save Warning: {e}")

def load_lkg_from_db(key, is_dataframe=False):
    """טוען מידע מטבלת הגיבוי אם הרשת נפלה"""
    try:
        conn = init_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT data_payload FROM market_cache WHERE cache_key = %s", (key,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            payload = result[0]
            if is_dataframe:
                return pd.read_json(StringIO(payload), orient='split')
            else:
                return json.loads(payload)
    except Exception as e:
        print(f"LKG Load Warning: {e}")
    return None

# --- שליפת נתונים עם מנגנון שרידות ---
@st.cache_data(ttl=600)
def get_current_prices():
    """מושך מחירים. מנסה יאהו -> אם נכשל מנסה DB -> אם נכשל מחזיר ברירת מחדל"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    tickers = {
        "^GSPC": "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?interval=1d&range=1d",
        "BTC": "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=1d&range=1d",
        "VNQ": "https://query1.finance.yahoo.com/v8/finance/chart/VNQ?interval=1d&range=1d", 
        "IXIC": "https://query1.finance.yahoo.com/v8/finance/chart/^IXIC?interval=1d&range=1d"
    }
    
    prices = {}
    is_live = True
    
    try:
        for key, url in tickers.items():
            r = requests.get(url, headers=headers, timeout=3) # Timeout קצר
            r.raise_for_status()
            data = r.json()
            prices[key] = data['chart']['result'][0]['meta']['regularMarketPrice']
        
        # הצלחה - שומרים ל-LKG
        save_lkg_to_db("current_prices", prices)
        
    except (RequestException, Timeout, ValueError):
        # כישלון - מנסים לטעון LKG
        is_live = False
        cached_prices = load_lkg_from_db("current_prices")
        if cached_prices:
            prices = cached_prices
        else:
            # Fallback אחרון למניעת קריסה
            prices = {"^GSPC": 0, "BTC": 0, "VNQ": 0, "IXIC": 0}

    return prices, is_live

@st.cache_data(ttl=3600)
def get_historical_data_for_chart():
    """מושך היסטוריה לגרף. מנגנון LKG מלא"""
    is_live = True
    df_combined = pd.DataFrame()

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        tickers_config = {
            "S&P 500": "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?interval=1mo&range=5y",
            "קריפטו (BTC)": "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=1mo&range=5y",
            "נדל\"ן (VNQ)": "https://query1.finance.yahoo.com/v8/finance/chart/VNQ?interval=1mo&range=5y"
        }
        
        for name, url in tickers_config.items():
            r = requests.get(url, headers=headers, timeout=5)
            r.raise_for_status()
            data = r.json()
            timestamps = data['chart']['result'][0]['timestamp']
            prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
            dates = [datetime.fromtimestamp(ts) for ts in timestamps]
            df_temp = pd.DataFrame({'Date': dates, name: prices})
            df_temp.set_index('Date', inplace=True)
            
            # נירמול לאחוזים
            start_price = df_temp[name].iloc[0]
            df_temp[name] = ((df_temp[name] / start_price) - 1) * 100
            
            if df_combined.empty: df_combined = df_temp
            else: df_combined = df_combined.join(df_temp, how='outer')
            
        df_final = df_combined.ffill().dropna()
        save_lkg_to_db("history_chart", df_final)
        return df_final, True

    except Exception:
        is_live = False
        cached_df = load_lkg_from_db("history_chart", is_dataframe=True)
        if cached_df is not None:
            return cached_df, False
        
        # Fallback בסיסי כדי שהגרף יוצג (אפילו אם ריק)
        dates = pd.date_range(end=datetime.today(), periods=10, freq='ME')
        return pd.DataFrame(index=dates, columns=["S&P 500", "קריפטו (BTC)", "נדל\"ן (VNQ)"]).fillna(0), False

@st.cache_data(ttl=1800)
def get_latest_news():
    is_live = True
    news_list = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://query2.finance.yahoo.com/v1/finance/search?q=^GSPC&newsCount=3"
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        if 'news' in data:
            for item in data['news'][:3]:
                news_list.append({
                    'title': item.get('title', 'No Title'),
                    'link': item.get('link', '#'),
                    'publisher': item.get('publisher', 'Yahoo Finance'),
                    'date': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime('%d/%m %H:%M')
                })
        save_lkg_to_db("news_list", news_list)
        return news_list, True
    except Exception:
        cached_news = load_lkg_from_db("news_list")
        return (cached_news if cached_news else []), False

# --- מנוע חישוב ---
@st.cache_data(ttl=3600)
def calculate_portfolio_stats(portfolio_mix):
    # כאן משתמשים בנתונים סטטיסטיים כלליים אם נכשלים, אין צורך ב-DB כבד לזה
    headers = {'User-Agent': 'Mozilla/5.0'}
    total_avg_win = 0
    total_avg_loss = 0
    total_p_win = 0
    valid_assets = 0
    
    fallback_stats = {"p_win": 0.65, "avg_win": 0.15, "avg_loss": -0.07}

    for ticker, weight in portfolio_mix.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1mo&range=10y"
        try:
            r = requests.get(url, headers=headers, timeout=3)
            r.raise_for_status()
            data = r.json()
            prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
            yearly_returns = []
            for i in range(12, len(prices), 12):
                if prices[i-12] > 0:
                    yearly_returns.append((prices[i] - prices[i-12]) / prices[i-12])
            
            if yearly_returns:
                yr = np.array(yearly_returns)
                wins = yr[yr > 0]
                losses = yr[yr <= 0]
                p_win = len(wins) / len(yr)
                avg_win = wins.mean() if len(wins) > 0 else 0
                avg_loss = losses.mean() if len(losses) > 0 else 0
                total_p_win += p_win * weight
                total_avg_win += avg_win * weight
                total_avg_loss += avg_loss * weight
                valid_assets += 1
        except Exception:
            total_p_win += fallback_stats["p_win"] * weight
            total_avg_win += fallback_stats["avg_win"] * weight
            total_avg_loss += fallback_stats["avg_loss"] * weight
            valid_assets += 1

    if valid_assets == 0: 
        return {"p_win": 0.7, "p_loss": 0.3, "avg_win": 0.12, "avg_loss": -0.05}
    
    return {"p_win": total_p_win, "p_loss": 1 - total_p_win, "avg_win": total_avg_win, "avg_loss": total_avg_loss}

def generate_decision_tree_portfolio(amount, portfolio_name, stats):
    dot = graphviz.Digraph(comment='Decision Tree')
    dot.attr(rankdir='TB', bgcolor='transparent')
    dot.attr('node', shape='box', style='filled', fillcolor='white', fontname="Heebo", color="#6c418c")
    dot.attr('edge', fontname="Heebo", color="#2c3e50")

    dot.node('A', f'התחלה\nסכום: ₪{amount:,}')
    dot.node('B', f'הרכב תיק נבחר\n{portfolio_name}', fillcolor="#e8f8f5")
    dot.edge('A', 'B')

    dot.node('D', 'סימולציה סטטיסטית\n(שקלול 10 שנים)', shape='diamond', fillcolor='#fff')
    dot.edge('B', 'D')

    win_amount = amount * (1 + stats['avg_win'])
    dot.node('E', f'תרחיש חיובי\nתשואה ממוצעת: {(stats["avg_win"]*100):.1f}%\nשווי: ₪{win_amount:,.0f}', fillcolor='#d5f5e3')
    dot.edge('D', 'E', label=f' {stats["p_win"]*100:.0f}% סבירות ')

    loss_amount = amount * (1 + stats['avg_loss'])
    dot.node('F', f'תרחיש שלילי\nתשואה ממוצעת: {(stats["avg_loss"]*100):.1f}%\nשווי: ₪{loss_amount:,.0f}', fillcolor='#fadbd8')
    dot.edge('D', 'F', label=f' {stats["p_loss"]*100:.0f}% סבירות ')

    expected_val = (win_amount * stats['p_win']) + (loss_amount * stats['p_loss'])
    net_profit = expected_val - amount
    final_color = "#abebc6" if net_profit > 0 else "#f5b7b1"
    dot.node('G', f'שווי הוגן (תוחלת)\n₪{expected_val:,.0f}\n(רווח משוקלל: ₪{net_profit:,.0f})', style='filled,bold', fillcolor=final_color)
    
    dot.edge('E', 'G')
    dot.edge('F', 'G')

    return dot, expected_val

def save_simulation_db(user_id, amount, risk, field, net_ev, mode, years, portfolio_mix, stats):
    try:
        conn = init_connection()
        cursor = conn.cursor()
        
        # המרה ל-JSON string כדי לשמור בדאטה-בייס
        portfolio_json = json.dumps(portfolio_mix)
        stats_json = json.dumps(stats)
        
        # שאילתה מעודכנת עם העמודות החדשות
        sql = """
            INSERT INTO investments 
            (user_id, amount, risk_level, field_chosen, expected_net_value, selection_mode, investment_years, portfolio_composition, simulation_stats) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (user_id, amount, risk, field, net_ev, mode, years, portfolio_json, stats_json))
        conn.commit()
        conn.close()
    except Exception as e: 
        st.error("שגיאה בשמירת הנתונים")
        print(f"DB Error: {e}")

# --- ניהול משתמשים (כולל שכחתי סיסמה) ---
def login_user(username, password):
    try:
        conn = init_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE username = %s"
        cursor.execute(query, (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            user['full_name'] = f"{user['first_name']} {user['last_name']}"
            return user
        return None
    except Exception as e: 
        print(f"Login Error: {e}")
        return None

def register_user(first_name, last_name, email, username, password):
    try:
        conn = init_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            conn.close()
            return False, "שם המשתמש או האימייל כבר תפוסים במערכת"
        
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        sql = "INSERT INTO users (first_name, last_name, email, username, password) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (first_name, last_name, email, username, hashed_pw.decode('utf-8')))
        
        conn.commit()
        conn.close()
        return True, "המשתמש נוצר בהצלחה! ניתן להתחבר."
    except Exception as e: 
        return False, f"שגיאה: {e}"

def reset_user_password(username, email, new_password):
    """פונקציה לאיפוס סיסמה"""
    try:
        conn = init_connection()
        cursor = conn.cursor()
        
        # 1. בדיקה שהמשתמש קיים והאימייל תואם
        cursor.execute("SELECT * FROM users WHERE username = %s AND email = %s", (username, email))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return False, "הפרטים אינם תואמים למשתמש קיים"
            
        # 2. הצפנת הסיסמה החדשה
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # 3. עדכון הסיסמה בבסיס הנתונים (user[0] הוא ה-ID)
        update_query = "UPDATE users SET password = %s WHERE id = %s"
        cursor.execute(update_query, (hashed_pw.decode('utf-8'), user[0])) 
        
        conn.commit()
        conn.close()
        return True, "הסיסמה שונתה בהצלחה! עכשיו אפשר להתחבר."
    except Exception as e:
        return False, f"שגיאה: {e}"

# --- UI Helper ---
def display_data_status(is_live):
    if not is_live:
        st.markdown('<span class="status-badge status-cached">⚠️ מוצג מידע שמור (עדכון חי לא זמין כרגע)</span>', unsafe_allow_html=True)
    else:
        # אפשר להציג אינדיקטור ירוק או לא להציג כלום
        pass

# --- ניווט ---
if 'page' not in st.session_state: st.session_state['page'] = 'home'
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
def go_to_login(): st.session_state['page'] = 'login'
def go_to_register(): st.session_state['page'] = 'register'
def go_to_home(): st.session_state['page'] = 'home'

# --- 1. דף הבית ---
def home_page():
    col_spacer, col_btns = st.columns([6, 2]) 
    with col_btns:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔑 כניסה", width="stretch", key="home_login"): go_to_login(); st.rerun()
        with c2:
            if st.button("🚀 הירשמו", width="stretch", key="home_reg"): go_to_register(); st.rerun()

    st.markdown('<div class="hero-title">InvestWise</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">הפכו את קבלת ההחלטות הפיננסיות לפשוטה וחכמה</div>', unsafe_allow_html=True)
    
    prices, is_live_prices = get_current_prices()
    display_data_status(is_live_prices)

    st.write("---")
    cols = st.columns(4)
    metrics_data = [
        ("מדד S&P 500", f"${prices.get('^GSPC', 0):,.2f}"),
        ("ביטקוין (BTC)", f"${prices.get('BTC', 0):,.0f}"),
        ("מדד נדל\"ן (VNQ)", f"${prices.get('VNQ', 0):,.2f}"),
        ("מדד נאסד\"ק", f"${prices.get('IXIC', 0):,.2f}")
    ]
    
    for i, col in enumerate(cols):
        col.metric(metrics_data[i][0], metrics_data[i][1])
        
    st.write("---")

    st.subheader("📰 עדכונים חמים מהשווקים")
    news_items, is_live_news = get_latest_news()
    if not is_live_news and news_items:
        st.caption("חדשות שמורות (לא התקבלו עדכונים חדשים)")
    
    if news_items:
        cols = st.columns(3)
        for i, item in enumerate(news_items):
            with cols[i]:
                st.markdown(f"""
                <div class="news-card">
                    <div>
                        <div class="news-title">{item['title']}</div>
                        <div class="news-meta">{item['date']} | {item['publisher']}</div>
                    </div>
                    <a href="{item['link']}" target="_blank" class="news-link">לקריאת הכתבה ⬅</a>
                </div>
                """, unsafe_allow_html=True)
    else: 
        st.info("לא נמצאו עדכונים זמינים.")

    st.write("---")
    
    main_text, chart_col = st.columns([1, 1.5]) 
    with main_text:
        st.markdown("### 💡 למה הכסף שלכם צריך לעבוד?")
        st.write("בעולם שבו האינפלציה שוחקת את ערך הכסף, השקעה חכמה היא הדרך היחידה לשמור על כוח הקנייה.")
        st.markdown("### ⚠️ האתגר: הצפת מידע")
        st.write("היום קל מאוד לקנות מניות, אבל קשה לדעת **מה** לקנות. הכלים הקיימים מסובכים מידי.")
        st.markdown("### ✅ הפתרון של InvestWise")
        st.write("אנחנו מנגישים לכם כלי אנליטי שמבוסס על **עץ החלטות** וסטטיסטיקה.")

    with chart_col:
        st.markdown("##### 📊 השוואת תשואות מנורמלות (5 שנים אחרונות)")
        chart_data, is_live_chart = get_historical_data_for_chart()
        if not is_live_chart:
            st.caption("⚠️ מוצגים נתונים היסטוריים שמורים")
        st.line_chart(chart_data, color=["#6c418c", "#f1c40f", "#27ae60"])

    st.write("---")
    
    st.header("🌍 עולם ההשקעות שלנו")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""<div class="info-card"><h2 style="color:#6c418c; margin:0;">📈</h2><h3>שוק ההון</h3><p>השקעה בחברות הגדולות והחזקות במשק. אפיק עם נזילות גבוהה ופוטנציאל צמיחה.</p></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""<div class="info-card"><h2 style="color:#27ae60; margin:0;">🏠</h2><h3>נדל"ן</h3><p>השקעה בנכסים מוחשיים וקרקעות. אפיק יציב יחסית ופחות תנודתי.</p></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""<div class="info-card"><h2 style="color:#f1c40f; margin:0;">₿</h2><h3>קריפטו</h3><p>השקעה במטבעות דיגיטליים. שוק חדשני עם תנודתיות קיצונית ופוטנציאל רווח גבוה.</p></div>""", unsafe_allow_html=True)

    st.write("")
    
    st.subheader("❓ שאלות נפוצות")
    st.markdown('<div class="faq-question">האם השימוש במערכת עולה כסף?</div><div class="faq-answer">ההרשמה למערכת ושימוש בסיסי הם בחינם.</div>', unsafe_allow_html=True)
    st.markdown('<div class="faq-question">על מה מבוססות ההמלצות?</div><div class="faq-answer">ההמלצות מבוססות על מודל מתמטי (עץ החלטות) המשקלל נתוני עבר.</div>', unsafe_allow_html=True)
    st.markdown('<div class="faq-question">האם המידע שלי מאובטח?</div><div class="faq-answer">בהחלט. המידע נשמר בצורה מאובטחת בשרתים שלנו.</div>', unsafe_allow_html=True)

    # Footer
    st.markdown("""
    <div class="footer">
        <p style="font-size: 1.1em; color: #2c3e50;">© 2025 InvestWise | כל הזכויות שמורות</p>
        <p class="footer-names">מייסדים: יוגב בוסידן, שירה שחר | מנהלי פיתוח: ליאור קימה, אברהם מועלם</p>
        <p class="footer-vision">"להפוך כל חולם למשקיע, וכל משקיע למקצוען - באמצעות נתונים וטכנולוגיה."</p>
    </div>
    """, unsafe_allow_html=True)

# --- דפים משניים (לוגין + שכחתי סיסמה) ---
def login_page():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br><h1 style='text-align:center;'>👋 ברוכים השבים</h1>", unsafe_allow_html=True)
        
        # --- ניהול מצב: האם להציג טופס איפוס או התחברות? ---
        if 'show_reset' not in st.session_state:
            st.session_state['show_reset'] = False

        if not st.session_state['show_reset']:
            # === טופס התחברות רגיל ===
            with st.form("login_form"):
                username = st.text_input("שם משתמש")
                password = st.text_input("סיסמה", type="password")
                st.write("")
                if st.form_submit_button("התחבר עכשיו", width="stretch"): 
                    user = login_user(username, password)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user
                        st.success("התחברת בהצלחה!"); time.sleep(1); st.rerun()
                    else: st.error("שם משתמש או סיסמה שגויים")
            
            # כפתור מעבר לאיפוס סיסמה
            if st.button("שכחתי סיסמה?", key="btn_forgot"):
                st.session_state['show_reset'] = True
                st.rerun()
                
            st.write("")
            if st.button("חזרה לדף הבית", width="stretch", key="login_back"): go_to_home(); st.rerun()

        else:
            # === טופס איפוס סיסמה ===
            st.warning("🔒 איפוס סיסמה")
            with st.form("reset_form"):
                st.caption("אנא הזן את פרטי הזיהוי שלך לאימות:")
                r_username = st.text_input("שם המשתמש שאיתו נרשמת")
                r_email = st.text_input("האימייל שאיתו נרשמת")
                new_pass = st.text_input("סיסמה חדשה", type="password")
                
                st.write("")
                if st.form_submit_button("אפס סיסמה", width="stretch"):
                    if r_username and r_email and new_pass:
                        if validate_password(new_pass):
                            res, msg = reset_user_password(r_username, r_email, new_pass)
                            if res:
                                st.success(msg)
                                time.sleep(2)
                                st.session_state['show_reset'] = False # חזרה ללוגין
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("הסיסמה החדשה חייבת להיות באורך 8 תווים לפחות ולכלול אות וספרה")
                    else:
                        st.warning("נא למלא את כל השדות")

            # כפתור ביטול וחזרה ללוגין
            if st.button("חזרה להתחברות", key="btn_cancel_reset"):
                st.session_state['show_reset'] = False
                st.rerun()

def register_page():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br><h1 style='text-align:center;'>🚀 יצירת חשבון</h1>", unsafe_allow_html=True)
        with st.form("register_form"):
            col_fname, col_lname = st.columns(2)
            with col_fname:
                first_name = st.text_input("שם פרטי")
            with col_lname:
                last_name = st.text_input("שם משפחה")
            
            email = st.text_input("אימייל")
            new_user = st.text_input("שם משתמש (באנגלית)")
            new_pass = st.text_input("סיסמה", type="password", help="מינימום 8 תווים, כולל אות וספרה")
            
            st.write("")
            if st.form_submit_button("צור חשבון", width="stretch"): 
                if not (first_name and last_name and email and new_user and new_pass):
                    st.warning("נא למלא את כל שדות החובה")
                elif not validate_email(email):
                    st.error("כתובת אימייל לא תקינה")
                elif not validate_username(new_user):
                    st.error("שם משתמש חייב להכיל רק אותיות באנגלית ומספרים")
                elif not validate_password(new_pass):
                    st.error("הסיסמה חייבת להיות באורך 8 תווים לפחות ולכלול אות וספרה")
                else:
                    res, msg = register_user(first_name, last_name, email, new_user, new_pass)
                    if res: st.success(msg); time.sleep(1); go_to_login(); st.rerun()
                    else: st.error(msg)
                    
        st.write("")
        if st.button("חזרה לדף הבית", width="stretch", key="reg_back"): go_to_home(); st.rerun()

# --- דף האפליקציה ---
def app_dashboard():
    user = st.session_state['user_info']
    
    c_right, c_left = st.columns([8, 1])
    with c_right:
        st.write(f"#### 👋 שלום, {user['full_name']}")
    with c_left:
        if st.button("יציאה", key="top_logout_btn"): 
            st.session_state['logged_in'] = False
            go_to_home()
            st.rerun()
    
    st.divider()
    st.markdown('<div class="dashboard-title">InvestWise</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🚀 בניית תיק השקעות", "📊 הפרופיל שלי"])

    with tab1:
        st.write("### המנוע החכם - בניית תיק מותאם אישית")
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            amount = st.number_input("סכום להשקעה (₪)", min_value=1000, value=50000, step=1000, key="main_amount_input")
        with c2:
            years = st.number_input("משך ההשקעה (שנים)", min_value=1, max_value=30, value=3, step=1, key="main_years_input")
        with c3:
            time_horizon = st.pills(
                "רמת סיכון (נגזרת מטווח הזמן):",
                options=["טווח קצר (סולידי)", "טווח בינוני (מאוזן)", "טווח ארוך (צמיחה)"],
                default="טווח בינוני (מאוזן)",
                key="main_risk_pills"
            )
            
            risk_mapping = {
                "טווח קצר (סולידי)": "Conservative",
                "טווח בינוני (מאוזן)": "Balanced",
                "טווח ארוך (צמיחה)": "Aggressive"
            }
            derived_risk = risk_mapping.get(time_horizon, "Balanced")

        st.write("---")
        
        col_auto, col_manual = st.columns(2)
        
        # --- ניהול זיכרון (State) לתצוגה בלבד ---
        # אנחנו נשמור את התוצאות בזיכרון כדי להציג אותן, אבל את השמירה לדאטה-בייס נעשה רק בלחיצה
        if 'display_results' not in st.session_state:
            st.session_state['display_results'] = None
        
        # === אפשרות 1: כפתור אוטומטי ===
        if col_auto.button("🤖 בנה לי תיק אוטומטית", type="primary", width="stretch", key="btn_auto"):
            # 1. חישובים
            selected_mix = PORTFOLIOS[derived_risk].copy()
            portfolio_name = f"תיק {derived_risk}"
            
            # איזון VNQ אם הסכום נמוך
            if amount < 100000 and "VNQ" in selected_mix:
                vnq_weight = selected_mix.pop("VNQ")
                if "^GSPC" in selected_mix: selected_mix["^GSPC"] += vnq_weight
                else: selected_mix["^GSPC"] = vnq_weight

            with st.spinner('מנתח נתונים ומחשב תחזיות...'):
                stats = calculate_portfolio_stats(selected_mix)
                
                # חישוב ערכים עתידיים
                future_value_optimistic = amount * ((1 + stats['avg_win']) ** years)
                future_value_pessimistic = amount * ((1 + stats['avg_loss']) ** years)
                expected_future_val = (future_value_optimistic * stats['p_win']) + (future_value_pessimistic * stats['p_loss'])
                
                # 2. שמירה לדאטה בייס (קורה פעם אחת בדיוק!)
                save_simulation_db(user['id'], amount, derived_risk, portfolio_name, expected_future_val, "auto", years, selected_mix, stats)
                
                # 3. שמירה לזיכרון לתצוגה
                st.session_state['display_results'] = {
                    'mix': selected_mix,
                    'stats': stats,
                    'name': portfolio_name,
                    'ev': expected_future_val,
                    'years': years,
                    'amount': amount
                }
                # איפוס מצב ידני
                st.session_state['manual_mode'] = False

        # === אפשרות 2: כפתור ידני ===
        if col_manual.button("🖐️ אני רוצה לבחור נכס בודד", width="stretch", key="btn_manual"):
            st.session_state['manual_mode'] = True
            st.session_state['display_results'] = None # מנקים תוצאות קודמות

        # תצוגת הבחירה הידנית
        if st.session_state.get('manual_mode') and st.session_state['display_results'] is None:
            st.write("### בחירה ידנית")
            chosen_asset_key = st.selectbox("בחר באיזה אפיק להתמקד:", list(ASSET_NAMES.keys()), format_func=lambda x: ASSET_NAMES[x], key="manual_asset_select")
            
            if st.button("נתח את הבחירה שלי", key="btn_analyze_manual", width="stretch"):
                # 1. חישובים
                selected_mix = {chosen_asset_key: 1.0}
                portfolio_name = f"תיק {ASSET_NAMES[chosen_asset_key]} (ידני)"
                
                with st.spinner('מנתח נתונים...'):
                    stats = calculate_portfolio_stats(selected_mix)
                    future_value_optimistic = amount * ((1 + stats['avg_win']) ** years)
                    future_value_pessimistic = amount * ((1 + stats['avg_loss']) ** years)
                    expected_future_val = (future_value_optimistic * stats['p_win']) + (future_value_pessimistic * stats['p_loss'])

                    # 2. שמירה לדאטה בייס (פעם אחת!)
                    save_simulation_db(user['id'], amount, derived_risk, portfolio_name, expected_future_val, "manual", years, selected_mix, stats)

                    # 3. שמירה לזיכרון לתצוגה
                    st.session_state['display_results'] = {
                        'mix': selected_mix,
                        'stats': stats,
                        'name': portfolio_name,
                        'ev': expected_future_val,
                        'years': years,
                        'amount': amount
                    }
                    st.session_state['manual_mode'] = False # סוגרים את התפריט הידני אחרי הבחירה
                    st.rerun()

        # === תצוגת התוצאות (קורא מהזיכרון) ===
        # החלק הזה רק מציג! הוא לא שומר כלום ל-DB
        if st.session_state['display_results']:
            res = st.session_state['display_results']
            
            st.divider()
            c_head, c_reset = st.columns([4, 1])
            c_head.subheader(f"📊 תוצאות הניתוח: {res['name']}")
            
            if c_reset.button("🔄 התחל מחדש", key="btn_reset"):
                st.session_state['display_results'] = None
                st.session_state['manual_mode'] = False
                st.rerun()
            
            col_visual, col_data = st.columns([1.2, 1])
            with col_data:
                st.markdown("#### 🍰 הרכב התיק")
                df_pie = pd.DataFrame(list(res['mix'].items()), columns=['Ticker', 'Weight'])
                df_pie['Asset Name'] = df_pie['Ticker'].map(ASSET_NAMES)
                fig = px.pie(df_pie, values='Weight', names='Asset Name', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(showlegend=True, height=250, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, width="stretch")
                
                st.markdown("---")
                # חישוב תשואה שנתית לתצוגה
                annualized_return = ((res['ev'] / res['amount']) ** (1/res['years'])) - 1
                total_profit = res['ev'] - res['amount']
                
                st.write(f"**צפי תשואה שנתית ממוצעת:** {annualized_return*100:.1f}%")
                st.success(f"**שווי מוערך בתום {res['years']} שנים:** ₪{res['ev']:,.0f}")
                color_txt = "green" if total_profit > 0 else "red"
                st.markdown(f"רווח משוקלל צפוי: :{color_txt}[**₪{total_profit:,.0f}**]")

            with col_visual:
                with st.expander("🔍 לחץ להצגת ניתוח עץ ההחלטות", expanded=False):
                    st.caption(f"התרשים מציג את ההתפלגות הסטטיסטית לשנה אחת (מתוך {res['years']}):")
                    tree_graph, _ = generate_decision_tree_portfolio(res['amount'], res['name'], res['stats'])
                    st.graphviz_chart(tree_graph)
                    st.info("העץ מציג הסתברויות על בסיס 10 שנות היסטוריה.")
    with tab2:
        st.header("📜 היסטוריית ההמלצות שלי")
        conn = init_connection()
        # שליפת כל המידע כולל ה-JSON
        query = "SELECT id, timestamp, amount, investment_years, risk_level, field_chosen, expected_net_value, selection_mode, portfolio_composition, simulation_stats FROM investments WHERE user_id=%(uid)s ORDER BY timestamp DESC"
        df = pd.read_sql(query, conn, params={"uid": user['id']})
        conn.close()

        if df.empty:
            st.info("עדיין אין לך השקעות שמורות. צור את ההשקעה הראשונה בטאב הראשון!")
        else:
            # תצוגת טבלה ראשית נקייה
            st.dataframe(
                df[['timestamp', 'amount', 'risk_level', 'field_chosen', 'expected_net_value']],
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("תאריך", format="DD/MM/YYYY HH:mm"),
                    "amount": st.column_config.NumberColumn("סכום השקעה", format="₪%d"),
                    "expected_net_value": st.column_config.NumberColumn("שווי חזוי", format="₪%d"),
                    "risk_level": "רמת סיכון",
                    "field_chosen": "שם התיק"
                },
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            st.subheader("🔍 שחזור השקעה")
            
            # יצירת רשימת בחירה נוחה למשתמש
            df['label'] = df.apply(lambda x: f"{x['timestamp']} | ₪{x['amount']:,} | {x['field_chosen']}", axis=1)
            selected_label = st.selectbox("בחר השקעה מהרשימה כדי לראות את הניתוח המלא שלה:", df['label'])
            
            # שליפת השורה הספציפית שנבחרה
            row = df[df['label'] == selected_label].iloc[0]
            
            # בדיקה האם יש מידע מורחב (עבור השקעות ישנות ייתכן שאין)
            if row['portfolio_composition'] and row['simulation_stats']:
                # המרת ה-JSON חזרה למילון פייתון
                # הערה: לפעמים MySQL מחזיר את זה כמילון ולפעמים כטקסט, הקוד הזה מטפל בשניהם
                p_mix = json.loads(row['portfolio_composition']) if isinstance(row['portfolio_composition'], str) else row['portfolio_composition']
                p_stats = json.loads(row['simulation_stats']) if isinstance(row['simulation_stats'], str) else row['simulation_stats']
                
                # --- שחזור התצוגה הגרפית ---
                h_col_visual, h_col_data = st.columns([1.2, 1])
                
                with h_col_data:
                    st.markdown("#### 🍰 הרכב התיק שנשמר")
                    df_pie = pd.DataFrame(list(p_mix.items()), columns=['Ticker', 'Weight'])
                    df_pie['Asset Name'] = df_pie['Ticker'].map(ASSET_NAMES)
                    fig = px.pie(df_pie, values='Weight', names='Asset Name', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                    fig.update_layout(showlegend=True, height=250, margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig, width="stretch")
                    
                    # נתונים מספריים
                    roi = ((row['expected_net_value'] / row['amount']) ** (1/row['investment_years'])) - 1
                    st.success(f"**צפי תשואה שנתית:** {roi*100:.1f}%")

                with h_col_visual:
                     st.markdown("#### 🌳 עץ ההחלטות (שחזור מלא)")
                     # שימוש בפונקציה הקיימת שלנו כדי לצייר מחדש את העץ
                     tree, _ = generate_decision_tree_portfolio(row['amount'], row['field_chosen'], p_stats)
                     st.graphviz_chart(tree)
                     st.caption(f"הנתונים נכונים לרגע ביצוע ההשקעה ({row['timestamp']})")
            else:
                st.warning("השקעה זו נוצרה לפני שדרוג המערכת ואין לה נתונים שמורים")

# --- נתב ראשי ---
if st.session_state['logged_in']: app_dashboard()
else:
    if st.session_state['page'] == 'home': home_page()
    elif st.session_state['page'] == 'login': login_page()
    elif st.session_state['page'] == 'register': register_page()