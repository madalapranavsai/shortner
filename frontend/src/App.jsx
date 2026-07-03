import React, { useState, useEffect } from 'react';
import { 
  Bolt, 
  ArrowRight, 
  Link as LinkIcon, 
  Copy, 
  Plus, 
  RotateCw, 
  Trash2, 
  User as UserIcon, 
  Lock, 
  LogOut, 
  FolderOpen,
  Cpu,
  Zap,
  ShieldAlert
} from 'lucide-react';

const API_BASE = window.location.origin;

function App() {
  // Authentication & Navigation State
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [currentView, setCurrentView] = useState('guest'); // 'guest' | 'auth' | 'dashboard'
  const [authTab, setAuthTab] = useState('login'); // 'login' | 'register'

  // Input States
  const [guestLongUrl, setGuestLongUrl] = useState('');
  const [guestShortUrl, setGuestShortUrl] = useState('');
  const [dashboardLongUrl, setDashboardLongUrl] = useState('');
  
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');

  // Status & Error Messages
  const [loginError, setLoginError] = useState('');
  const [registerError, setRegisterError] = useState('');
  const [registerSuccess, setRegisterSuccess] = useState(false);

  // Data List & Loading States
  const [urls, setUrls] = useState([]);
  const [isLoadingUrls, setIsLoadingUrls] = useState(false);
  const [isSubmittingGuest, setIsSubmittingGuest] = useState(false);
  const [isSubmittingAuth, setIsSubmittingAuth] = useState(false);
  const [isSubmittingDashboard, setIsSubmittingDashboard] = useState(false);

  // Toast Notification State
  const [toastText, setToastText] = useState('');
  const [showToast, setShowToast] = useState(false);

  // Sync Views with Token
  useEffect(() => {
    if (token) {
      setCurrentView('dashboard');
      fetchUserUrls();
    } else {
      setCurrentView('guest');
      setUrls([]);
    }
  }, [token]);

  // --- API Client wrapper ---
  const requestApi = async (endpoint, method = 'GET', body = null, authToken = '') => {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const config = { method, headers };
    if (body) {
      config.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE}${endpoint}`, config);

    if (response.status === 204) {
      return null;
    }

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Request failed');
    }
    return data;
  };

  // --- Fetch Dashboard URLs ---
  const fetchUserUrls = async () => {
    setIsLoadingUrls(true);
    try {
      const data = await requestApi('/my-urls', 'GET', null, token);
      setUrls(data);
    } catch (err) {
      triggerToast('Session expired. Please log in.');
      handleLogout();
    } finally {
      setIsLoadingUrls(false);
    }
  };

  // --- Guest Shortening Action ---
  const handleGuestShorten = async (e) => {
    e.preventDefault();
    if (!guestLongUrl.trim()) return;

    setIsSubmittingGuest(true);
    setGuestShortUrl('');
    
    try {
      const data = await requestApi('/shorten', 'POST', { url: guestLongUrl.trim() });
      setGuestShortUrl(data.short_url);
    } catch (err) {
      triggerToast('Failed to shorten: ' + err.message);
    } finally {
      setIsSubmittingGuest(false);
    }
  };

  // --- Dashboard Shortening Action ---
  const handleDashboardShorten = async (e) => {
    e.preventDefault();
    if (!dashboardLongUrl.trim()) return;

    setIsSubmittingDashboard(true);
    
    try {
      await requestApi('/shorten', 'POST', { url: dashboardLongUrl.trim() }, token);
      setDashboardLongUrl('');
      triggerToast('Link shortened!');
      fetchUserUrls(); // Refresh table list
    } catch (err) {
      triggerToast('Failed to shorten: ' + err.message);
    } finally {
      setIsSubmittingDashboard(false);
    }
  };

  // --- Authentication Actions ---
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    setIsSubmittingAuth(true);

    try {
      const res = await requestApi('/auth/login', 'POST', {
        username: loginUsername.trim(),
        password: loginPassword
      });
      localStorage.setItem('token', res.access_token);
      setToken(res.access_token);
      
      // Clear fields
      setLoginUsername('');
      setLoginPassword('');
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setIsSubmittingAuth(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setRegisterError('');
    setRegisterSuccess(false);
    setIsSubmittingAuth(true);

    try {
      await requestApi('/auth/register', 'POST', {
        username: registerUsername.trim(),
        password: registerPassword
      });
      setRegisterSuccess(true);
      setRegisterUsername('');
      setRegisterPassword('');
      
      // Switch tabs automatically
      setTimeout(() => {
        setAuthTab('login');
      }, 1500);
    } catch (err) {
      setRegisterError(err.message);
    } finally {
      setIsSubmittingAuth(false);
    }
  };

  const handleDeleteUrl = async (shortCode) => {
    if (!confirm('Are you sure you want to delete this short URL? This will immediately invalidate cache records.')) {
      return;
    }

    try {
      await fetch(`${API_BASE}/${shortCode}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      triggerToast('Link deleted successfully.');
      fetchUserUrls();
    } catch (err) {
      triggerToast('Failed to delete link.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
  };

  // --- Helper Operations ---
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      triggerToast('Link copied to clipboard!');
    }).catch(() => {
      triggerToast('Failed to copy link.');
    });
  };

  const triggerToast = (msg) => {
    setToastText(msg);
    setShowToast(true);
    setTimeout(() => {
      setShowToast(false);
    }, 2000);
  };

  return (
    <>
      <div className="background-glow-1"></div>
      <div className="background-glow-2"></div>

      <div className="container">
        {/* Navigation Header */}
        <header className="header">
          <div className="logo" style={{ cursor: 'pointer' }} onClick={() => token ? setCurrentView('dashboard') : setCurrentView('guest')}>
            <Bolt className="logo-icon hover-rotate" />
            <span className="logo-text">Bolt</span>
          </div>
          <div className="nav-auth">
            {token ? (
              <>
                <span className="user-greeting">
                  <UserIcon size={16} /> Dashboard Active
                </span>
                <button className="btn btn-secondary" onClick={handleLogout}>
                  <LogOut size={16} />
                  <span>Sign Out</span>
                </button>
              </>
            ) : (
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  setAuthTab('login');
                  setCurrentView('auth');
                }}
              >
                <UserIcon size={16} />
                <span>Sign In</span>
              </button>
            )}
          </div>
        </header>

        {/* Main Wrapper */}
        <main className="main-content">
          {/* 1. GUEST LANDING VIEW */}
          {currentView === 'guest' && (
            <section className="view-section">
              <div className="hero">
                <h1 className="hero-title">Shorten URLs.<br /><span className="gradient-text">Track Performance.</span></h1>
                <p className="hero-subtitle">Generate secure time-based Snowflake codes, cached for sub-millisecond redirect speeds, backed by distributed token-bucket rate limits.</p>
              </div>

              <div className="card glass shortener-card">
                <form onSubmit={handleGuestShorten} className="shorten-form">
                  <div className="input-group">
                    <div style={{ position: 'relative', flexGrow: 1, display: 'flex', alignItems: 'center' }}>
                      <LinkIcon size={18} style={{ position: 'absolute', left: '1.25rem', color: 'var(--text-secondary)' }} />
                      <input 
                        type="url" 
                        value={guestLongUrl}
                        onChange={(e) => setGuestLongUrl(e.target.value)}
                        placeholder="Paste your long link here..." 
                        required 
                        style={{ paddingLeft: '3rem', width: '100%' }}
                        disabled={isSubmittingGuest}
                      />
                    </div>
                    <button type="submit" className="btn btn-primary btn-large" disabled={isSubmittingGuest}>
                      {isSubmittingGuest ? (
                        <span className="spinner"></span>
                      ) : (
                        <>
                          <span>Shorten</span>
                          <ArrowRight size={18} />
                        </>
                      )}
                    </button>
                  </div>
                </form>
                
                {guestShortUrl && (
                  <div className="result-area">
                    <p className="result-label">Your shortened link:</p>
                    <div className="result-box">
                      <a href={guestShortUrl} target="_blank" rel="noreferrer" className="short-link-href">{guestShortUrl}</a>
                      <button className="btn btn-copy" onClick={() => copyToClipboard(guestShortUrl)}>
                        <Copy size={14} />
                        <span>Copy</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="features-grid">
                <div className="feature-card glass">
                  <Cpu className="feature-icon" />
                  <h3>Snowflake IDs</h3>
                  <p>Time-ordered 64-bit non-predictable codes mapped into Base62.</p>
                </div>
                <div className="feature-card glass">
                  <Zap className="feature-icon" />
                  <h3>Redis Caching</h3>
                  <p>Sub-millisecond redirect lookups using a memory caching layer.</p>
                </div>
                <div className="feature-card glass">
                  <ShieldAlert className="feature-icon" />
                  <h3>Token Limiter</h3>
                  <p>Self-built IP and API key rate limiting using atomic Redis Lua scripts.</p>
                </div>
              </div>
            </section>
          )}

          {/* 2. LOGIN / REGISTER VIEW */}
          {currentView === 'auth' && (
            <section className="view-section">
              <div className="auth-box card glass">
                <div className="auth-tabs">
                  <button 
                    className={`auth-tab ${authTab === 'login' ? 'active' : ''}`}
                    onClick={() => switchAuthTab('login')}
                  >
                    Sign In
                  </button>
                  <button 
                    className={`auth-tab ${authTab === 'register' ? 'active' : ''}`}
                    onClick={() => switchAuthTab('register')}
                  >
                    Sign Up
                  </button>
                </div>

                {/* Login Form */}
                {authTab === 'login' && (
                  <form onSubmit={handleLogin} className="auth-form active">
                    <h2 className="auth-title">Welcome Back</h2>
                    <p className="auth-subtitle">Sign in to manage and track your shortened URLs.</p>
                    <div className="form-group">
                      <label>Username</label>
                      <div className="input-wrapper">
                        <UserIcon size={16} />
                        <input 
                          type="text" 
                          value={loginUsername}
                          onChange={(e) => setLoginUsername(e.target.value)}
                          required 
                          placeholder="Enter username" 
                          disabled={isSubmittingAuth}
                        />
                      </div>
                    </div>
                    <div className="form-group">
                      <label>Password</label>
                      <div className="input-wrapper">
                        <Lock size={16} />
                        <input 
                          type="password" 
                          value={loginPassword}
                          onChange={(e) => setLoginPassword(e.target.value)}
                          required 
                          placeholder="Enter password" 
                          disabled={isSubmittingAuth}
                        />
                      </div>
                    </div>
                    <button type="submit" className="btn btn-primary btn-full" disabled={isSubmittingAuth}>
                      {isSubmittingAuth ? (
                        <span className="spinner"></span>
                      ) : (
                        <>
                          <span>Sign In</span>
                          <ArrowRight size={16} />
                        </>
                      )}
                    </button>
                    {loginError && <div className="error-msg">{loginError}</div>}
                  </form>
                )}

                {/* Register Form */}
                {authTab === 'register' && (
                  <form onSubmit={handleRegister} className="auth-form active">
                    <h2 class="auth-title">Create Account</h2>
                    <p class="auth-subtitle">Get user dashboard access, stats history, and URL management.</p>
                    <div className="form-group">
                      <label>Username</label>
                      <div className="input-wrapper">
                        <UserIcon size={16} />
                        <input 
                          type="text" 
                          value={registerUsername}
                          onChange={(e) => setRegisterUsername(e.target.value)}
                          required 
                          placeholder="Choose a username" 
                          disabled={isSubmittingAuth}
                        />
                      </div>
                    </div>
                    <div className="form-group">
                      <label>Password</label>
                      <div className="input-wrapper">
                        <Lock size={16} />
                        <input 
                          type="password" 
                          value={registerPassword}
                          onChange={(e) => setRegisterPassword(e.target.value)}
                          required 
                          placeholder="Choose a secure password" 
                          disabled={isSubmittingAuth}
                        />
                      </div>
                    </div>
                    <button type="submit" className="btn btn-primary btn-full" disabled={isSubmittingAuth}>
                      {isSubmittingAuth ? (
                        <span className="spinner"></span>
                      ) : (
                        <>
                          <span>Create Account</span>
                          <ArrowRight size={16} />
                        </>
                      )}
                    </button>
                    {registerError && <div className="error-msg">{registerError}</div>}
                    {registerSuccess && <div className="success-msg">Account created! Switching to sign in...</div>}
                  </form>
                )}
              </div>
            </section>
          )}

          {/* 3. DASHBOARD VIEW */}
          {currentView === 'dashboard' && (
            <section className="view-section">
              <div className="dashboard-header">
                <div>
                  <h1 className="dashboard-title">Developer Dashboard</h1>
                  <p className="dashboard-subtitle">Manage your shortened URLs and inspect real-time click statistics.</p>
                </div>
                <button className="btn btn-secondary" onClick={fetchUserUrls} disabled={isLoadingUrls}>
                  <RotateCw size={16} className={isLoadingUrls ? 'spinner' : ''} />
                  <span>Refresh</span>
                </button>
              </div>

              {/* Shortener Form */}
              <div className="card glass shortener-card-dashboard">
                <form onSubmit={handleDashboardShorten} className="shorten-form">
                  <div className="input-group">
                    <div style={{ position: 'relative', flexGrow: 1, display: 'flex', alignItems: 'center' }}>
                      <LinkIcon size={18} style={{ position: 'absolute', left: '1.25rem', color: 'var(--text-secondary)' }} />
                      <input 
                        type="url" 
                        value={dashboardLongUrl}
                        onChange={(e) => setDashboardLongUrl(e.target.value)}
                        placeholder="Paste a link to shorten under your account..." 
                        required 
                        style={{ paddingLeft: '3rem', width: '100%' }}
                        disabled={isSubmittingDashboard}
                      />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={isSubmittingDashboard}>
                      {isSubmittingDashboard ? (
                        <span className="spinner"></span>
                      ) : (
                        <>
                          <span>Shorten</span>
                          <Plus size={16} />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>

              {/* URL Dashboard Analytics List */}
              <div className="card glass table-card">
                <div className="table-header">
                  <h3>Your Short Links</h3>
                  <span className="badge">{urls.length} Link{urls.length === 1 ? '' : 's'}</span>
                </div>
                <div className="table-wrapper">
                  <table className="urls-table">
                    <thead>
                      <tr>
                        <th>Short Link</th>
                        <th>Original Destination</th>
                        <th>Created At</th>
                        <th>Clicks</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {isLoadingUrls ? (
                        // Render animated skeleton loaders while URLs fetch
                        Array.from({ length: 3 }).map((_, idx) => (
                          <tr key={idx}>
                            <td>
                              <span className="skeleton skeleton-text" style={{ width: '80px' }}></span>
                            </td>
                            <td>
                              <span className="skeleton skeleton-text" style={{ width: '250px' }}></span>
                            </td>
                            <td>
                              <span className="skeleton skeleton-text" style={{ width: '100px' }}></span>
                            </td>
                            <td>
                              <span className="skeleton skeleton-text" style={{ width: '40px' }}></span>
                            </td>
                            <td>
                              <span className="skeleton skeleton-text" style={{ width: '120px' }}></span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        urls.map(url => {
                          const dateObj = new Date(url.created_at);
                          const formattedDate = dateObj.toLocaleDateString(undefined, { 
                            year: 'numeric', month: 'short', day: 'numeric' 
                          });

                          return (
                            <tr key={url.id}>
                              <td>
                                <a href={url.short_url} target="_blank" rel="noreferrer" className="short-link-href">
                                  {url.short_code}
                                </a>
                              </td>
                              <td>
                                <div className="destination-url" title={url.long_url}>
                                  {url.long_url}
                                </div>
                              </td>
                              <td style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                                {formattedDate}
                              </td>
                              <td>
                                <span className={`clicks-badge ${url.click_count > 0 ? 'active-clicks' : ''}`}>
                                  {url.click_count}
                                </span>
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                  <button className="btn btn-copy" onClick={() => copyToClipboard(url.short_url)}>
                                    <Copy size={12} />
                                  </button>
                                  <button className="btn btn-danger" onClick={() => handleDeleteUrl(url.short_code)}>
                                    <Trash2 size={12} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {!isLoadingUrls && urls.length === 0 && (
                  <div className="empty-state">
                    <FolderOpen className="empty-icon" />
                    <h4>No links generated yet</h4>
                    <p>Shorten your first link above to start tracking clicks.</p>
                  </div>
                )}
              </div>
            </section>
          )}
        </main>
      </div>

      {/* Notification Toast */}
      <div className={`toast ${showToast ? 'show' : ''}`}>
        {toastText}
      </div>
    </>
  );

  function switchAuthTab(tab) {
    setAuthTab(tab);
    setLoginError('');
    setRegisterError('');
    setRegisterSuccess(false);
  }
}

export default App;
