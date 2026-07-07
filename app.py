# app_auth.py - Complete Authentication System
# Run with: streamlit run app_auth.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Import auth modules
from src.database.models import User, UserRole
from src.auth.auth_manager import AuthManager
from src.database.connection import engine, SessionLocal

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# PAGE CONFIG
# ============================================

st.set_page_config(
    page_title="📰 News Intelligence Dashboard",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# SESSION STATE INITIALIZATION
# ============================================

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.user_role = None
    st.session_state.username = None

def get_db_session():
    """Get database session"""
    return SessionLocal()

def get_auth_manager():
    """Get auth manager instance"""
    db = get_db_session()
    return AuthManager(db)

# ============================================
# AUTHENTICATION FUNCTIONS
# ============================================

def login(username, password):
    """Login user"""
    auth = get_auth_manager()
    user = auth.authenticate_user(username, password)
    
    if user:
        st.session_state.authenticated = True
        st.session_state.user = user
        st.session_state.user_role = user.role.value
        st.session_state.username = user.username
        return True
    return False

def logout():
    """Logout user"""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.user_role = None
    st.session_state.username = None
    st.rerun()

def register(username, email, password, full_name):
    """Register new user"""
    auth = get_auth_manager()
    user = auth.create_user(username, email, password, full_name)
    return user

# ============================================
# LOGIN PAGE
# ============================================

def login_page():
    """Display login page"""
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            margin-top: 3rem;
        }
        .login-header {
            text-align: center;
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .login-subheader {
            text-align: center;
            color: #6b7280;
            margin-bottom: 2rem;
        }
        .login-button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.75rem;
            border-radius: 8px;
            width: 100%;
            font-weight: 600;
            cursor: pointer;
        }
        .login-button:hover {
            transform: scale(1.02);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    st.markdown('<div class="login-header">📰 News Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subheader">Sign in to access your dashboard</div>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username or Email", placeholder="Enter your username or email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Sign In", use_container_width=True)
        with col2:
            # Register button goes to register page
            st.markdown("""
            <div style="text-align: right; padding-top: 0.5rem;">
                <a href="#" onclick="window.location.reload();" style="color: #667eea; text-decoration: none;">Register</a>
            </div>
            """, unsafe_allow_html=True)
        
        if submitted:
            if username and password:
                if login(username, password):
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.warning("Please enter both username and password")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================
# REGISTER PAGE
# ============================================

def register_page():
    """Display registration page"""
    st.markdown("""
    <style>
        .register-container {
            max-width: 450px;
            margin: 0 auto;
            padding: 2rem;
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            margin-top: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="register-container">', unsafe_allow_html=True)
    
    st.markdown('<div style="text-align: center; font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem;">📰 Create Account</div>', unsafe_allow_html=True)
    
    with st.form("register_form"):
        full_name = st.text_input("Full Name", placeholder="John Doe")
        username = st.text_input("Username", placeholder="Choose a username")
        email = st.text_input("Email", placeholder="your@email.com")
        password = st.text_input("Password", type="password", placeholder="Create a password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Create Account", use_container_width=True)
        with col2:
            st.markdown("""
            <div style="text-align: center; padding-top: 0.5rem;">
                <a href="#" onclick="window.location.reload();" style="color: #667eea; text-decoration: none;">Back to Login</a>
            </div>
            """, unsafe_allow_html=True)
        
        if submitted:
            if not all([full_name, username, email, password]):
                st.warning("Please fill in all fields")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif len(password) < 6:
                st.warning("Password must be at least 6 characters")
            else:
                user = register(username, email, password, full_name)
                if user:
                    st.success("✅ Account created successfully! Please login.")
                    st.balloons()
                    # Switch to login view
                    st.session_state.show_login = True
                    st.rerun()
                else:
                    st.error("❌ Username or email already exists")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================
# DASHBOARD FUNCTIONS (YOUR EXISTING CODE)
# ============================================

def get_stats():
    """Get dashboard statistics"""
    # Your existing get_stats function here
    return {
        'total': 482,
        'processed': 482,
        'avg_quality': 19.0,
        'languages': {'English': 450, 'Hindi': 32},
        'topics': {'general': 141, 'crime': 26, 'politics': 24, 'business': 23, 'health': 16, 'sports': 14, 'science': 14, 'entertainment': 14},
        'sentiments': {'positive': 31, 'neutral': 442, 'negative': 9},
        'sources': {'BBC': 150, 'CNN': 100, 'NPR': 80, 'Reuters': 70, 'AP': 60, 'The Guardian': 50, 'Al Jazeera': 40, 'TechCrunch': 30, 'The Verge': 25, 'Other': 47},
        'articles_today': 273
    }

def dashboard_page():
    """Display dashboard"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 16px; margin-bottom: 2rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="color: white; margin: 0; font-size: 2rem;">📰 News Intelligence Dashboard</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0;">AI-powered news briefing with sentiment analysis, topic clustering, and real-time insights</p>
            </div>
            <div style="text-align: right; color: white;">
                <div style="font-size: 0.8rem; opacity: 0.7;">Welcome back,</div>
                <div style="font-weight: 600; font-size: 1.1rem;">{st.session_state.username}</div>
                <div style="font-size: 0.7rem; opacity: 0.6;">{st.session_state.user_role.upper()}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get stats
    stats = get_stats()
    
    # Metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    metrics = [
        (col1, "📄", stats['total'], "Total Articles"),
        (col2, "✅", stats['processed'], "Processed"),
        (col3, "⭐", f"{stats['avg_quality']:.1f}", "Avg Quality"),
        (col4, "🌐", len(stats['languages']), "Languages"),
        (col5, "📅", stats['articles_today'], "Today")
    ]
    
    for col, icon, value, label in metrics:
        with col:
            st.markdown(f"""
            <div style="background: white; padding: 1.2rem 1rem; border-radius: 12px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.06);">
                <div style="font-size: 1.5rem;">{icon}</div>
                <div style="font-size: 2rem; font-weight: 700; color: #1a1a2e;">{value}</div>
                <div style="font-size: 0.8rem; color: #6b7280;">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Topic Distribution")
        if stats['topics']:
            df = pd.DataFrame({'Topic': list(stats['topics'].keys()), 'Count': list(stats['topics'].values())})
            fig = px.pie(df, values='Count', names='Topic', hole=0.35)
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Sentiment Distribution")
        if stats['sentiments']:
            df = pd.DataFrame({'Sentiment': list(stats['sentiments'].keys()), 'Count': list(stats['sentiments'].values())})
            colors = {'positive': '#34d399', 'neutral': '#fbbf24', 'negative': '#f87171'}
            fig = px.pie(df, values='Count', names='Sentiment', color='Sentiment', color_discrete_map=colors, hole=0.35)
            fig.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

# ============================================
# ADMIN PANEL
# ============================================

def admin_panel():
    """Display admin panel"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 2rem;">🛡️ Admin Panel</h1>
        <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0;">Manage users, monitor system activity, and view analytics</p>
    </div>
    """, unsafe_allow_html=True)
    
    auth = get_auth_manager()
    users = auth.get_all_users()
    stats = get_stats()
    
    # Admin Stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Users", len(users))
    col2.metric("Admins", len([u for u in users if u.role == UserRole.ADMIN]))
    col3.metric("Total Articles", stats['total'])
    col4.metric("Active Users", len([u for u in users if u.is_active]))
    
    st.markdown("---")
    
    # User Management
    st.subheader("👥 User Management")
    
    # Create admin user if none exists
    auth.create_admin_user()
    users = auth.get_all_users()
    
    if users:
        # User table
        data = []
        for user in users:
            data.append({
                "ID": user.id,
                "Username": user.username,
                "Email": user.email,
                "Full Name": user.full_name or "",
                "Role": "🛡️ Admin" if user.role == UserRole.ADMIN else "👤 User",
                "Active": "✅" if user.is_active else "❌",
                "Joined": user.created_at.strftime("%Y-%m-%d") if user.created_at else "",
                "Last Login": user.last_login.strftime("%Y-%m-%d") if user.last_login else "Never"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # User actions
        st.subheader("🔧 User Actions")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            user_options = [f"{u.id} - {u.username}" for u in users]
            selected_user = st.selectbox("Select User", user_options)
            user_id = int(selected_user.split(" - ")[0])
        
        with col2:
            action = st.selectbox("Action", ["Promote to Admin", "Demote to User", "Delete User"])
        
        with col3:
            if st.button("Execute Action", type="primary"):
                if action == "Promote to Admin":
                    if auth.promote_to_admin(user_id):
                        st.success("✅ User promoted to admin!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to promote user")
                elif action == "Demote to User":
                    if auth.demote_to_user(user_id):
                        st.success("✅ User demoted!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to demote user")
                elif action == "Delete User":
                    if auth.delete_user(user_id):
                        st.success("✅ User deleted!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete user")
    else:
        st.info("No users found.")

# ============================================
# MAIN APP
# ============================================

def main():
    """Main application"""
    
    # Check authentication
    if not st.session_state.authenticated:
        # Show login/register
        # Simple toggle between login and register
        if 'show_login' not in st.session_state:
            st.session_state.show_login = True
        
        # Check if register button was clicked
        if 'register_clicked' not in st.session_state:
            st.session_state.register_clicked = False
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.session_state.get('show_login', True):
                login_page()
                st.markdown("---")
                st.markdown('<div style="text-align: center;">Don\'t have an account? <a href="#" onclick="window.location.reload();" style="color: #667eea; text-decoration: none;">Register</a></div>', unsafe_allow_html=True)
                # Toggle to register
                if st.button("Register", key="register_toggle", use_container_width=True):
                    st.session_state.show_login = False
                    st.rerun()
            else:
                register_page()
                st.markdown("---")
                st.markdown('<div style="text-align: center;">Already have an account? <a href="#" onclick="window.location.reload();" style="color: #667eea; text-decoration: none;">Login</a></div>', unsafe_allow_html=True)
                if st.button("Login", key="login_toggle", use_container_width=True):
                    st.session_state.show_login = True
                    st.rerun()
    else:
        # Authenticated user
        # Sidebar
        with st.sidebar:
            st.markdown("""
            <div style="text-align: center; padding: 0.5rem 0;">
                <div style="font-size: 2.5rem;">📰</div>
                <h3 style="color: #1a1a2e; margin: 0;">News Intel</h3>
                <p style="color: #6b7280; font-size: 0.75rem;">Intelligence Briefing Agent</p>
                <div style="margin-top: 0.5rem; padding: 0.3rem 1rem; background: #f3f4f6; border-radius: 20px; font-size: 0.7rem; display: inline-block;">
                    {st.session_state.user_role.upper()}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Navigation
            if st.session_state.user_role == "admin":
                nav_options = ["📊 Dashboard", "📰 Articles", "📈 Analytics", "🔍 Search", "🛡️ Admin Panel"]
            else:
                nav_options = ["📊 Dashboard", "📰 Articles", "📈 Analytics", "🔍 Search"]
            
            selection = st.radio("Navigation", nav_options, index=0, label_visibility="collapsed")
            
            st.markdown("---")
            
            # User info
            st.markdown(f"""
            <div style="padding: 0.5rem; background: #f8f9fa; border-radius: 8px; font-size: 0.8rem;">
                <div style="font-weight: 600;">👤 {st.session_state.username}</div>
                <div style="color: #6b7280;">{st.session_state.user.email if st.session_state.user else ''}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            if st.button("🚪 Logout", use_container_width=True):
                logout()
        
        # Content
        if selection == "📊 Dashboard":
            dashboard_page()
        elif selection == "📰 Articles":
            st.info("📰 Articles page - Add your articles display here")
        elif selection == "📈 Analytics":
            st.info("📈 Analytics page - Add your analytics here")
        elif selection == "🔍 Search":
            st.info("🔍 Search page - Add your search functionality here")
        elif selection == "🛡️ Admin Panel" and st.session_state.user_role == "admin":
            admin_panel()

if __name__ == "__main__":
    main()