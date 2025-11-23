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
import os  # --- NEW: Import the os module ---

# Suppress openpyxl warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# ========================= CONFIGURATION =========================

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

# Storage file for historical data
STORAGE_FILE = "spending_history.json"

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

# --- NEW: Function to clear history ---
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
                # Validate day and month values
                if 1 <= day <= 31 and 1 <= month <= 12:
                    return datetime(year, month, day)
            except ValueError:
                pass  # Fall through to other parsing methods
    
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
    # Get all valid dates
    valid_dates = df[date_col].dropna()
    if len(valid_dates) == 0:
        return None
    
    # Find the latest date in the statement
    latest_date = valid_dates.max()
    
    # If the latest date is between 24th-31st, the statement is for the NEXT month
    # If the latest date is between 1st-23rd, the statement is for the CURRENT month
    if latest_date.day >= 24:
        # Statement is for next month
        target_date = latest_date + relativedelta(months=1)
    else:
        # Statement is for current month
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
    
    # Goal adherence
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
    # Sort by date
    df['SortDate'] = pd.to_datetime(df['Month'], format='%B %Y')
    df = df.sort_values('SortDate').drop('SortDate', axis=1)
    return df

# ========================= STREAMLIT UI =========================

st.set_page_config(
    page_title='Expense Tracker',
    page_icon='💰',
    layout='wide',
    initial_sidebar_state='collapsed'
)

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
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">💰 Expense Tracker</p>', unsafe_allow_html=True)

# ========================= FILE UPLOAD =========================

uploaded_file = st.file_uploader('📤 Upload Your Bank Statement', type=['xls', 'xlsx'], help='Upload your exported statement from 24th to 23rd')

if uploaded_file is None:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.info('👆 Upload your monthly bank statement to get started')
        
        # Show historical data if available
        history = load_history()
        if history:
            st.markdown('### 📚 Historical Data Available')
            st.write(f"You have {len(history)} month(s) of data stored")
            
            # --- NEW: Add Clear History Button ---
            col_hist1, col_hist2, col_hist3 = st.columns([1, 2, 1])
            with col_hist2:
                if st.button('🗑️ Clear All History', type='secondary'):
                    if st.session_state.get('confirm_clear', False):
                        if clear_history():
                            st.success('✅ History cleared successfully!')
                            st.session_state['confirm_clear'] = False
                            st.rerun()
                        else:
                            st.error('❌ No history file found to clear.')
                    else:
                        st.session_state['confirm_clear'] = True
                        st.warning('⚠️ Are you sure? Click the button again to confirm.')
            
            if st.button('📊 View Historical Analysis', type='primary'):
                st.session_state['show_history'] = True
                st.rerun()
        
else:
    try:
        # Load and process data
        with st.spinner('🔄 Analyzing your statement...'):
            # Try multiple approaches to read the Excel file
            try:
                # First try with openpyxl
                df = pd.read_excel(uploaded_file, header=7, dtype=str, engine='openpyxl')
            except (ValueError, Exception) as e:
                if "vertical" in str(e).lower():
                    # If it's a vertical alignment issue, try with xlrd
                    try:
                        df = pd.read_excel(uploaded_file, header=7, dtype=str, engine='xlrd')
                    except:
                        # If xlrd doesn't work, try to read with openpyxl but ignore styling
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
            
            # Filter for DEBIT transactions only
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
            
        # ========================= DASHBOARD =========================
        
        st.markdown('---')
        
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric('Total Spending', f'₦{total_debit:,.0f}', 
                     delta=f'{((total_debit/goal_total - 1) * 100):.1f}% vs goal',
                     delta_color='inverse')
        with col2:
            st.metric('Budget Goal', f'₦{goal_total:,.0f}')
        with col3:
            st.metric('Transactions', f'{len(period_df):,}')
        with col4:
            savings = goal_total - total_debit
            st.metric('Net Position', f'₦{savings:,.0f}',
                     delta='Under budget ✅' if savings > 0 else 'Over budget ❌',
                     delta_color='normal' if savings > 0 else 'inverse')
        
        # Insights
        st.markdown('### 💡 Key Insights')
        cols = st.columns(2)
        for i, insight in enumerate(insights):
            with cols[i % 2]:
                st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)
        
        # ========================= TABS =========================
        
        st.markdown('---')
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(['📊 Overview', '📅 Daily Trends', '🏪 Top Merchants', '⏰ Spending Patterns', '📋 Transactions', '📈 Historical'])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                # Budget vs Actual
                fig = go.Figure()
                cats = list(summary.index)
                fig.add_trace(go.Bar(name='Goal', x=cats, y=[GOALS[c] for c in cats], 
                                    marker_color='lightblue'))
                fig.add_trace(go.Bar(name='Actual', x=cats, y=[summary[c] for c in cats],
                                    marker_color=[CATEGORY_COLORS.get(c, '#95a5a6') for c in cats]))
                fig.update_layout(title='Budget vs Actual by Category', barmode='group', height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Pie chart
                nz = [(c, summary[c]) for c in cats if summary[c] > 0]
                if nz:
                    labels, values = zip(*nz)
                    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4,
                                                 marker_colors=[CATEGORY_COLORS.get(c, '#95a5a6') for c in labels])])
                    fig.update_layout(title='Spending Distribution', height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Progress bars
            st.markdown('#### 🎯 Category Progress')
            for cat in cats:
                col1, col2 = st.columns([3, 1])
                with col1:
                    progress = summary[cat] / GOALS[cat] if GOALS[cat] > 0 else 0
                    st.progress(min(progress, 1.0))
                with col2:
                    st.caption(f'₦{summary[cat]:,.0f} / ₦{GOALS[cat]:,.0f}')
        
        with tab2:
            # Daily spending trend
            daily_spending = calculate_daily_spending(period_df, date_col)
            
            col1, col2 = st.columns(2)
            with col1:
                fig = px.line(daily_spending, x='Date', y='Amount', title='Daily Spending Trend',
                             markers=True)
                fig.update_traces(line_color='#667eea', line_width=3)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Cumulative spending
                daily_spending['Cumulative'] = daily_spending['Amount'].cumsum()
                fig = px.area(daily_spending, x='Date', y='Cumulative', title='Cumulative Spending')
                fig.update_traces(fillcolor='rgba(102, 126, 234, 0.3)', line_color='#667eea')
                st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            # Top merchants
            merchant_data = find_top_merchants(period_df, narration_col, top_n=15)
            fig = go.Figure(go.Bar(
                x=merchant_data['sum'],
                y=merchant_data.index,
                orientation='h',
                marker_color='#764ba2'
            ))
            fig.update_layout(title='Top 15 Merchants by Spending', height=500, yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        with tab4:
            col1, col2 = st.columns(2)
            
            with col1:
                # Day of week pattern
                dow_spending, hour_spending = calculate_spending_patterns(period_df, date_col)
                fig = px.bar(x=dow_spending.index, y=dow_spending.values, 
                            title='Spending by Day of Week',
                            labels={'x': 'Day', 'y': 'Amount (NGN)'})
                fig.update_traces(marker_color='#2ecc71')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Hour of day pattern
                fig = px.line(x=hour_spending.index, y=hour_spending.values,
                             title='Spending by Hour of Day',
                             labels={'x': 'Hour', 'y': 'Amount (NGN)'},
                             markers=True)
                fig.update_traces(line_color='#e74c3c', line_width=3)
                st.plotly_chart(fig, use_container_width=True)
        
        with tab5:
            # Transaction details
            st.markdown('#### 📋 Transaction Details')
            
            # Filters
            col1, col2 = st.columns(2)
            with col1:
                cat_filter = st.multiselect('Filter by category', options=['All'] + list(cats), default=['All'])
            with col2:
                search = st.text_input('🔍 Search narration', '')
            
            # Apply filters
            filtered_df = period_df.copy()
            if 'All' not in cat_filter and cat_filter:
                filtered_df = filtered_df[filtered_df['Category'].isin(cat_filter)]
            if search:
                filtered_df = filtered_df[filtered_df[narration_col].str.contains(search, case=False, na=False)]
            
            # Display
            display_cols = [date_col, 'DateOnly', 'TimeAMPM', narration_col, 'Category', 'AmountOut']
            display_cols = [c for c in display_cols if c in filtered_df.columns]
            
            st.dataframe(
                filtered_df[display_cols].sort_values(by=date_col, ascending=False).reset_index(drop=True),
                use_container_width=True,
                height=400
            )
            
            # Download button
            csv_buf = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button('📥 Download CSV', data=csv_buf, 
                             file_name=f'transactions_{statement_month.replace(" ", "_")}.csv',
                             mime='text/csv')
        
        with tab6:
            # Historical comparison
            st.markdown('#### 📈 Historical Trends')
            
            history = load_history()
            if len(history) < 2:
                st.info('💡 Upload more months to see historical trends')
            else:
                hist_df = prepare_historical_comparison(history)
                
                # Total spending trend
                fig = px.line(hist_df, x='Month', y='Total', title='Monthly Spending Trend',
                             markers=True, line_shape='spline')
                fig.update_traces(line_color='#667eea', line_width=3)
                fig.add_hline(y=goal_total, line_dash="dash", line_color="red", 
             annotation=dict(text="Monthly Goal"))
                st.plotly_chart(fig, use_container_width=True)
                
                # Category comparison
                category_cols = [c for c in hist_df.columns if c in GOALS.keys()]
                if category_cols:
                    fig = go.Figure()
                    for cat in category_cols:
                        fig.add_trace(go.Scatter(
                            x=hist_df['Month'], y=hist_df[cat],
                            name=cat, mode='lines+markers',
                            line=dict(width=2, color=CATEGORY_COLORS.get(cat, '#95a5a6'))
                        ))
                    fig.update_layout(title='Category Trends Over Time', height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Summary table
                st.markdown('#### 📊 Historical Summary')
                st.dataframe(hist_df.set_index('Month'), use_container_width=True)
        
        st.success(f'✅ {statement_month} analysis complete and saved to history!')
        
    except Exception as e:
        st.error(f'❌ Error processing file: {str(e)}')
        st.exception(e)

# Show history view if requested
if 'show_history' in st.session_state and st.session_state['show_history'] and uploaded_file is None:
    history = load_history()
    if history:
        st.markdown('### 📚 Historical Overview')
        hist_df = prepare_historical_comparison(history)
        
        # Overview metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            total_months = len(history)
            st.metric('Months Tracked', total_months)
        with col2:
            avg_spending = hist_df['Total'].mean()
            st.metric('Average Monthly Spend', f'₦{avg_spending:,.0f}')
        with col3:
            total_spent = hist_df['Total'].sum()
            st.metric('Total Tracked', f'₦{total_spent:,.0f}')
        
        # Charts
        fig = px.line(hist_df, x='Month', y='Total', markers=True, title='All-Time Spending Trend')
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(hist_df.set_index('Month'), use_container_width=True)
        
        if st.button('← Back to Upload'):
            del st.session_state['show_history']
            st.rerun()

# Footer
st.markdown('---')