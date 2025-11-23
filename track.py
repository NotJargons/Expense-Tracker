# Advanced Bank Statement Analyzer with Historical Tracking
# Install: pip install streamlit pandas matplotlib plotly openpyxl seaborn
# Run: streamlit run bank_analyzer_pro.py

import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from pathlib import Path
import warnings
import os
import hashlib
import base64
from io import BytesIO
import random
import string

# Suppress openpyxl warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# ========================= CONFIGURATION =========================

# Security settings
CREDENTIALS_FILE = "credentials.json"
STORAGE_FILE = "spending_history.json"
MAX_LOGIN_ATTEMPTS = 3
SESSION_TIMEOUT = 3600  # 1 hour

# Default credentials (will be replaced with user-provided ones)
DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

GOALS = {
    "Data": 11000,
    "Transport": 60000,
    "Food": 70000,
    "Subscriptions": 2500,
    "Miscellaneous": 10000,
}

CATEGORY_KEYWORDS = {
    "Data": [r"\bdata\b", r"\bbundle\b", r"\bairtel\b", r"\b9mobile\b", r"\bglo\b", r"\bmtn\b", r"\bmomo psb\b", r"\bmomo\b", r"\bopay\b"],
    "Transport": [r"\bbus\b", r"\bbrt\b", r"\btransport\b", r"\btfare\b", r"\buber\b", r"\bbus fare\b", r"\bbolt\b", r"\btaxi\b", r"\btransport fare\b"],
    "Food": [r"\brestaurant\b", r"\bfood\b", r"\bfnb\b", r"\bgrocer", r"\bsupermarket\b", r"\bkitchen\b", r"\bmeal\b", r"\bubereats\b"],
    "Subscriptions": [r"\bspotify\b", r"\bnetflix\b", r"\bprime\b", r"\bapple subscription\b", r"\bgoogle play\b", r"\bsubscription\b"],
}

CATEGORY_COLORS = {
    "Data": "#3498db",
    "Transport": "#e74c3c",
    "Food": "#2ecc71",
    "Subscriptions": "#9b59b6",
    "Miscellaneous": "#95a5a6"
}

# ========================= AUTHENTICATION =========================

def load_credentials():
    """Load credentials from file or create default"""
    try:
        if Path(CREDENTIALS_FILE).exists():
            with open(CREDENTIALS_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create default credentials
            default_creds = {
                "email": DEFAULT_EMAIL,
                "password_hash": DEFAULT_PASSWORD_HASH,
                "created_at": datetime.now().isoformat(),
                "reset_tokens": {}
            }
            save_credentials(default_creds)
            return default_creds
    except:
        return {
            "email": DEFAULT_EMAIL,
            "password_hash": DEFAULT_PASSWORD_HASH,
            "created_at": datetime.now().isoformat(),
            "reset_tokens": {}
        }

def save_credentials(credentials):
    """Save credentials to file"""
    try:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving credentials: {e}")
        return False

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    """Verify password against hash"""
    return hash_password(password) == password_hash

def is_valid_email(email):
    """Check if email is valid"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_reset_token():
    """Generate a random reset token"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=20))

def check_login():
    """Check if user is logged in"""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['login_time'] = None
        st.session_state['login_attempts'] = 0
    
    # Check session timeout
    if st.session_state['logged_in'] and st.session_state['login_time']:
        elapsed = datetime.now().timestamp() - st.session_state['login_time']
        if elapsed > SESSION_TIMEOUT:
            st.session_state['logged_in'] = False
            st.session_state['login_time'] = None
            st.warning("Session expired. Please login again.")
    
    return st.session_state['logged_in']

def login_page():
    """Display login page"""
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            background: white;
        }
        .login-title {
            font-size: 2rem;
            font-weight: bold;
            text-align: center;
            margin-bottom: 30px;
            color: #667eea;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<h2 class="login-title">🔐 Login</h2>', unsafe_allow_html=True)
        
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary", use_container_width=True):
            if st.session_state.get('login_attempts', 0) >= MAX_LOGIN_ATTEMPTS:
                st.error("Too many failed attempts. Please restart the app.")
                st.stop()
            
            credentials = load_credentials()
            
            if email == credentials['email'] and verify_password(password, credentials['password_hash']):
                st.session_state['logged_in'] = True
                st.session_state['login_time'] = datetime.now().timestamp()
                st.session_state['login_attempts'] = 0
                st.success("Login successful!")
                st.rerun()
            else:
                st.session_state['login_attempts'] = st.session_state.get('login_attempts', 0) + 1
                remaining = MAX_LOGIN_ATTEMPTS - st.session_state['login_attempts']
                st.error(f"Invalid credentials. {remaining} attempts remaining.")
        
        st.markdown('<div style="text-align: center; margin-top: 20px;">', unsafe_allow_html=True)
        if st.button("Forgot Password?"):
            st.session_state['show_reset'] = True
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Password reset section
    if st.session_state.get('show_reset', False):
        st.markdown("""
            <style>
            .reset-container {
                max-width: 400px;
                margin: 20px auto;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
                background: white;
            }
            </style>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="reset-container">', unsafe_allow_html=True)
            st.markdown('<h3 class="login-title">🔑 Reset Password</h3>', unsafe_allow_html=True)
            
            reset_email = st.text_input("Email", key="reset_email")
            
            if st.button("Send Reset Link", type="primary", use_container_width=True):
                credentials = load_credentials()
                
                if reset_email == credentials['email']:
                    # Generate reset token
                    token = generate_reset_token()
                    expiry = (datetime.now() + timedelta(hours=24)).isoformat()
                    
                    # Update credentials with reset token
                    if 'reset_tokens' not in credentials:
                        credentials['reset_tokens'] = {}
                    credentials['reset_tokens'][token] = expiry
                    
                    save_credentials(credentials)
                    
                    # Display reset link (in a real app, this would be emailed)
                    reset_url = f"?reset_token={token}"
                    st.success(f"Reset link generated! In a real app, this would be emailed to {reset_email}.")
                    st.code(reset_url)
                    
                    # For demo purposes, we'll show the token directly
                    st.info(f"Your reset token is: {token}")
                else:
                    st.error("Email not found in our system.")
            
            if st.button("Back to Login"):
                st.session_state['show_reset'] = False
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

def reset_password_page():
    """Display password reset page"""
    query_params = st.experimental_get_query_params()
    token = query_params.get('reset_token', [None])[0]
    
    if not token:
        st.error("Invalid reset link.")
        return
    
    credentials = load_credentials()
    
    if 'reset_tokens' not in credentials or token not in credentials['reset_tokens']:
        st.error("Invalid or expired reset token.")
        return
    
    # Check if token is expired
    expiry = datetime.fromisoformat(credentials['reset_tokens'][token])
    if datetime.now() > expiry:
        st.error("Reset token has expired.")
        return
    
    st.markdown("""
        <style>
        .reset-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            background: white;
        }
        .reset-title {
            font-size: 2rem;
            font-weight: bold;
            text-align: center;
            margin-bottom: 30px;
            color: #667eea;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="reset-container">', unsafe_allow_html=True)
        st.markdown('<h2 class="reset-title">🔑 Reset Password</h2>', unsafe_allow_html=True)
        
        new_password = st.text_input("New Password", type="password", key="new_pass")
        confirm_password = st.text_input("Confirm New Password", type="password", key="confirm_pass")
        
        if st.button("Reset Password", type="primary", use_container_width=True):
            if new_password == confirm_password:
                if len(new_password) >= 6:
                    # Update password
                    credentials['password_hash'] = hash_password(new_password)
                    credentials['updated_at'] = datetime.now().isoformat()
                    
                    # Remove used token
                    del credentials['reset_tokens'][token]
                    
                    save_credentials(credentials)
                    st.success("Password reset successfully! Please login with your new password.")
                    st.session_state['show_reset'] = False
                    st.rerun()
                else:
                    st.error("Password must be at least 6 characters long.")
            else:
                st.error("Passwords do not match.")
        
        st.markdown('</div>', unsafe_allow_html=True)

def settings_page():
    """Settings page for updating credentials"""
    st.markdown("### ⚙️ Settings")
    
    credentials = load_credentials()
    
    with st.expander("🔐 Update Credentials"):
        current_password = st.text_input("Current Password", type="password", key="current_pass")
        new_email = st.text_input("New Email", value=credentials['email'])
        new_password = st.text_input("New Password", type="password", key="new_pass")
        confirm_password = st.text_input("Confirm New Password", type="password", key="confirm_pass")
        
        if st.button("Update Credentials", type="primary"):
            if verify_password(current_password, credentials['password_hash']):
                if new_password == confirm_password:
                    if len(new_password) >= 6 and is_valid_email(new_email):
                        new_credentials = {
                            "email": new_email,
                            "password_hash": hash_password(new_password),
                            "updated_at": datetime.now().isoformat(),
                            "reset_tokens": credentials.get('reset_tokens', {})
                        }
                        if save_credentials(new_credentials):
                            st.success("Credentials updated successfully!")
                            st.session_state['logged_in'] = False
                            st.rerun()
                    else:
                        st.error("Password must be at least 6 characters long and email must be valid.")
                else:
                    st.error("New passwords do not match.")
            else:
                st.error("Current password is incorrect.")
    
    with st.expander("🗑️ Data Management"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear History", type="secondary"):
                if st.session_state.get('confirm_clear_history', False):
                    if clear_history():
                        st.success("History cleared successfully!")
                        st.session_state['confirm_clear_history'] = False
                        st.rerun()
                else:
                    st.session_state['confirm_clear_history'] = True
                    st.warning("Click again to confirm clearing all history.")
        
        with col2:
            if st.button("Export Data", type="secondary"):
                history = load_history()
                if history:
                    json_str = json.dumps(history, indent=2)
                    st.download_button(
                        label="Download History JSON",
                        data=json_str,
                        file_name=f"spending_history_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json"
                    )

# ========================= STORAGE FUNCTIONS =========================

def load_history():
    """Load historical spending data from JSON file"""
    try:
        if Path(STORAGE_FILE).exists():
            with open(STORAGE_FILE, 'r') as f:
                return json.load(f)
        return {}
    except:
        return {}

def save_history(history):
    """Save historical spending data to JSON file"""
    try:
        with open(STORAGE_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving history: {e}")
        return False

def add_month_to_history(month_key, data):
    """Add or update a month's data in history"""
    history = load_history()
    history[month_key] = data
    return save_history(history)

def clear_history():
    """Clear the historical spending data file"""
    if Path(STORAGE_FILE).exists():
        os.remove(STORAGE_FILE)
        return True
    return False

# ========================= HELPER FUNCTIONS =========================

def try_parse_date(s):
    if pd.isna(s) or str(s).strip() == "":
        return pd.NaT
    s = str(s).strip()
    
    # Handle the specific YYYY:DD:MM format
    if ':' in s and s.count(':') == 2:
        parts = s.split(':')
        if len(parts) == 3 and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2:
            try:
                year, day, month = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= day <= 31 and 1 <= month <= 12:
                    return datetime(year, month, day)
            except ValueError:
                pass
    
    # Try common date formats
    try:
        return pd.to_datetime(s, dayfirst=True, errors='coerce')
    except:
        return pd.NaT

def normalize_columns(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df

def infer_column(df, candidates):
    cols = df.columns
    for cand in candidates:
        for c in cols:
            if cand.lower() in c.lower():
                return c
    return None

def classify_row(narration):
    """Classify transaction based on Narration column only"""
    text = str(narration or '').lower()
    for cat, pats in CATEGORY_KEYWORDS.items():
        for pat in pats:
            if re.search(pat, text, flags=re.IGNORECASE):
                return cat
    return 'Miscellaneous'

def is_debit_transaction(transaction_ref):
    """Check if transaction is a debit based on Transaction Ref column"""
    if pd.isna(transaction_ref):
        return False
    ref_str = str(transaction_ref).upper()
    return 'DEBIT' in ref_str

def detect_statement_month(df, date_col):
    """Detect the statement month based on transaction dates (24th to 23rd cycle)"""
    valid_dates = df[date_col].dropna()
    if len(valid_dates) == 0:
        return None
    
    latest_date = valid_dates.max()
    
    if latest_date.day >= 24:
        target_date = latest_date + relativedelta(months=1)
    else:
        target_date = latest_date
    
    return target_date.strftime('%B %Y')

def extract_amount_from_row(row, prefer_cols):
    for c in prefer_cols:
        if c in row and pd.notna(row[c]) and str(row[c]).strip() != '':
            s = str(row[c]).replace(',', '').replace('(', '-').replace(')', '').strip()
            try:
                return float(s)
            except:
                continue
    for c in row.index:
        if 'debit' in c.lower() or 'amount' in c.lower() or 'credit' in c.lower():
            try:
                s = str(row[c]).replace(',', '').replace('(', '-').replace(')', '').strip()
                return float(s)
            except:
                continue
    return 0.0

def calculate_daily_spending(df, date_col):
    daily = df.groupby(df[date_col].dt.date)['AmountOut'].sum().reset_index()
    daily.columns = ['Date', 'Amount']
    return daily

def find_top_merchants(df, narration_col, top_n=10):
    df['Merchant'] = df[narration_col].fillna('Unknown')
    merchant_spending = df.groupby('Merchant')['AmountOut'].agg(['sum', 'count']).sort_values('sum', ascending=False).head(top_n)
    return merchant_spending

def calculate_spending_patterns(df, date_col):
    df['DayOfWeek'] = df[date_col].dt.day_name()
    df['Hour'] = df[date_col].dt.hour
    
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    dow_spending = df.groupby('DayOfWeek')['AmountOut'].sum().reindex(day_order, fill_value=0)
    hour_spending = df.groupby('Hour')['AmountOut'].sum()
    
    return dow_spending, hour_spending

def generate_insights(period_df, summary, total_debit):
    insights = []
    
    overspent = [cat for cat in GOALS if summary[cat] > GOALS[cat]]
    if overspent:
        insights.append(f"⚠️ Overspent in: {', '.join(overspent)}")
    
    underspent = [cat for cat in GOALS if summary[cat] < GOALS[cat] * 0.8]
    if underspent:
        insights.append(f"✅ Well under budget in: {', '.join(underspent)}")
    
    top_category = summary.idxmax()
    insights.append(f"💸 Highest spending: {top_category} (₦{summary[top_category]:,.0f})")
    
    transaction_count = len(period_df)
    avg_transaction = total_debit / transaction_count if transaction_count > 0 else 0
    insights.append(f"📊 {transaction_count} transactions • ₦{avg_transaction:,.0f} avg")
    
    unique_days = period_df['DateOnly'].nunique()
    daily_avg = total_debit / unique_days if unique_days > 0 else 0
    insights.append(f"📅 Daily average: ₦{daily_avg:,.0f}")
    
    return insights

def prepare_historical_comparison(history):
    """Prepare data for historical comparison charts"""
    if not history:
        return None
    
    df_list = []
    for month, data in history.items():
        row = {'Month': month, 'Total': data['total']}
        row.update(data['categories'])
        df_list.append(row)
    
    df = pd.DataFrame(df_list)
    df['SortDate'] = pd.to_datetime(df['Month'], format='%B %Y')
    df = df.sort_values('SortDate').drop('SortDate', axis=1)
    return df

def calculate_monthly_change(history, current_month, previous_month=None):
    """Calculate percentage change between months"""
    if not history or current_month not in history:
        return None, None, None
    
    current_data = history[current_month]
    
    if not previous_month:
        # Find the previous month in history
        months = sorted(history.keys(), key=lambda x: datetime.strptime(x, '%B %Y'))
        current_index = months.index(current_month)
        if current_index > 0:
            previous_month = months[current_index - 1]
        else:
            return None, None, None
    
    if previous_month not in history:
        return None, None, None
    
    previous_data = history[previous_month]
    
    # Calculate percentage changes
    total_change = ((current_data['total'] - previous_data['total']) / previous_data['total']) * 100 if previous_data['total'] > 0 else 0
    
    category_changes = {}
    for cat in GOALS.keys():
        current = current_data['categories'].get(cat, 0)
        previous = previous_data['categories'].get(cat, 0)
        change = ((current - previous) / previous) * 100 if previous > 0 else 0
        category_changes[cat] = change
    
    return total_change, category_changes, previous_month

def create_historical_dashboard(history):
    """Create comprehensive historical dashboard"""
    if not history:
        st.info("No historical data available")
        return
    
    hist_df = prepare_historical_comparison(history)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Months Tracked", len(history))
    with col2:
        avg_spend = hist_df['Total'].mean()
        st.metric("Avg Monthly Spend", f"₦{avg_spend:,.0f}")
    with col3:
        total_spend = hist_df['Total'].sum()
        st.metric("Total Tracked", f"₦{total_spend:,.0f}")
    with col4:
        trend = "📈" if hist_df['Total'].iloc[-1] > hist_df['Total'].iloc[0] else "📉"
        st.metric("Trend", trend)
    
    # Spending trend chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df['Month'],
        y=hist_df['Total'],
        mode='lines+markers',
        name='Monthly Spending',
        line=dict(color='#667eea', width=3),
        marker=dict(size=8)
    ))
    fig.add_hline(y=sum(GOALS.values()), line_dash="dash", line_color="red", 
                  annotation_text="Monthly Goal")
    fig.update_layout(title="Monthly Spending Trend", height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Category trends
    st.markdown("### 📊 Category Trends Over Time")
    category_cols = [c for c in hist_df.columns if c in GOALS.keys()]
    
    if category_cols:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=category_cols[:4],
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        for i, cat in enumerate(category_cols[:4]):
            row = (i // 2) + 1
            col = (i % 2) + 1
            fig.add_trace(
                go.Scatter(
                    x=hist_df['Month'],
                    y=hist_df[cat],
                    name=cat,
                    mode='lines+markers',
                    line=dict(color=CATEGORY_COLORS.get(cat, '#95a5a6'))
                ),
                row=row, col=col
            )
            fig.add_hline(
                y=GOALS[cat], line_dash="dot", 
                line_color="gray", row=row, col=col
            )
        
        fig.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    # Year-over-Year comparison
    st.markdown("### 📅 Year-over-Year Comparison")
    
    # Extract year from month
    hist_df['Year'] = pd.to_datetime(hist_df['Month'], format='%B %Y').dt.year
    hist_df['Month_Name'] = pd.to_datetime(hist_df['Month'], format='%B %Y').dt.month_name()
    
    yearly_data = hist_df.groupby('Year')['Total'].sum().reset_index()
    
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(yearly_data, x='Year', y='Total', title="Annual Spending")
        fig.update_traces(marker_color='#764ba2')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Month-over-month comparison
        month_comparison = hist_df.pivot(index='Month_Name', columns='Year', values='Total').fillna(0)
        fig = px.imshow(month_comparison.T, title="Monthly Heatmap by Year",
                       labels=dict(x="Month", y="Year", color="Spending"))
        st.plotly_chart(fig, use_container_width=True)
    
    # Detailed table
    st.markdown("### 📋 Detailed Monthly Breakdown")
    st.dataframe(
        hist_df.set_index('Month').style.format({
            'Total': '₦{:,.0f}',
            **{cat: '₦{:,.0f}' for cat in GOALS.keys()}
        }),
        use_container_width=True
    )

# ========================= MAIN APP =========================

def main_app():
    """Main application after login"""
    # Custom CSS
    st.markdown("""
        <style>
        .main-header {
            font-size: 3rem;
            font-weight: bold;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .month-badge {
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
            padding: 1rem;
            background: #f0f2f6;
            border-radius: 10px;
            text-align: center;
            margin: 1rem 0;
        }
        .insight-box {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            margin: 0.5rem 0;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding-left: 20px;
            padding-right: 20px;
        }
        .metric-change {
            font-size: 0.8rem;
            color: #666;
        }
        .metric-up {
            color: green;
        }
        .metric-down {
            color: red;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("### 🧭 Navigation")
        page = st.radio(
            "Select Page",
            ["📊 Dashboard", "📤 Upload Statement", "📚 Historical Analysis", "⚙️ Settings", "🚪 Logout"]
        )
        
        if page == "🚪 Logout":
            st.session_state['logged_in'] = False
            st.session_state['login_time'] = None
            st.rerun()
    
    # Page content
    if page == "📊 Dashboard":
        st.markdown('<p class="main-header">💰 Expense Tracker</p>', unsafe_allow_html=True)
        
        # Quick stats from latest month
        history = load_history()
        if history:
            # Month selector
            months = sorted(history.keys(), key=lambda x: datetime.strptime(x, '%B %Y'), reverse=True)
            selected_month = st.selectbox("Select Month", months)
            
            # Get data for selected month
            month_data = history[selected_month]
            
            # Calculate changes from previous month
            total_change, category_changes, previous_month = calculate_monthly_change(history, selected_month)
            
            st.markdown(f'<div class="month-badge">📅 {selected_month}</div>', unsafe_allow_html=True)
            
            # Display metrics with percentage changes
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if total_change is not None:
                    change_icon = "📈" if total_change > 0 else "📉"
                    change_class = "metric-up" if total_change > 0 else "metric-down"
                    st.markdown(f'<div class="metric-change {change_class}">{change_icon} {total_change:.1f}% from {previous_month}</div>', unsafe_allow_html=True)
                st.metric("Total Spending", f"₦{month_data['total']:,.0f}")
            
            with col2:
                st.metric("Budget Goal", f"₦{sum(GOALS.values()):,.0f}")
            
            with col3:
                savings = sum(GOALS.values()) - month_data['total']
                st.metric("Savings", f"₦{savings:,.0f}")
            
            with col4:
                st.metric("Transactions", month_data['transaction_count'])
            
            # Category breakdown with changes
            st.markdown("### 📊 Category Breakdown")
            cats = list(month_data['categories'].keys())
            values = list(month_data['categories'].values())
            
            # Create subplot with two charts
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=["Budget vs Actual", "Spending Distribution"],
                specs=[[{"type": "bar"}, {"type": "pie"}]]
            )
            
            # Bar chart
            fig.add_trace(
                go.Bar(name='Actual', x=cats, y=values,
                      marker_color=[CATEGORY_COLORS.get(c, '#95a5a6') for c in cats]),
                row=1, col=1
            )
            fig.add_trace(
                go.Bar(name='Goal', x=cats, y=[GOALS[c] for c in cats],
                      marker_color='lightblue'),
                row=1, col=1
            )
            
            # Pie chart
            nz = [(c, month_data['categories'][c]) for c in cats if month_data['categories'][c] > 0]
            if nz:
                labels, values_pie = zip(*nz)
                fig.add_trace(
                    go.Pie(labels=labels, values=values_pie, hole=0.4,
                         marker_colors=[CATEGORY_COLORS.get(c, '#95a5a6') for c in labels]),
                    row=1, col=2
                )
            
            fig.update_layout(barmode='group', height=500)
            st.plotly_chart(fig, use_container_width=True)
            
            # Category metrics with changes
            st.markdown("### 📈 Category Performance")
            cat_cols = st.columns(3)
            for i, cat in enumerate(cats):
                with cat_cols[i % 3]:
                    if category_changes and cat in category_changes:
                        change = category_changes[cat]
                        change_icon = "📈" if change > 0 else "📉"
                        change_class = "metric-up" if change > 0 else "metric-down"
                        st.markdown(f'<div class="metric-change {change_class}">{change_icon} {change:.1f}% from {previous_month}</div>', unsafe_allow_html=True)
                    st.metric(cat, f"₦{month_data['categories'][cat]:,.0f}")
        else:
            st.info("No data available. Please upload a statement to get started.")
    
    elif page == "📤 Upload Statement":
        st.markdown('<p class="main-header">📤 Upload Statement</p>', unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            'Upload Your Bank Statement',
            type=['xls', 'xlsx'],
            help='Upload your exported statement from 24th to 23rd'
        )
        
        if uploaded_file is not None:
            try:
                with st.spinner('🔄 Analyzing your statement...'):
                    # Process file (same as original code)
                    try:
                        df = pd.read_excel(uploaded_file, header=7, dtype=str, engine='openpyxl')
                    except (ValueError, Exception) as e:
                        if "vertical" in str(e).lower():
                            try:
                                df = pd.read_excel(uploaded_file, header=7, dtype=str, engine='xlrd')
                            except:
                                import openpyxl
                                wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
                                df = pd.read_excel(wb, header=7, dtype=str)
                        else:
                            raise e
                    
                    df = normalize_columns(df)
                    
                    # Infer columns
                    date_col = infer_column(df, ['date', 'transaction date', 'value date']) or list(df.columns)[0]
                    narration_col = infer_column(df, ['narration', 'description']) or 'Narration'
                    transaction_ref_col = infer_column(df, ['transaction ref', 'ref', 'reference']) or 'Transaction Ref'
                    debit_col = infer_column(df, ['settlement debit', 'debit']) or None
                    alt_col = infer_column(df, ['transaction amount', 'amount']) or None
                    
                    # Parse dates
                    df[date_col] = df[date_col].apply(try_parse_date)
                    df['DateOnly'] = df[date_col].dt.date
                    df['TimeAMPM'] = df[date_col].dt.strftime('%I:%M:%S %p')
                    
                    # Detect statement month
                    statement_month = detect_statement_month(df, date_col)
                    
                    if statement_month is None:
                        st.error('❌ Could not detect statement month. Please check date format.')
                        st.stop()
                    
                    st.markdown(f'<div class="month-badge">📅 {statement_month}</div>', unsafe_allow_html=True)
                    
                    # Filter for DEBIT transactions
                    if transaction_ref_col in df.columns:
                        df['IsDebit'] = df[transaction_ref_col].apply(is_debit_transaction)
                        period_df = df[df['IsDebit'] == True].copy()
                    else:
                        st.warning('⚠️ Transaction Ref column not found - analyzing all transactions')
                        period_df = df.copy()
                    
                    if len(period_df) == 0:
                        st.error('❌ No DEBIT transactions found in this statement')
                        st.stop()
                    
                    # Classify transactions
                    if narration_col not in period_df.columns:
                        period_df['Narration'] = ''
                        narration_col = 'Narration'
                    
                    period_df['Category'] = period_df[narration_col].apply(classify_row)
                    
                    # Extract amounts
                    prefer_amount_cols = [c for c in [debit_col, alt_col] if c is not None]
                    period_df['AmountRaw'] = period_df.apply(lambda r: extract_amount_from_row(r, prefer_amount_cols), axis=1)
                    period_df['AmountOut'] = period_df['AmountRaw'].apply(lambda x: abs(x) if pd.notna(x) else 0.0)
                    period_df = period_df[period_df['AmountOut'] > 0].copy()
                    
                    # Calculate metrics
                    summary = period_df.groupby('Category', as_index=True)['AmountOut'].sum().reindex(list(GOALS.keys()), fill_value=0.0)
                    total_debit = period_df['AmountOut'].sum()
                    goal_total = sum(GOALS.values())
                    
                    # Generate insights
                    insights = generate_insights(period_df, summary, total_debit)
                    
                    # Save to history
                    month_data = {
                        'total': float(total_debit),
                        'goal': float(goal_total),
                        'categories': {k: float(v) for k, v in summary.items()},
                        'transaction_count': len(period_df),
                        'date_processed': datetime.now().isoformat()
                    }
                    add_month_to_history(statement_month, month_data)
                
                # Display results
                st.success(f'✅ {statement_month} analysis complete and saved to history!')
                
                # Key metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric('Total Spending', f'₦{total_debit:,.0f}')
                with col2:
                    st.metric('Budget Goal', f'₦{goal_total:,.0f}')
                with col3:
                    st.metric('Transactions', f'{len(period_df):,}')
                with col4:
                    savings = goal_total - total_debit
                    st.metric('Net Position', f'₦{savings:,.0f}')
                
                # Insights
                st.markdown('### 💡 Key Insights')
                for insight in insights:
                    st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)
                
                # Charts
                tab1, tab2, tab3 = st.tabs(['📊 Overview', '📅 Daily Trends', '🏪 Top Merchants'])
                
                with tab1:
                    col1, col2 = st.columns(2)
                    with col1:
                        fig = go.Figure()
                        cats = list(summary.index)
                        fig.add_trace(go.Bar(name='Goal', x=cats, y=[GOALS[c] for c in cats], 
                                            marker_color='lightblue'))
                        fig.add_trace(go.Bar(name='Actual', x=cats, y=[summary[c] for c in cats],
                                            marker_color=[CATEGORY_COLORS.get(c, '#95a5a6') for c in cats]))
                        fig.update_layout(title='Budget vs Actual', barmode='group')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        nz = [(c, summary[c]) for c in cats if summary[c] > 0]
                        if nz:
                            labels, values = zip(*nz)
                            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4,
                                                         marker_colors=[CATEGORY_COLORS.get(c, '#95a5a6') for c in labels])])
                            fig.update_layout(title='Spending Distribution')
                            st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    daily_spending = calculate_daily_spending(period_df, date_col)
                    fig = px.line(daily_spending, x='Date', y='Amount', title='Daily Spending Trend')
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab3:
                    merchant_data = find_top_merchants(period_df, narration_col)
                    fig = go.Figure(go.Bar(
                        x=merchant_data['sum'],
                        y=merchant_data.index,
                        orientation='h',
                        marker_color='#764ba2'
                    ))
                    fig.update_layout(title='Top Merchants')
                    st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f'❌ Error processing file: {str(e)}')
                st.exception(e)
    
    elif page == "📚 Historical Analysis":
        st.markdown('<p class="main-header">📚 Historical Analysis</p>', unsafe_allow_html=True)
        
        history = load_history()
        if not history:
            st.info("No historical data available. Upload statements to build your history.")
        else:
            create_historical_dashboard(history)
    
    elif page == "⚙️ Settings":
        settings_page()

# ========================= MAIN EXECUTION =========================

def main():
    """Main execution function"""
    # Configure page
    st.set_page_config(
        page_title='Expense Tracker',
        page_icon='💰',
        layout='wide',
        initial_sidebar_state='expanded'
    )
    
    # Check for reset token in URL
    query_params = st.experimental_get_query_params()
    if 'reset_token' in query_params:
        reset_password_page()
        return
    
    # Check authentication
    if not check_login():
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
