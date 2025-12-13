import streamlit as st
import mysql.connector
import pandas as pd
import time
import requests
import urllib3
import numpy as np
import graphviz 
import plotly.express as px
import warnings 
import bcrypt # ספרייה לאבטחת סיסמאות
from datetime import datetime, timedelta

# --- השתקת אזהרות ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# משתיק את האזהרה המציקה של פנדס
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

# --- הגדרות דף ---
st.set_page_config(page_title="InvestWise", layout="wide", page_icon="📈")

# --- הזרקת CSS (עיצוב Light Mode נקי) ---
st.markdown("""
<style>
    /* הגדרת כיוון כללית לכל האפליקציה */
    .stApp { 
        direction: rtl; 
        text-align: right; 
        background-color: #f8f9fa; 
        color: #2c3e50; 
    }
    
    /* יישור כפוי לימין לכל סוגי הטקסטים והכותרות */
    p, h1, h2, h3, h4, h5, h6, span, div, label {
        text-align: right !important;
        font-family: 'Heebo', sans-serif !important;
    }

    /* תיקון ספציפי לקלטים (Inputs) שנוטים לברוח שמאלה */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        direction: rtl;
        text-align: right;
    }
    
    /* Hero */
    .hero-title {
        text-align: center !important; /* הכותרת הראשית נשארת במרכז */
        background: -webkit-linear-gradient(45deg, #6c418c, #9b59b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 4.5em;
        margin-bottom: 0px;
        text-shadow: 0px 2px 5px rgba(108, 65, 140, 0.1);
    }
    .hero-subtitle { text-align: center !important; color: #7f8c8d; font-size: 1.4em; font-weight: 400; margin-top: 5px; margin-bottom: 50px; }

    /* כותרת מוקטנת לדשבורד */
    .dashboard-title {
        text-align: center !important;
        background: -webkit-linear-gradient(45deg, #6c418c, #9b59b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3em;
        margin-bottom: 20px;
    }

    /* כרטיסים */
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e9ecef; padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center !important; }
    div[data-testid="stMetricValue"] { color: #6c418c; direction: ltr; } /* מספרים עדיף שישארו LTR כדי לא להתהפך */
    
    .news-card { background-color: white; padding: 20px; border-radius: 12px; border-right: 5px solid #6c418c; border: 1px solid #e9ecef; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%; display: flex; flex-direction: column; justify-content: space-between; }
    .news-title { font-weight: 700; font-size: 1.1em; color: #2c3e50; margin-bottom: 10px; direction: rtl; text-align: right; }
    .news-meta { font-size: 0.85em; color: #95a5a6; direction: rtl; text-align: right; margin-bottom: 15px; }
    .news-link { color: #6c418c; font-weight: 600; font-size: 0.9em; align-self: flex-start; direction: rtl; }

    .info-card { background-color: #ffffff; padding: 30px; border-radius: 15px; border: 1px solid #e9ecef; box-shadow: 0 5px 15px rgba(0,0,0,0.03); height: 100%; text-align: right; }
    .info-card:hover { transform: translateY(-5px); border-bottom: 4px solid #6c418c; }
    
    /* כפתורים */
    .stButton>button { background-color: #6c418c; color: white; border-radius: 10px; border: none; width: 100%; font-weight: 600; padding: 12px 20px; box-shadow: 0 4px 6px rgba(108, 65, 140, 0.2); }
    .stButton>button:hover { background-color: #512e6b; }

    /* הסתרת אלמנטים */
    [data-testid="stExpanderToggleIcon"] { display: none; }
    .streamlit-expanderHeader { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; color: #6c418c; font-weight: bold; }
    
    /* סרגל עליון אישי */
    .user-header { font-size: 1.2em; color: #2c3e50; font-weight: bold; text-align: right; }

    /* פוטר */
    .footer { margin-top: 100px; padding: 40px 20px; border-top: 1px solid #e9ecef; text-align: center !important; background: #ffffff; color: #7f8c8d; }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- הגדרת תיקי השקעות (Portfolios) ---
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

# --- חיבור לדאטה בייס (Production) ---
def init_connection():
    # use_pure=True פותר את בעיית ה-DLL בווינדוס ומבטיח תאימות לענן
    return mysql.connector.connect(**st.secrets["mysql"], use_pure=True)

# --- פונקציות עזר לדף הבית ---
@st.cache_data(ttl=600)
def get_current_prices():
    headers = {'User-Agent': 'Mozilla/5.0'}
    prices = {"^GSPC": 0, "BTC": 0, "VNQ": 0, "IXIC": 0}
    tickers = {
        "^GSPC": "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?interval=1d&range=1d",
        "BTC": "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=1d&range=1d",
        "VNQ": "https://query1.finance.yahoo.com/v8/finance/chart/VNQ?interval=1d&range=1d", 
        "IXIC": "https://query1.finance.yahoo.com/v8/finance/chart/^IXIC?interval=1d&range=1d"
    }
    for key, url in tickers.items():
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=5)
            data = r.json()
            prices[key] = data['chart']['result'][0]['meta']['regularMarketPrice']
        except: pass
    return prices

@st.cache_data(ttl=3600)
def get_historical_data_for_chart():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        tickers_config = {
            "S&P 500": "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?interval=1mo&range=5y",
            "קריפטו (BTC)": "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=1mo&range=5y",
            "נדל\"ן (VNQ)": "https://query1.finance.yahoo.com/v8/finance/chart/VNQ?interval=1mo&range=5y"
        }
        df_combined = pd.DataFrame()
        for name, url in tickers_config.items():
            r = requests.get(url, headers=headers, verify=False, timeout=5)
            data = r.json()
            timestamps = data['chart']['result'][0]['timestamp']
            prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
            dates = [datetime.fromtimestamp(ts) for ts in timestamps]
            df_temp = pd.DataFrame({'Date': dates, name: prices})
            df_temp.set_index('Date', inplace=True)
            start_price = df_temp[name].iloc[0]
            df_temp[name] = ((df_temp[name] / start_price) - 1) * 100
            if df_combined.empty: df_combined = df_temp
            else: df_combined = df_combined.join(df_temp, how='outer')
        return df_combined.ffill().dropna()
    except:
        dates = pd.date_range(end=datetime.today(), periods=60, freq='ME')
        df_backup = pd.DataFrame(index=dates)
        df_backup["S&P 500"] = np.linspace(0, 60, 60) + np.random.normal(0, 2, 60)
        df_backup["קריפטו (BTC)"] = np.linspace(0, 200, 60) + np.random.normal(0, 15, 60)
        df_backup["נדל\"ן (VNQ)"] = np.linspace(0, 25, 60) + np.random.normal(0, 3, 60)
        return df_backup

@st.cache_data(ttl=1800)
def get_latest_news():
    headers = {'User-Agent': 'Mozilla/5.0'}
    news_list = []
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search?q=^GSPC&newsCount=3"
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        data = r.json()
        if 'news' in data:
            for item in data['news'][:3]:
                news_list.append({
                    'title': item.get('title', 'No Title'),
                    'link': item.get('link', '#'),
                    'publisher': item.get('publisher', 'Yahoo Finance'),
                    'date': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime('%d/%m %H:%M')
                })
        return news_list
    except: return []

# --- מנוע חישוב משוקלל לתיק ---
@st.cache_data(ttl=3600)
def calculate_portfolio_stats(portfolio_mix):
    headers = {'User-Agent': 'Mozilla/5.0'}
    total_avg_win = 0
    total_avg_loss = 0
    total_p_win = 0
    valid_assets = 0
    
    for ticker, weight in portfolio_mix.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1mo&range=10y"
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=3)
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
        except: continue

    if valid_assets == 0: return {"p_win": 0.7, "p_loss": 0.3, "avg_win": 0.12, "avg_loss": -0.05}
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

def save_simulation_db(user_id, amount, risk, field, net_ev, mode, years):
    try:
        conn = init_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO investments (user_id, amount, risk_level, field_chosen, expected_net_value, selection_mode, investment_years) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(sql, (user_id, amount, risk, field, net_ev, mode, years))
        conn.commit()
        conn.close()
    except Exception as e: print(f"DB Error: {e}")

# --- ניהול משתמשים (כולל אבטחה והצפנה) ---
def login_user(username, password):
    try:
        conn = init_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE username = %s"
        cursor.execute(query, (username,))
        user = cursor.fetchone()
        conn.close()
        
        # בדיקת סיסמה מוצפנת + יצירת שם מלא לתצוגה
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
        
        # בדיקה האם המשתמש או האימייל תפוסים
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            conn.close()
            return False, "שם המשתמש או האימייל כבר תפוסים במערכת"
        
        # הצפנת סיסמה
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        sql = "INSERT INTO users (first_name, last_name, email, username, password) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (first_name, last_name, email, username, hashed_pw.decode('utf-8')))
        
        conn.commit()
        conn.close()
        return True, "המשתמש נוצר בהצלחה! ניתן להתחבר."
    except Exception as e: 
        return False, f"שגיאה: {e}"

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
            if st.button("🚀 הירשמו והתחילו ניתוח תיק חינם ", width="stretch", key="home_reg"): go_to_register(); st.rerun()

    st.markdown('<div class="hero-title">InvestWise</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">הפכו את קבלת ההחלטות הפיננסיות לפשוטה וחכמה</div>', unsafe_allow_html=True)
    
    prices = get_current_prices()
    st.write("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("מדד S&P 500", f"${prices['^GSPC']:,.2f}")
    m2.metric("ביטקוין (BTC)", f"${prices['BTC']:,.0f}")
    m3.metric("מדד נדל\"ן (VNQ)", f"${prices['VNQ']:,.2f}")
    m4.metric("מדד נאסד\"ק", f"${prices['IXIC']:,.2f}")
    st.write("---")

    st.subheader("📰 עדכונים חמים מהשווקים")
    news_items = get_latest_news()
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
    else: st.info("טוען חדשות...")

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
        st.markdown("##### 📊 השוואת תשואות (5 שנים אחרונות - באחוזים)")
        chart_data = get_historical_data_for_chart()
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

# --- דפים משניים (לוגין והרשמה מעודכנים) ---
def login_page():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br><h1 style='text-align:center;'>👋 ברוכים השבים</h1>", unsafe_allow_html=True)
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
        st.write("")
        if st.button("חזרה לדף הבית", width="stretch", key="login_back"): go_to_home(); st.rerun()

def register_page():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br><h1 style='text-align:center;'>🚀 יצירת חשבון</h1>", unsafe_allow_html=True)
        with st.form("register_form"):
            # פיצול לשתי עמודות עבור השם
            col_fname, col_lname = st.columns(2)
            with col_fname:
                first_name = st.text_input("שם פרטי")
            with col_lname:
                last_name = st.text_input("שם משפחה")
            
            email = st.text_input("אימייל")
            new_user = st.text_input("שם משתמש (באנגלית)")
            new_pass = st.text_input("סיסמה", type="password")
            
            st.write("")
            if st.form_submit_button("צור חשבון", width="stretch"):
                # שליחת כל הפרטים לפונקציה החדשה
                if first_name and last_name and email and new_user and new_pass:
                    res, msg = register_user(first_name, last_name, email, new_user, new_pass)
                    if res: st.success(msg); time.sleep(1); go_to_login(); st.rerun()
                    else: st.error(msg)
                else: st.warning("נא למלא את כל שדות החובה")
        st.write("")
        if st.button("חזרה לדף הבית", width="stretch", key="reg_back"): go_to_home(); st.rerun()

# --- דף האפליקציה (ללא Sidebar) ---
def app_dashboard():
    user = st.session_state['user_info']
    
    # בר עליון נקי
    c_right, c_left = st.columns([8, 1])
    with c_right:
        st.write(f"#### 👋 שלום, {user['full_name']}")
    with c_left:
        # כפתור יציאה
        if st.button("יציאה", key="top_logout_btn"): 
            st.session_state['logged_in'] = False
            go_to_home()
            st.rerun()
    
    st.divider()

    # כותרת מוקטנת
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
        
        if 'analysis_done' not in st.session_state:
            st.session_state['analysis_done'] = False
        
        mode = None
        selected_mix = None
        portfolio_name = ""
        
        # כפתורים
        if col_auto.button("🤖 בנה לי תיק אוטומטית", type="primary", width="stretch", key="btn_auto"):
            st.session_state['manual_mode'] = False 
            st.session_state['analysis_done'] = True
            st.session_state['current_mode'] = "auto"
            
        if col_manual.button("🖐️ אני רוצה לבחור נכס בודד (ידני)", width="stretch", key="btn_manual"):
            st.session_state['manual_mode'] = True
            st.session_state['analysis_done'] = False
            st.session_state['current_mode'] = "manual"
        
        if st.session_state.get('current_mode') == 'auto':
            selected_mix = PORTFOLIOS[derived_risk].copy()
            portfolio_name = f"תיק {derived_risk} (אוטומטי)"
            if amount < 100000 and "VNQ" in selected_mix:
                vnq_weight = selected_mix.pop("VNQ")
                if "^GSPC" in selected_mix: selected_mix["^GSPC"] += vnq_weight
                else: selected_mix["^GSPC"] = vnq_weight

        if st.session_state.get('manual_mode'):
            st.write("### בחירה ידנית")
            chosen_asset_key = st.selectbox("בחר באיזה אפיק להתמקד:", list(ASSET_NAMES.keys()), format_func=lambda x: ASSET_NAMES[x], key="manual_asset_select")
            if st.button("נתח את הבחירה שלי", key="btn_analyze_manual", width="stretch"):
                st.session_state['analysis_done'] = True
                st.session_state['manual_asset'] = chosen_asset_key

            if st.session_state.get('analysis_done') and st.session_state.get('current_mode') == 'manual':
                asset = st.session_state.get('manual_asset', chosen_asset_key)
                selected_mix = {asset: 1.0}
                portfolio_name = f"תיק {ASSET_NAMES[asset]} (ידני)"

        if st.session_state.get('analysis_done') and selected_mix:
            st.divider()
            c_head, c_reset = st.columns([4, 1])
            c_head.subheader(f"📊 תוצאות הניתוח: {portfolio_name}")
            if c_reset.button("🔄 התחל מחדש", key="btn_reset"):
                st.session_state['analysis_done'] = False
                st.session_state['manual_mode'] = False
                st.rerun()
            
            with st.spinner('מנתח נתונים ומחשב תחזיות...'):
                stats = calculate_portfolio_stats(selected_mix)
                future_value_optimistic = amount * ((1 + stats['avg_win']) ** years)
                future_value_pessimistic = amount * ((1 + stats['avg_loss']) ** years)
                expected_future_val = (future_value_optimistic * stats['p_win']) + (future_value_pessimistic * stats['p_loss'])
                total_profit = expected_future_val - amount
                annualized_return = ((expected_future_val / amount) ** (1/years)) - 1
                save_simulation_db(user['id'], amount, derived_risk, portfolio_name, expected_future_val, st.session_state['current_mode'], years)
            
            col_visual, col_data = st.columns([1.2, 1])
            with col_data:
                st.markdown("#### 🍰 הרכב התיק")
                df_pie = pd.DataFrame(list(selected_mix.items()), columns=['Ticker', 'Weight'])
                df_pie['Asset Name'] = df_pie['Ticker'].map(ASSET_NAMES)
                fig = px.pie(df_pie, values='Weight', names='Asset Name', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(showlegend=True, height=250, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, width="stretch")
                st.markdown("---")
                st.write(f"**צפי תשואה שנתית ממוצעת:** {annualized_return*100:.1f}%")
                st.success(f"**שווי מוערך בתום {years} שנים:** ₪{expected_future_val:,.0f}")
                color_txt = "green" if total_profit > 0 else "red"
                st.markdown(f"רווח משוקלל צפוי: :{color_txt}[**₪{total_profit:,.0f}**]")

            with col_visual:
                with st.expander("🔍 לחץ להצגת ניתוח עץ ההחלטות", expanded=False):
                    st.caption(f"התרשים מציג את ההתפלגות הסטטיסטית לשנה אחת (מתוך {years}):")
                    tree_graph, _ = generate_decision_tree_portfolio(amount, portfolio_name, stats)
                    st.graphviz_chart(tree_graph)
                    st.info("העץ מציג הסתברויות על בסיס 10 שנות היסטוריה.")

    with tab2:
        st.header("ההיסטוריה שלי")
        conn = init_connection()
        df = pd.read_sql(f"SELECT timestamp as 'תאריך', amount as 'סכום', investment_years as 'שנים', risk_level as 'סיכון', field_chosen as 'תיק נבחר', expected_net_value as 'שווי חזוי', selection_mode as 'מצב' FROM investments WHERE user_id={user['id']} ORDER BY timestamp DESC", conn)
        st.dataframe(df, width="stretch")
        conn.close()

# --- נתב ראשי ---
if st.session_state['logged_in']: app_dashboard()
else:
    if st.session_state['page'] == 'home': home_page()
    elif st.session_state['page'] == 'login': login_page()
    elif st.session_state['page'] == 'register': register_page()