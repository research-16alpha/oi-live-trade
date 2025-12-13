import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json
from datetime import datetime

st.set_page_config(
    page_title="Option Chain Trading Portfolio",
    page_icon="📈",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .positive { color: #00cc00; font-weight: bold; }
    .negative { color: #ff0000; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def load_portfolio_data():
    """Load portfolio data from JSON file."""
    portfolio_file = Path("portfolio.json")
    if not portfolio_file.exists():
        return None
    try:
        with open(portfolio_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading portfolio: {e}")
        return None

def get_current_position_value():
    """Get current position value if position is open."""
    try:
        from portfolio_manager import PortfolioManager
        from generate_signal import get_current_ltp, load_csv, prepare_data
        
        portfolio = PortfolioManager()
        open_position = portfolio.get_open_position()
        if not open_position:
            return None, None
        
        output_dir = Path("output")
        csv_files = sorted(output_dir.glob("snapshot_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if csv_files:
            df_raw = load_csv(csv_files[0])
            df_prep = prepare_data(df_raw)
            current_ltp = get_current_ltp(
                df_prep,
                open_position['expiry'],
                open_position['strike'],
                open_position['type']
            )
            return open_position, current_ltp
        return open_position, None
    except Exception as e:
        return None, None

def calculate_portfolio_history(portfolio_data):
    """Calculate portfolio value over time from trade history."""
    if not portfolio_data:
        return pd.DataFrame()
    
    initial_balance = portfolio_data.get('initial_balance', 100000.0)
    trade_history = portfolio_data.get('trade_history', [])
    
    history = [{
        'timestamp': portfolio_data.get('created_at', datetime.now().isoformat()),
        'balance': initial_balance,
        'total_value': initial_balance,
        'position_value': 0.0,
        'realized_pnl': 0.0
    }]
    
    current_balance = initial_balance
    realized_pnl = 0.0
    
    for trade in trade_history:
        if trade['action'] == 'BUY':
            current_balance = trade['balance_after']
            history.append({
                'timestamp': trade['timestamp'],
                'balance': current_balance,
                'total_value': current_balance,
                'position_value': 0.0,
                'realized_pnl': realized_pnl
            })
        elif trade['action'] == 'SELL':
            current_balance = trade['balance_after']
            realized_pnl += trade.get('pnl', 0)
            history.append({
                'timestamp': trade['timestamp'],
                'balance': current_balance,
                'total_value': current_balance,
                'position_value': 0.0,
                'realized_pnl': realized_pnl
            })
    
    from portfolio_manager import PortfolioManager
    portfolio = PortfolioManager()
    open_position, current_ltp = get_current_position_value()
    current_balance = portfolio.get_balance()
    
    if open_position and current_ltp:
        position_value = current_ltp * 150
        total_value = current_balance + position_value
        entry_price = open_position.get('entry_price', 0)
        unrealized_pnl = (current_ltp - entry_price) * 150
        total_pnl = realized_pnl + unrealized_pnl
    else:
        position_value = 0.0
        total_value = current_balance
        total_pnl = realized_pnl
    
    history.append({
        'timestamp': datetime.now().isoformat(),
        'balance': current_balance,
        'total_value': total_value,
        'position_value': position_value,
        'realized_pnl': total_pnl
    })
    
    df = pd.DataFrame(history)
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
    
    return df

def calculate_win_ratio(portfolio_data):
    """Calculate win ratio from closed positions."""
    if not portfolio_data:
        return 0, 0, 0
    
    closed_positions = [p for p in portfolio_data.get('positions', []) if p.get('status') == 'closed']
    
    if not closed_positions:
        return 0, 0, 0
    
    winning_trades = len([p for p in closed_positions if p.get('pnl', 0) > 0])
    losing_trades = len([p for p in closed_positions if p.get('pnl', 0) < 0])
    total_trades = len(closed_positions)
    
    win_ratio = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return win_ratio, winning_trades, losing_trades

def main():
    st.markdown('<div class="main-header">📈 Option Chain Trading Portfolio Dashboard</div>', unsafe_allow_html=True)
    
    portfolio_data = load_portfolio_data()
    
    if not portfolio_data:
        st.warning("No portfolio data found. Start trading to see your portfolio!")
        st.info("Run the monitor to start trading: `python automate_oi_monitor.py`")
        return
    
    from portfolio_manager import PortfolioManager
    portfolio = PortfolioManager()
    open_position, current_ltp = get_current_position_value()
    
    summary = portfolio.get_portfolio_summary(current_ltp)
    
    # Get start date and initial balance
    start_date_str = portfolio_data.get('created_at', datetime.now().isoformat())
    try:
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
    except:
        start_date = datetime.fromisoformat(start_date_str)
    
    initial_balance = summary['initial_balance']
    current_total = summary['total_value']
    current_date = datetime.now()
    total_pnl = current_total - initial_balance
    total_pnl_pct = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0
    
    win_ratio, winning_trades, losing_trades = calculate_win_ratio(portfolio_data)
    
    # Key Metrics Section - Start Date, Start Value, Current Date, Current Value
    st.markdown("### 🎯 Portfolio Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; text-align: center;">
            <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">Start Date</div>
            <div style="font-size: 1.2rem; font-weight: bold; color: #1f77b4;">
                {start_date.strftime('%d %b %Y')}
            </div>
            <div style="font-size: 0.8rem; color: #999; margin-top: 0.3rem;">
                {start_date.strftime('%I:%M %p')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; text-align: center;">
            <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">Start Portfolio Value</div>
            <div style="font-size: 1.2rem; font-weight: bold; color: #1f77b4;">
                ₹{initial_balance:,.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="background-color: #e8f5e9; padding: 1rem; border-radius: 0.5rem; text-align: center;">
            <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">Current Date</div>
            <div style="font-size: 1.2rem; font-weight: bold; color: #2ca02c;">
                {current_date.strftime('%d %b %Y')}
            </div>
            <div style="font-size: 0.8rem; color: #999; margin-top: 0.3rem;">
                {current_date.strftime('%I:%M %p')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        pnl_color = "#00cc00" if total_pnl >= 0 else "#ff0000"
        st.markdown(f"""
        <div style="background-color: #e8f5e9; padding: 1rem; border-radius: 0.5rem; text-align: center;">
            <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">Current Portfolio Value</div>
            <div style="font-size: 1.2rem; font-weight: bold; color: #2ca02c;">
                ₹{current_total:,.2f}
            </div>
            <div style="font-size: 0.9rem; color: {pnl_color}; margin-top: 0.3rem; font-weight: bold;">
                {total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Portfolio Value Graph - Historical from Start Date
    st.markdown("### 📊 Portfolio Value History (Since Start)")
    portfolio_history = calculate_portfolio_history(portfolio_data)
    
    if not portfolio_history.empty:
        fig = go.Figure()
        
        # Main portfolio value line
        fig.add_trace(go.Scatter(
            x=portfolio_history['timestamp'],
            y=portfolio_history['total_value'],
            mode='lines+markers',
            name='Total Portfolio Value',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=6, color='#1f77b4'),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Date: %{x|%d %b %Y %I:%M %p}<br>' +
                         'Value: ₹%{y:,.2f}<extra></extra>',
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        # Cash balance line
        fig.add_trace(go.Scatter(
            x=portfolio_history['timestamp'],
            y=portfolio_history['balance'],
            mode='lines',
            name='Cash Balance',
            line=dict(color='#2ca02c', width=2, dash='dash'),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Date: %{x|%d %b %Y %I:%M %p}<br>' +
                         'Value: ₹%{y:,.2f}<extra></extra>'
        ))
        
        # Initial balance reference line
        fig.add_hline(
            y=initial_balance,
            line_dash="dot",
            line_color="gray",
            line_width=2,
            annotation_text=f"Start Value: ₹{initial_balance:,.2f}",
            annotation_position="right"
        )
        
        # Current value annotation
        if len(portfolio_history) > 0:
            last_value = portfolio_history['total_value'].iloc[-1]
            last_time = portfolio_history['timestamp'].iloc[-1]
            fig.add_annotation(
                x=last_time,
                y=last_value,
                text=f"Current: ₹{last_value:,.2f}",
                showarrow=True,
                arrowhead=2,
                arrowcolor="#2ca02c",
                bgcolor="white",
                bordercolor="#2ca02c",
                borderwidth=2
            )
        
        fig.update_layout(
            title={
                'text': f'Portfolio Value Evolution (Since {start_date.strftime("%d %b %Y")})',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18}
            },
            xaxis_title="Date & Time",
            yaxis_title="Portfolio Value (₹)",
            hovermode='x unified',
            height=600,
            template='plotly_white',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=50, r=50, t=80, b=50)
        )
        
        # Format x-axis to show dates nicely
        fig.update_xaxes(
            tickformat='%d %b %Y\n%I:%M %p',
            tickangle=-45
        )
        
        # Format y-axis to show currency
        fig.update_yaxes(
            tickformat=',.0f',
            tickprefix='₹'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show time period summary
        days_running = (current_date - start_date).days
        hours_running = (current_date - start_date).total_seconds() / 3600
        st.caption(f"📅 Trading Period: {days_running} days ({hours_running:.1f} hours) | Total P&L: ₹{total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
    else:
        st.info("No trading history yet. Start trading to see your portfolio grow!")
    
    st.divider()
    
    # Additional metrics
    st.markdown("### 📈 Performance Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Cash Balance", f"₹{summary['cash']:,.2f}", f"Position: ₹{summary['position_value']:,.2f}" if summary['position_value'] > 0 else None)
    
    with col2:
        realized_pnl = summary.get('total_pnl', 0)
        st.metric("Realized P&L", f"₹{realized_pnl:,.2f}", f"{winning_trades}W / {losing_trades}L")
    
    with col3:
        st.metric("Win Ratio", f"{win_ratio:.1f}%", f"{winning_trades}/{winning_trades + losing_trades}" if (winning_trades + losing_trades) > 0 else "0/0")
    
    with col4:
        if open_position and current_ltp:
            unrealized_pnl = summary['unrealized_pnl']
            st.metric("Unrealized P&L", f"₹{unrealized_pnl:,.2f}", f"{summary['unrealized_pnl_pct']:+.2f}%")
        else:
            st.metric("Unrealized P&L", "₹0.00", "No open position")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📌 Current Position")
        if open_position:
            entry_price = open_position.get('entry_price', 0)
            entry_time = open_position.get('entry_time', 'Unknown')
            
            if current_ltp:
                unrealized_pnl = summary['unrealized_pnl']
                unrealized_pnl_pct = summary['unrealized_pnl_pct']
                pnl_class = "positive" if unrealized_pnl >= 0 else "negative"
                
                st.markdown(f"""
                <div style="background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem;">
                    <strong>Type:</strong> {open_position['type']}<br>
                    <strong>Expiry:</strong> {open_position['expiry']}<br>
                    <strong>Strike:</strong> {open_position['strike']}<br>
                    <strong>Entry Price:</strong> ₹{entry_price:.2f}<br>
                    <strong>Current LTP:</strong> ₹{current_ltp:.2f}<br>
                    <strong>Quantity:</strong> {open_position.get('quantity', 150)}<br>
                    <strong>Entry Time:</strong> {entry_time}<br>
                    <strong class="{pnl_class}">Unrealized P&L:</strong> 
                    <span class="{pnl_class}">₹{unrealized_pnl:,.2f} ({unrealized_pnl_pct:+.2f}%)</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info(f"Position: {open_position['type']} {open_position['expiry']} {open_position['strike']}")
        else:
            st.success("No open position")
    
    with col2:
        st.markdown("### 📋 Recent Trades")
        trade_history = portfolio_data.get('trade_history', [])
        
        if trade_history:
            recent_trades = trade_history[-10:]
            trades_df = pd.DataFrame(recent_trades)
            
            if not trades_df.empty:
                display_cols = ['action', 'signal_type', 'strike', 'timestamp']
                if 'entry_price' in trades_df.columns:
                    display_cols.insert(3, 'entry_price')
                if 'exit_price' in trades_df.columns:
                    display_cols.insert(4, 'exit_price')
                if 'pnl' in trades_df.columns:
                    display_cols.append('pnl')
                
                available_cols = [c for c in display_cols if c in trades_df.columns]
                trades_display = trades_df[available_cols].copy()
                st.dataframe(trades_display, use_container_width=True, hide_index=True)
        else:
            st.info("No trades yet")
    
    st.divider()
    st.markdown("### 📊 Trading Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_trades = summary['total_trades']
        st.metric("Total Trades", total_trades)
    
    with col2:
        closed_count = summary['closed_positions_count']
        st.metric("Closed Positions", closed_count)
    
    with col3:
        avg_pnl = (summary['total_pnl'] / closed_count) if closed_count > 0 else 0
        st.metric("Avg P&L per Trade", f"₹{avg_pnl:,.2f}")
    
    with col4:
        closed_positions = [p for p in portfolio_data.get('positions', []) if p.get('status') == 'closed']
        best_trade = max([p.get('pnl', 0) for p in closed_positions], default=0)
        st.metric("Best Trade", f"₹{best_trade:,.2f}")

if __name__ == "__main__":
    main()
