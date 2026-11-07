import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';

import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type Dispatch, type FormEvent, type ReactNode, type SetStateAction } from 'react';




const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const SESSION_ID_KEY = 'job_hunt_session_id';



type NavItem = 'Dashboard' | 'Job Search' | 'My Applications' | 'Resume Analyzer' | 'AI Assistant' | 'Saved Jobs' | 'Alerts & Automation' | 'Settings';

type SortKey = 'combined_score' | 'ats_score' | 'semantic_score';

type ApplicationStatus = 'Applied' | 'Interview' | 'Shortlisted' | 'Offer' | 'Rejected';

type Job = {

  title: string;

  company: string;

  location: string;

  url: string;

  description: string;

  source: string;

  ats_score?: number | string;

  semantic_score?: number | string;

  combined_score?: number | string;

  matched_skills?: string[];

};



type Message = {

  role: 'user' | 'agent';

  content: string;

  jobs?: Job[];

};



type ApplicationRecord = {

  id: number;

  company: string;

  role: string;

  appliedDate: string;

  status: ApplicationStatus;

  nextAction: string;

  interviewDate: string;

  notes: string;
};

type AlertStatus = 'Enabled' | 'Paused';

type AlertRecord = {
  id: number;
  name: string;
  description: string;
  status: AlertStatus;
  lastRun: string;
  nextRun: string;
};

type AlertApiRecord = Omit<AlertRecord, 'lastRun' | 'nextRun'> & {
  last_run: string;
  next_run: string;
};

type AlertForm = Omit<AlertRecord, 'id'>;

type ToastMessage = {
  id: number;
  message: string;
  kind: 'success' | 'error';
};

function getAuthorizationHeaders(): Record<string, string> {
  const token = sessionStorage.getItem('jobhunt_access_token');
  if (!token) {
    throw new Error('Your session has expired. Please sign in again.');
  }
  return { Authorization: `Bearer ${token}` };
}

function toAlertRecord(alert: AlertApiRecord): AlertRecord {
  return {
    id: alert.id,
    name: alert.name,
    description: alert.description,
    status: alert.status,
    lastRun: alert.last_run,
    nextRun: alert.next_run,
  };
}

function toAlertPayload(alert: AlertForm) {
  return {
    name: alert.name.trim(),
    description: alert.description.trim(),
    status: alert.status,
    last_run: alert.lastRun.trim(),
    next_run: alert.nextRun.trim(),
  };
}

async function getResponseError(response: Response, fallback: string): Promise<string> {
  const payload: unknown = await response.json().catch(() => null);
  if (
    payload &&
    typeof payload === 'object' &&
    'detail' in payload &&
    typeof payload.detail === 'string'
  ) {
    return payload.detail;
  }
  return fallback;
}

function useToast() {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const notify = useCallback((message: string, kind: ToastMessage['kind'] = 'success') => {
    setToast({ id: Date.now() + Math.random(), message, kind });
  }, []);
  const dismiss = useCallback(() => setToast(null), []);

  return { toast, notify, dismiss };
}

function ToastRegion({ toast, onDismiss }: {
  toast: ToastMessage | null;
  onDismiss: () => void;
}) {
  if (!toast) return null;

  return (
    <div
      key={toast.id}
      className={`app-toast app-toast--${toast.kind}`}
      role={toast.kind === 'error' ? 'alert' : 'status'}
      aria-live={toast.kind === 'error' ? 'assertive' : 'polite'}
    >
      <span className="app-toast-icon" aria-hidden="true">{toast.kind === 'success' ? '✓' : '!'}</span>
      <span>{toast.message}</span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss notification">×</button>
    </div>
  );
}

function ModalDialog({ title, children, onClose, wide = false }: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <div
      className="app-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className={`app-modal${wide ? ' app-modal--wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="app-modal-title"
        onKeyDown={(event) => {
          if (event.key === 'Escape') onClose();
        }}
        tabIndex={-1}
      >
        <div className="app-modal-heading">
          <div>
            <span className="app-modal-eyebrow">JOBHUNT AI · AUTOMATION</span>
            <h2 id="app-modal-title">{title}</h2>
          </div>
          <button type="button" className="app-modal-close" onClick={onClose} aria-label="Close dialog">×</button>
        </div>
        {children}
      </section>
    </div>
  );
}



function getSessionId() {
  const existing = sessionStorage.getItem(SESSION_ID_KEY);

  if (existing) {
    console.log("Existing Session ID:", existing);
    return existing;
  }

  const next = crypto.randomUUID();

  sessionStorage.setItem(SESSION_ID_KEY, next);

  console.log("New Session ID:", next);

  return next;
}



function clearAuthSession() {

  sessionStorage.removeItem(SESSION_ID_KEY);

  sessionStorage.removeItem('jobhunt_access_token');

  sessionStorage.removeItem('jobhunt_authenticated');

  sessionStorage.removeItem('jobhunt_user_email');

  sessionStorage.removeItem('jobhunt_user_name');

}



function readSavedJobs(): Job[] {

  try {

    const raw = localStorage.getItem('jobhunt_saved_jobs');

    if (!raw) return [];

    const parsed = JSON.parse(raw);

    return Array.isArray(parsed) ? parsed : [];

  } catch {

    return [];

  }

}



function readApplications(): ApplicationRecord[] {

  try {

    const raw = localStorage.getItem('jobhunt_applications');

    if (!raw) return [];

    const parsed = JSON.parse(raw);

    return Array.isArray(parsed) ? parsed : [];

  } catch {

    return [];

  }

}



function App() {

  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const [authReady, setAuthReady] = useState(false);

  const [currentUserName, setCurrentUserName] = useState('Kiran Kavala');

  const [messages, setMessages] = useState<Message[]>([

    {

      role: 'agent',

      content: 'Hi! Upload your resume and I will find the best-fit jobs for you.',

    },

  ]);

  const [input, setInput] = useState('');

  const [isLoading, setIsLoading] = useState(false);

  const [searchError, setSearchError] = useState('');

  const [resumeName, setResumeName] = useState<string | null>(null);

  const [resumeSkills, setResumeSkills] = useState<string[]>([]);

  const [resumeMatchScore, setResumeMatchScore] = useState<number | null>(null);

  const [uploading, setUploading] = useState(false);

  const [atsThreshold, setAtsThreshold] = useState(0);

  const [semanticThreshold, setSemanticThreshold] = useState(0);

  const [remoteOnly, setRemoteOnly] = useState(false);

  const [includeInternships, setIncludeInternships] = useState(true);

  const [fresherFriendly, setFresherFriendly] = useState(false);

  const [mySkillsMatch, setMySkillsMatch] = useState(false);

  const [sortKey, setSortKey] = useState<SortKey>('combined_score');

  const [selectedTab, setSelectedTab] = useState<'All Jobs' | 'High Match' | 'Internship' | 'Fresher'>('All Jobs');

  const [activeSource, setActiveSource] = useState<string | null>(null);



  useEffect(() => {

    const token = sessionStorage.getItem('jobhunt_access_token');

    const authenticated = sessionStorage.getItem('jobhunt_authenticated') === 'true';



    if (!token || !authenticated) {

      setIsAuthenticated(false);

      setAuthReady(true);

      return;

    }



    fetch(`${API_BASE_URL}/api/auth/me`, {

      headers: { Authorization: `Bearer ${token}` },

    })

      .then(async (response) => {

        if (!response.ok) {

          clearAuthSession();

          setIsAuthenticated(false);

          setAuthReady(true);

          return;

        }



        const data = await response.json();

        const nextName = data.user?.full_name || sessionStorage.getItem('jobhunt_user_name') || 'Kiran Kavala';

        sessionStorage.setItem('jobhunt_user_name', nextName);

        setCurrentUserName(nextName);

        setIsAuthenticated(true);

        setAuthReady(true);

      })

      .catch(() => {

        clearAuthSession();

        setIsAuthenticated(false);

        setAuthReady(true);

      });

  }, []);



  const latestJobs = useMemo(() => {

    for (let i = messages.length - 1; i >= 0; i -= 1) {

      const message = messages[i];

      if (message.jobs && message.jobs.length > 0) return message.jobs;

    }

    return [];

  }, [messages]);

  const topMatch = latestJobs.length
  ? Math.max(
      ...latestJobs.map((job) => Number(job.combined_score ?? 0))
    )
  : 0;



  const filteredJobs = useMemo(() => {
    // Normalize backend score values whether they arrive as 0.35, 35, or "35".
    // Missing ATS scores remain 0; do not substitute the combined/match score,
    // because ATS and semantic scores are separate measurements.
    const scoreAsPercent = (score: number | string | undefined) => {
      if (score == null || score === '') return 0;
      const numericScore = Number(score);
      if (!Number.isFinite(numericScore)) return 0;
      return numericScore <= 1 ? numericScore * 100 : numericScore;
    };

    const isInternship = (job: Job) =>
      /intern(ship)?/i.test(`${job.title || ''} ${job.description || ''}`);

    const isFresherRole = (job: Job) =>
      /fresher|entry[- ]level|junior|graduate|trainee|intern(ship)?|new grad/i.test(
        `${job.title || ''} ${job.description || ''}`,
      );

    const isRemote = (job: Job) =>
      /remote|work from home|work-from-home|wfh|anywhere/i.test(
        `${job.location || ''} ${job.title || ''} ${job.description || ''}`,
      );

    const matchesMySkills = (job: Job) => {
      const skills = Array.isArray(job.matched_skills) ? job.matched_skills : [];
      if (resumeSkills.length) {
        const resumeSkillSet = new Set(resumeSkills.map((skill) => skill.toLowerCase().trim()));
        return skills.some((skill) => resumeSkillSet.has(String(skill).toLowerCase().trim()));
      }
      // Without an uploaded resume, use the backend's matched_skills when it exists.
      return skills.length > 0;
    };

    return latestJobs
      // A zero threshold means "don't filter by this score". Some source listings
      // do not carry ATS/semantic scores, so those jobs should remain visible.
      .filter((job) => atsThreshold <= 0 || scoreAsPercent(job.ats_score) >= atsThreshold)
      .filter((job) => semanticThreshold <= 0 || scoreAsPercent(job.semantic_score) >= semanticThreshold)
      .filter((job) => (activeSource ? job.source === activeSource : true))
      .filter((job) => {
        if (selectedTab === 'High Match') return scoreAsPercent(job.combined_score) >= 70;
        if (selectedTab === 'Internship') return isInternship(job);
        if (selectedTab === 'Fresher') return isFresherRole(job);
        return true;
      })
      .filter((job) => (remoteOnly ? isRemote(job) : true))
      .filter((job) => (includeInternships ? true : !isInternship(job)))
      .filter((job) => (fresherFriendly ? isFresherRole(job) : true))
      .filter((job) => (mySkillsMatch ? matchesMySkills(job) : true))
      .sort((a, b) => scoreAsPercent(b[sortKey]) - scoreAsPercent(a[sortKey]));
  }, [
    latestJobs, atsThreshold, semanticThreshold, activeSource, selectedTab, sortKey,
    remoteOnly, includeInternships, fresherFriendly, mySkillsMatch, resumeSkills,
  ]);

  const sourceCounts = useMemo(() => {

    const counts: Record<string, number> = {};

    latestJobs.forEach((job) => {

      const source = job.source || 'Unknown';

      counts[source] = (counts[source] || 0) + 1;

    });

    return Object.entries(counts).sort((a, b) => b[1] - a[1]);

  }, [latestJobs]);



  const handleSearch = async (override?: string) => {

    const query = (override ?? input).trim();

    if (!query) return;



    setMessages((prev) => [...prev, { role: 'user', content: query }]);

    setInput('');

    setSearchError('');

    setIsLoading(true);

    setAtsThreshold(0);

    setSemanticThreshold(0);

    setSelectedTab('All Jobs');

    setActiveSource(null);

    setSortKey('combined_score');



    try {

      const response = await fetch(`${API_BASE_URL}/api/chat`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

          'X-Session-ID': getSessionId(),

        },

        body: JSON.stringify({ message: query }),

      });



      const data = await response.json();

      if (!response.ok) throw new Error(data.detail || 'Unable to fetch jobs.');



      setMessages((prev) => [

        ...prev,

        {

          role: 'agent',

          content: data.reply || 'No response from agent.',

          jobs: Array.isArray(data.jobs) ? data.jobs : [],

        },

      ]);

    } catch (error) {

      const message = error instanceof Error ? error.message : 'Unable to reach backend.';

      setSearchError(message);

      setMessages((prev) => [

        ...prev,

        {

          role: 'agent',

          content: `I hit an issue while searching: ${message}`,

        },

      ]);

    } finally {

      setIsLoading(false);

    }

  };



  const handleUploadResume = async (event: ChangeEvent<HTMLInputElement>) => {

    const file = event.target.files?.[0];

    if (!file) return;

    if (file.type !== 'application/pdf') {

      window.alert('Please upload a PDF file.');

      return;

    }



    const form = new FormData();

    form.append('file', file);

    setUploading(true);



    try {

      const response = await fetch(`${API_BASE_URL}/api/upload_resume`, {

        method: 'POST',

        headers: { 'X-Session-ID': getSessionId() },

        body: form,

      });



      const data = await response.json();

      if (!response.ok) throw new Error(data.detail || 'Resume upload failed.');



      setResumeName(file.name);

      setResumeSkills(Array.isArray(data.skills) ? data.skills : []);

      setMessages((prev) => [

        ...prev,

        {

          role: 'agent',

          content: `Resume parsed successfully: ${file.name}. I can use this profile for ATS scoring and matching.`,

        },

      ]);

    } catch (error) {

      window.alert(error instanceof Error ? error.message : 'Resume upload failed.');

    } finally {

      setUploading(false);

      event.target.value = '';

    }

  };



  if (!authReady) {

    return <div className="loading-screen">Loading JobHunt AI...</div>;

  }



  return (

    <BrowserRouter>

      <Routes>

        <Route path="/" element={<Navigate to={isAuthenticated ? '/dashboard' : '/welcome'} replace />} />

        <Route path="/welcome" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <WelcomePage />} />

        <Route path="/signin" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <AuthPage mode="signin" onSuccess={(name) => { setCurrentUserName(name); setIsAuthenticated(true); }} />} />

        <Route path="/register" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <AuthPage mode="register" onSuccess={(name) => { setCurrentUserName(name); setIsAuthenticated(true); }} />} />

        <Route
  path="/dashboard"
  element={
    <ProtectedRoute isAuthenticated={isAuthenticated}>
      <AppLayout
        currentUserName={currentUserName}
        onLogout={() => {
          clearAuthSession();
          setIsAuthenticated(false);
          setCurrentUserName("Kiran Kavala");
        }}
      >
        <DashboardPage
          latestJobs={latestJobs}
          topMatch={topMatch}
          resumeName={resumeName}
          resumeSkills={resumeSkills}
          input={input}
          setInput={setInput}
          onSearch={handleSearch}
          isLoading={isLoading}
          onUpload={handleUploadResume}
          isUploading={uploading}
          resumeMatchScore={resumeMatchScore}
          />
              </AppLayout>
            </ProtectedRoute>
          }
        />

        <Route path="/jobs" element={<ProtectedRoute isAuthenticated={isAuthenticated}><AppLayout currentUserName={currentUserName} onLogout={() => { clearAuthSession(); setIsAuthenticated(false); setCurrentUserName('Kiran Kavala'); }}><JobSearchPage jobs={latestJobs} filteredJobs={filteredJobs} allSources={sourceCounts} input={input} setInput={setInput} onSearch={handleSearch} isLoading={isLoading} searchError={searchError} atsThreshold={atsThreshold} setAtsThreshold={setAtsThreshold} semanticThreshold={semanticThreshold} setSemanticThreshold={setSemanticThreshold} sortKey={sortKey} setSortKey={setSortKey} selectedTab={selectedTab} setSelectedTab={setSelectedTab} activeSource={activeSource} setActiveSource={setActiveSource} remoteOnly={remoteOnly} setRemoteOnly={setRemoteOnly} includeInternships={includeInternships} setIncludeInternships={setIncludeInternships} fresherFriendly={fresherFriendly} setFresherFriendly={setFresherFriendly} mySkillsMatch={mySkillsMatch} setMySkillsMatch={setMySkillsMatch} /></AppLayout></ProtectedRoute>} />

        <Route path="/applications" element={<ProtectedRoute isAuthenticated={isAuthenticated}><AppLayout currentUserName={currentUserName} onLogout={() => { clearAuthSession(); setIsAuthenticated(false); setCurrentUserName('Kiran Kavala'); }}><ApplicationsPage /></AppLayout></ProtectedRoute>} />

        <Route path="/resume-analyzer" element={<ProtectedRoute isAuthenticated={isAuthenticated}><AppLayout currentUserName={currentUserName} onLogout={() => { clearAuthSession(); setIsAuthenticated(false); setCurrentUserName('Kiran Kavala'); }}><ResumeAnalyzerPage
                resumeName={resumeName}
                resumeSkills={resumeSkills}
                onUpload={handleUploadResume}
                isUploading={uploading}
                setResumeMatchScore={setResumeMatchScore}
              /></AppLayout></ProtectedRoute>} />
        <Route path="/saved-jobs" element={<ProtectedRoute isAuthenticated={isAuthenticated}><AppLayout currentUserName={currentUserName} onLogout={() => { clearAuthSession(); setIsAuthenticated(false); setCurrentUserName('Kiran Kavala'); }}><SavedJobsPage /></AppLayout></ProtectedRoute>} />
        <Route path="/alerts" element={<ProtectedRoute isAuthenticated={isAuthenticated}><AppLayout currentUserName={currentUserName} onLogout={() => { clearAuthSession(); setIsAuthenticated(false); setCurrentUserName('Kiran Kavala'); }}><AlertsPage /></AppLayout></ProtectedRoute>} />

        <Route path="/settings" element={<ProtectedRoute isAuthenticated={isAuthenticated}><AppLayout currentUserName={currentUserName} onLogout={() => { clearAuthSession(); setIsAuthenticated(false); setCurrentUserName('Kiran Kavala'); }}><SettingsPage onProfileUpdated={setCurrentUserName} /></AppLayout></ProtectedRoute>} />

        <Route path="*" element={<NotFoundPage />} />

      </Routes>

    </BrowserRouter>

  );

}



function ProtectedRoute({ isAuthenticated, children }: { isAuthenticated: boolean; children: ReactNode }) {

  if (!isAuthenticated) {

    return <Navigate to="/welcome" replace />;

  }

  return <>{children}</>;

}



function AppLayout({ children, currentUserName, onLogout }: { children: ReactNode; currentUserName: string; onLogout: () => void }) {

  const navigate = useNavigate();

  const location = useLocation();

  const [showNotifications, setShowNotifications] = useState(false);

  const navItems: { label: NavItem; to: string; icon: string }[] = [

    { label: 'Dashboard', to: '/dashboard', icon: '⌂' },

    { label: 'Job Search', to: '/jobs', icon: '🔎' },

    { label: 'My Applications', to: '/applications', icon: '✓' },

    { label: 'Resume Analyzer', to: '/resume-analyzer', icon: '📄' },

    { label: 'Saved Jobs', to: '/saved-jobs', icon: '★' },

    { label: 'Alerts & Automation', to: '/alerts', icon: '⚡' },

    { label: 'Settings', to: '/settings', icon: '⚙' },

  ];



  const activeLabel = navItems.find((item) => item.to === location.pathname)?.label ?? 'Dashboard';



  return (

    <div className="app-shell min-h-screen">

      <aside className="sidebar">

        <div className="brand-row">

          <div className="brand-mark">◆</div>

          <div>

            <strong>JobHunt AI</strong>

            <small>AI-Powered Job Discovery</small>

          </div>

        </div>



        <nav className="nav-list">

          {navItems.map((item) => (

            <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>

              <span>{item.icon}</span>

              {item.label}

            </NavLink>

          ))}

        </nav>



        <div className="sidebar-footer">

          <div className="pro-card">

            <div className="pro-title">Pro Advisor</div>

            <p>Get personalized job alerts, resume tips, and interview prep.</p>

            <button type="button" onClick={() => navigate('/alerts')}>Explore features →</button>

          </div>



          <div className="logged-user">

            <div className="avatar">{currentUserName.charAt(0).toUpperCase()}</div>

            <div className="user-copy">

              <strong>{currentUserName}</strong>

              <small>AI Developer</small>

            </div>

            <button type="button" className="logout-button" onClick={() => { onLogout(); navigate('/welcome'); }}>

              Log out

            </button>

          </div>

        </div>

      </aside>



      <main className="main-panel">

        <header className="topbar">

          <div>

            <p className="eyebrow">YOUR CAREER WORKSPACE</p>

            <h1>

              {activeLabel === 'Dashboard' ? 'Good Morning, ' : ''}

              <span>{currentUserName.split(' ')[0]}</span>

              {activeLabel === 'Dashboard' ? ' ☀️' : ''}

            </h1>

            <p>{activeLabel === 'Dashboard' ? 'Your AI job hunt agent is ready to help.' : `Managing ${activeLabel.toLowerCase()} for your next move.`}</p>

          </div>



          <div className="header-actions">

            <div style={{ position: 'relative' }}>
              <button
                type="button"
                className="notification-btn"
                aria-label="Notifications"
                aria-expanded={showNotifications}
                onClick={() => setShowNotifications((open) => !open)}
              >
                🔔 <i />
              </button>

              {showNotifications && (
                <div
                  role="dialog"
                  aria-label="Notifications"
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 12px)',
                    right: 0,
                    width: 300,
                    zIndex: 1000,
                    padding: 16,
                    borderRadius: 12,
                    background: 'var(--panel, #1c1c2b)',
                    border: '1px solid var(--border, #343448)',
                    boxShadow: '0 12px 30px rgba(0,0,0,.25)',
                    color: 'var(--text, #fff)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <strong>Notifications</strong>
                    <button type="button" onClick={() => setShowNotifications(false)} aria-label="Close notifications">✕</button>
                  </div>
                  <p style={{ margin: '8px 0', fontSize: 14 }}>🔎 Your job search is ready. Search for new opportunities from the dashboard.</p>
                  <p style={{ margin: '8px 0', fontSize: 14 }}>📄 Upload your latest resume to improve job matching.</p>
                  <button
                    type="button"
                    className="secondary-button"
                    style={{ marginTop: 8, width: '100%' }}
                    onClick={() => { setShowNotifications(false); navigate('/alerts'); }}
                  >
                    View Alerts & Automation
                  </button>
                </div>
              )}
            </div>

            <button
              type="button"
              className="user-widget"
              onClick={() => navigate('/settings')}
              aria-label="Open profile settings"
              style={{ border: 0, background: 'transparent', color: 'inherit', cursor: 'pointer', textAlign: 'left' }}
            >
              <div className="avatar">{currentUserName.charAt(0).toUpperCase()}</div>
              <div className="user-copy">
                <strong>{currentUserName}</strong>
                <small>AI Developer</small>
              </div>
            </button>

          </div>

        </header>



        {children}

      </main>

    </div>

  );

}



function CareerIllustration() {
  return (
    <div className="career-visual" aria-label="AI-powered career matching illustration">
      <div className="visual-orbit visual-orbit-one" />
      <div className="visual-orbit visual-orbit-two" />
      <svg className="career-network" viewBox="0 0 620 460" fill="none" aria-hidden="true">
        <path d="M75 132 190 190 267 92 384 147 526 76M110 350l105-94 95 94 106-110 104 83M190 190l25 66 169-109 26 93M267 92l43 258M384 147l32 83M215 256l201-26" stroke="url(#network-line)" strokeWidth="1.5" />
        <circle cx="75" cy="132" r="5" fill="#9E8BFF" />
        <circle cx="190" cy="190" r="7" fill="#7BE7FF" />
        <circle cx="267" cy="92" r="5" fill="#C5A3FF" />
        <circle cx="384" cy="147" r="8" fill="#A78BFA" />
        <circle cx="526" cy="76" r="5" fill="#7BE7FF" />
        <circle cx="110" cy="350" r="5" fill="#7BE7FF" />
        <circle cx="215" cy="256" r="6" fill="#C5A3FF" />
        <circle cx="310" cy="350" r="5" fill="#A78BFA" />
        <circle cx="416" cy="230" r="6" fill="#7BE7FF" />
        <circle cx="520" cy="313" r="5" fill="#C5A3FF" />
        <defs>
          <linearGradient id="network-line" x1="75" y1="76" x2="526" y2="350" gradientUnits="userSpaceOnUse">
            <stop stopColor="#747BFF" stopOpacity=".16" />
            <stop offset=".52" stopColor="#8DEAFF" stopOpacity=".68" />
            <stop offset="1" stopColor="#B17AFF" stopOpacity=".18" />
          </linearGradient>
        </defs>
      </svg>
      <div className="visual-core">
        <span className="visual-core-mark">✦</span>
        <span className="visual-core-kicker">YOUR AI CAREER COPILOT</span>
        <strong>Opportunity,<br />in focus.</strong>
        <span className="visual-core-caption">A smarter next step starts here</span>
      </div>
      <div className="visual-match-card">
        <div className="visual-card-top"><span><i /> LIVE MATCH</span><span>✦</span></div>
        <strong>94<span>%</span></strong>
        <p>Resume-to-role fit</p>
        <div className="visual-meter"><i /></div>
        <div className="visual-card-foot"><span>Skills aligned</span><b>Excellent</b></div>
      </div>
      <div className="visual-role-card">
        <span className="visual-company-mark">N</span>
        <span className="visual-role-copy"><strong>Product Designer</strong><small>Northstar · Recommended</small></span>
        <b>92%</b>
      </div>
    </div>
  );
}

function WelcomePage() {

  const navigate = useNavigate();



  return (

    <main className="auth-shell auth-shell--welcome">
      <div className="auth-grid">
        <section className="auth-copy">
          <div className="brand-row compact">
            <div className="brand-mark">✦</div>
            <div>
              <strong>JobHunt AI</strong>
              <small>AI-POWERED CAREER PLATFORM</small>
            </div>
          </div>
          <div className="eyebrow auth-eyebrow">YOUR NEXT OPPORTUNITY STARTS HERE</div>
          <h1>
            Find your dream job with <span>AI by your side.</span>
          </h1>
          <p>Turn your experience into momentum. Discover roles that fit, understand your strengths, and move forward with a smarter career search.</p>
          <div className="tag-row">
            <span><i>✦</i> Resume Matching</span>
            <span><i>⌕</i> Smart Job Search</span>
            <span><i>✓</i> ATS Scoring</span>
          </div>
          <div className="welcome-actions">
            <button type="button" className="primary-button" onClick={() => navigate('/register')}>
              Get Started <span aria-hidden="true">→</span>
            </button>
            <span className="welcome-note">Free to get started <i>·</i> Your next move, made clearer</span>
          </div>
        </section>

        <section className="welcome-side" aria-label="Career matching preview">
          <CareerIllustration />
          <div className="auth-panel welcome-panel">
            <div className="welcome-panel-copy">
              <span className="auth-card-kicker">A BETTER WAY FORWARD</span>
              <h2>Make your next move count.</h2>
              <p>Bring your career search into focus with one intelligent workspace.</p>
            </div>
            <div className="auth-stack">
              <button type="button" className="primary-button" onClick={() => navigate('/register')}>Create Account <span aria-hidden="true">→</span></button>
              <button type="button" className="secondary-button" onClick={() => navigate('/signin')}>I already have an account</button>
            </div>
          </div>
        </section>
      </div>

    </main>

  );

}



function AuthPage({ mode, onSuccess }: { mode: 'signin' | 'register'; onSuccess: (name: string) => void }) {

  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');

  const [email, setEmail] = useState('');

  const [password, setPassword] = useState('');

  const [error, setError] = useState('');

  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);



  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {

    event.preventDefault();

    setError('');



    if (!email.trim()) {

      setError('Please enter your email address.');

      return;

    }



    if (mode === 'register' && !fullName.trim()) {

      setError('Please enter your full name.');

      return;

    }



    if (!password) {

      setError('Please enter your password.');

      return;

    }



    if (password.length < 8) {

      setError('Password must be at least 8 characters long.');

      return;

    }



    setLoading(true);



    try {

      const endpoint = mode === 'register' ? '/api/auth/register' : '/api/auth/login';

      const payload = mode === 'register' ? { full_name: fullName.trim(), email: email.trim(), password } : { email: email.trim(), password };

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify(payload),

      });



      const data = await response.json();

      if (!response.ok) {

        const detail = typeof data.detail === 'string' ? data.detail : 'Authentication failed.';

        throw new Error(detail);

      }



      const nextName = data.user?.full_name || fullName.trim() || 'User';

      sessionStorage.setItem('jobhunt_access_token', data.access_token);

      sessionStorage.setItem('jobhunt_authenticated', 'true');

      sessionStorage.setItem('jobhunt_user_email', data.user.email);

      sessionStorage.setItem('jobhunt_user_name', nextName);

      onSuccess(nextName);

      navigate('/dashboard');

    } catch (caught) {

      setError(caught instanceof Error ? caught.message : 'Unable to connect to the backend.');

    } finally {

      setLoading(false);

    }

  };



  return (

    <main className={`auth-shell auth-shell--${mode}`}>
      <div className="auth-grid">
        <section className="auth-copy auth-story">
          <div className="brand-row compact">
            <div className="brand-mark">✦</div>
            <div>
              <strong>JobHunt AI</strong>
              <small>AI-POWERED CAREER PLATFORM</small>
            </div>
          </div>
          <div className="eyebrow auth-eyebrow">{mode === 'register' ? 'START YOUR NEXT CHAPTER' : 'YOUR CAREER, IN FOCUS'}</div>
          <h1>{mode === 'register' ? <>Build a career that <span>moves you forward.</span></> : <>Welcome back to your <span>next opportunity.</span></>}</h1>
          <p>{mode === 'register' ? 'Create your account and bring job discovery, resume matching, and career momentum together.' : 'Your search is ready when you are. Pick up where your next career move begins.'}</p>
          <div className="story-proof">
            <span className="proof-icon">✦</span>
            <span><strong>Less searching. More direction.</strong><small>Personalized matches shaped around your experience.</small></span>
          </div>
          <CareerIllustration />
        </section>

        <section className="auth-panel form-panel">
          <div className="auth-card-heading">
            <span className="auth-card-kicker">{mode === 'register' ? 'CREATE YOUR ACCOUNT' : 'WELCOME BACK'}</span>
            <h2>{mode === 'register' ? 'Your next chapter starts here.' : 'Sign in to JobHunt AI'}</h2>
            <p>{mode === 'register' ? 'Set up your profile to find the right opportunities.' : 'Enter your details to continue your career journey.'}</p>
          </div>
          <div className="tab-row">
            <button type="button" className={`tab ${mode === 'signin' ? 'active' : ''}`} onClick={() => navigate('/signin')}>Sign In</button>
            <button type="button" className={`tab ${mode === 'register' ? 'active' : ''}`} onClick={() => navigate('/register')}>Create Account</button>
          </div>



          <form onSubmit={handleSubmit} className="auth-form">

            {mode === 'register' && (
              <label>
                <span>Full name</span>
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Enter your full name" autoComplete="name" />
              </label>
            )}

            <label>
              <span>Email address</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" />
            </label>

            <label>
              <span>Password</span>
              <div className="password-wrap">
                <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
                <button type="button" className="inline-toggle" onClick={() => setShowPassword((value) => !value)}>{showPassword ? 'Hide' : 'Show'}</button>

              </div>

            </label>



            {error && <p className="auth-error">{error}</p>}



            <button type="submit" className="primary-button" disabled={loading}>

              {loading ? 'Please wait...' : mode === 'register' ? 'Create Account' : 'Sign In'} →

            </button>

          </form>

          <div className="auth-card-footer">
            <span>Protected, private, and built around your next step.</span>
            <button type="button" className="secondary-button ghost" onClick={() => navigate('/welcome')}>← Back to welcome</button>
          </div>
        </section>

      </div>

    </main>

  );

}



function DashboardPage({ latestJobs, topMatch, resumeName, resumeSkills, resumeMatchScore, input, setInput, onSearch, isLoading, onUpload, isUploading }: {
  
  latestJobs: Job[];
  topMatch: number;
  resumeName: string | null;
  resumeSkills: string[];
  resumeMatchScore: number | null;
  input: string;
  setInput: Dispatch<SetStateAction<string>>;
  onSearch: (query?: string) => void;
  isLoading: boolean;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
}) {
  const savedCount = readSavedJobs().length;
  const appCount = readApplications().length;

  return (
    <>
      <section className="hero-panel">
        <div className="hero-orb">
          <div className="robot-face">
            <span>◉ ◉</span>
            <b>◌</b>
          </div>
        </div>

        <div className="hero-copy">
          <div className="powered">✦ Powered by Gemini &amp; MCP</div>
          <h2>AI Job Hunt Agent</h2>
          <p>Discover, match, apply and track — all in one place.</p>

          <div className="hero-pills">
            <span>— Find Jobs</span>
            <span>✓ Match With Resume</span>
            <span>✦ Analyze Resume</span>
            <span>ÏŸ Automate Search</span>
          </div>

          <form className="search-box" onSubmit={(event) => { event.preventDefault(); onSearch(); }}>
            <span>◆</span>
            <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="e.g. Find Python developer jobs in Bangalore" />
            <button type="submit" disabled={isLoading || !input.trim()}>→</button>
          </form>
        </div>
      </section>

      <section className="metrics">
        <div className="metric green">
          <div className="metric-icon">◌</div>
          <div>
            <strong>{latestJobs.length}</strong>
            <span>Matched Jobs</span>
          </div>
          <em> —</em>
        </div>

        <div className="metric purple">
          <div className="metric-icon">✓</div>
          <div>
            <strong>{Math.round(topMatch)}%</strong>
            <span>Top Match Score</span>
          </div>
          <em>◆</em>
        </div>

        <div className="metric blue">
          <div className="metric-icon">—</div>
          <div>
            <strong>{appCount}</strong>
            <span>Applications</span>
          </div>
          <em> —</em>
        </div>

        <div className="metric amber">
          <div className="metric-icon">◉</div>
          <div>
            <strong>{savedCount}</strong>
            <span>Saved Jobs</span>
          </div>
          <em>◆</em>
        </div>
      </section>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Resume Snapshot</h3>
              <p>{resumeName ? `Uploaded: ${resumeName}` : 'No resume uploaded yet'}</p>
            </div>
            <label className="upload-button">
              <input type="file" accept="application/pdf" onChange={onUpload} />
              {isUploading ? 'Uploading◆' : resumeName ? 'Replace Resume' : 'Upload Resume'}
            </label>
          </div>

          {resumeSkills.length ? (
            <div className="skill-list">
              {resumeSkills.map((skill) => (
                <span key={skill} className="skill-pill">{skill}</span>
              ))}
            </div>
          ) : (
            <div className="empty-inline">Upload a PDF to let the agent match jobs to your profile.</div>
          )}
        </section>

        <section className="panel match-performance-panel">
          <div className="panel-header">
            <div>
              <h3>Resume Match Performance</h3>
              <p>Your job relevance score</p>
            </div>
          </div>

          <div className="match-performance">
            <div className="match-performance-value">
              <span className="match-score">
                    {resumeMatchScore !== null ? `${resumeMatchScore}%` : "-"}
                  </span>
              <span className="match-label">
                  {resumeMatchScore !== null ? "Latest Resume Match Score" : "Analyze a resume"}
              </span>
            </div>

            <div className="match-performance-chart">
              <div className="chart-bars">
                {resumeMatchScore !== null && (
                  <span
                    className="chart-bar"
                    style={{ height: `${Math.max(3, resumeMatchScore)}%` }}
                    title={`${resumeMatchScore}%`}
                  />
                )}
              </div>
            </div>
          </div>
        </section>
      </div>

      <section className="panel panel-spacer">
        <div className="panel-header">
          <div>
            <h3>Recommended Jobs</h3>
            <p>Opportunities ranked by your resume fit.</p>
          </div>
        </div>

        {latestJobs.length ? (
          <div className="job-grid compact-grid">
            {latestJobs.slice(0, 4).map((job) => (
              <JobMiniCard key={`${job.company}-${job.title}-${job.url}`} job={job} />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">◆</div>
            <h3>Search to populate your dashboard</h3>
            <p>Once you search, recommended roles and match scores appear here.</p>
          </div>
        )}
      </section>
    </>
  );
}

function JobSearchPage({ jobs, filteredJobs, allSources, input, setInput, onSearch, isLoading, searchError, atsThreshold, setAtsThreshold, semanticThreshold, setSemanticThreshold, sortKey, setSortKey, selectedTab, setSelectedTab, activeSource, setActiveSource, remoteOnly, setRemoteOnly, includeInternships, setIncludeInternships, fresherFriendly, setFresherFriendly, mySkillsMatch, setMySkillsMatch }: {
  jobs: Job[];

  filteredJobs: Job[];

  allSources: [string, number][];

  input: string;

  setInput: Dispatch<SetStateAction<string>>;

  onSearch: (query?: string) => void;

  isLoading: boolean;

  searchError: string;

  atsThreshold: number;

  setAtsThreshold: (value: number) => void;

  semanticThreshold: number;

  setSemanticThreshold: (value: number) => void;

  sortKey: SortKey;

  setSortKey: (value: SortKey) => void;

  selectedTab: 'All Jobs' | 'High Match' | 'Internship' | 'Fresher';

  setSelectedTab: (value: 'All Jobs' | 'High Match' | 'Internship' | 'Fresher') => void;

  activeSource: string | null;

  setActiveSource: (value: string | null) => void;
  remoteOnly: boolean;
  setRemoteOnly: (value: boolean) => void;
  includeInternships: boolean;
  setIncludeInternships: (value: boolean) => void;
  fresherFriendly: boolean;
  setFresherFriendly: (value: boolean) => void;
  mySkillsMatch: boolean;
  setMySkillsMatch: (value: boolean) => void;

}) {

  const tabs = ['All Jobs', 'High Match', 'Internship', 'Fresher'] as const;



  return (

    <>

      <section className="panel dedicated-search">

        <div className="panel-header">

          <div>

            <h3>Job Search</h3>

            <p>Find the best opportunities with AI-powered matching.</p>

          </div>

        </div>



        <form className="search-box dedicated" onSubmit={(event) => { event.preventDefault(); onSearch(); }}>

          <span>—</span>

          <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Search by role, skill, company" />

          <select defaultValue="" onChange={(event) => event.target.value && setInput((current) => `${current} in ${event.target.value}`)}>

            <option value="">Location</option>

            <option value="Bengaluru">Bengaluru</option>

            <option value="Hyderabad">Hyderabad</option>

            <option value="Remote">Remote</option>

            <option value="Chennai">Chennai</option>

          </select>

          <select defaultValue="" onChange={(event) => event.target.value && setInput((current) => `${current} ${event.target.value}`)}>

            <option value="">Type</option>

            <option value="Internship">Internship</option>

            <option value="Full-time">Full-time</option>

            <option value="Remote">Remote</option>

          </select>

          <button type="submit" disabled={isLoading || !input.trim()}>Search</button>

        </form>



        <div className="tab-row results-tabs">

          {tabs.map((tab) => (

            <button key={tab} type="button" className={`tab ${selectedTab === tab ? 'active' : ''}`} onClick={() => setSelectedTab(tab)}>{tab}</button>

          ))}

        </div>

      </section>



      <div className="content-grid">

        <section className="primary-section">

          <section className="panel">

            <div className="panel-header">

              <div>

                <h3>Results</h3>

                <p>{filteredJobs.length} jobs shown · {jobs.length} jobs discovered</p>

              </div>

              <select value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>

                <option value="combined_score">Match Score</option>

                <option value="ats_score">ATS Score</option>

                <option value="semantic_score">Semantic Score</option>

              </select>

            </div>



            {searchError && <div className="error-banner">{searchError}</div>}



            {jobs.length > 0 && (

              <div className="filter-tabs">

                <button type="button" className={!activeSource ? 'selected' : ''} onClick={() => setActiveSource(null)}>All ({jobs.length})</button>

                {allSources.map(([source, count]) => (

                  <button key={source} type="button" className={activeSource === source ? 'selected' : ''} onClick={() => setActiveSource(activeSource === source ? null : source)}>

                    {source} ({count})

                  </button>

                ))}

              </div>

            )}



            {isLoading ? (

              <div className="loading-state">Searching and scoring job listings◆</div>

            ) : filteredJobs.length ? (

              <div className="job-grid">

                {filteredJobs.map((job, index) => (

                  <JobCard key={`${job.url || job.title}-${index}`} job={job} rank={index + 1} />

                ))}

              </div>

            ) : (

              <div className="empty-state">

                <div className="empty-icon">◆</div>

                <h3>No jobs match your current filters</h3>

                <p>Try lowering the score thresholds or broadening your search phrase.</p>

              </div>

            )}

          </section>

        </section>



        <aside className="side-section">

          <section className="panel">

            <div className="panel-header">

              <div>

                <h3>Search Insights</h3>

                <p>Live discovery overview</p>

              </div>

            </div>

            <div className="insight-list">

              <div><strong>{jobs.length}</strong><span>Total jobs</span></div>

              <div><strong>{jobs.filter((job) => Number(job.combined_score ?? 0) >= 70).length}</strong><span>High-match jobs</span></div>

              <div><strong>{jobs.filter((job) => /intern(ship)?/i.test(job.title || '')).length}</strong><span>Internships</span></div>

            </div>

          </section>



          <section className="panel">

            <div className="panel-header">

              <div>

                <h3>Refine Your Search</h3>

                <p>Advanced filters</p>

              </div>

            </div>

            <div className="toggle-list">

              <label><input type="checkbox" checked={remoteOnly} onChange={(event) => setRemoteOnly(event.target.checked)} /> Remote jobs only</label>

              <label><input type="checkbox" checked={includeInternships} onChange={(event) => setIncludeInternships(event.target.checked)} /> Include internships</label>

              <label><input type="checkbox" checked={fresherFriendly} onChange={(event) => setFresherFriendly(event.target.checked)} /> Fresher friendly</label>

              <label><input type="checkbox" checked={mySkillsMatch} onChange={(event) => setMySkillsMatch(event.target.checked)} /> My skills match</label>

            </div>

            <div className="slider-stack">

              <label>

                ATS threshold

                <input type="range" min={0} max={100} step={5} value={atsThreshold} onChange={(event) => setAtsThreshold(Number(event.target.value))} />

                <span>{atsThreshold}%</span>

              </label>

              <label>

                Semantic threshold

                <input type="range" min={0} max={100} step={5} value={semanticThreshold} onChange={(event) => setSemanticThreshold(Number(event.target.value))} />

                <span>{semanticThreshold}%</span>

              </label>

            </div>

          </section>

        </aside>

      </div>

    </>

  );

}



function ApplicationsPage() {

  const [records, setRecords] = useState<ApplicationRecord[]>(() => readApplications());

  const [query, setQuery] = useState('');

  const [statusFilter, setStatusFilter] = useState('All');

  const [form, setForm] = useState({ company: '', role: '', status: 'Applied' as ApplicationStatus, nextAction: '', interviewDate: '', notes: '' });

  const [editingId, setEditingId] = useState<number | null>(null);



  useEffect(() => {

    localStorage.setItem('jobhunt_applications', JSON.stringify(records));

  }, [records]);



  const filtered = records.filter((record) => {

    const text = `${record.company} ${record.role}`.toLowerCase();

    const matchesQuery = !query || text.includes(query.toLowerCase());

    const matchesStatus = statusFilter === 'All' || record.status === statusFilter;

    return matchesQuery && matchesStatus;

  });



  const save = () => {

    if (!form.company.trim() || !form.role.trim()) return;



    const payload: ApplicationRecord = {

      id: editingId ?? Date.now(),

      company: form.company.trim(),

      role: form.role.trim(),

      appliedDate: new Date().toISOString(),

      status: form.status,

      nextAction: form.nextAction,

      interviewDate: form.interviewDate,

      notes: form.notes,

    };



    if (editingId === null) {

      setRecords((prev) => [payload, ...prev]);

    } else {

      setRecords((prev) => prev.map((item) => (item.id === editingId ? payload : item)));

    }



    setForm({ company: '', role: '', status: 'Applied', nextAction: '', interviewDate: '', notes: '' });

    setEditingId(null);

  };



  const totals = {

    Total: records.length,

    Applied: records.filter((item) => item.status === 'Applied').length,

    Interview: records.filter((item) => item.status === 'Interview').length,

    Shortlisted: records.filter((item) => item.status === 'Shortlisted').length,

    Offer: records.filter((item) => item.status === 'Offer').length,

    Rejected: records.filter((item) => item.status === 'Rejected').length,

  };



  return (

    <>

      <section className="panel">

        <div className="panel-header">

          <div>

            <h3>Application Tracking</h3>

            <p>Manage outreach, interviews, and follow-ups.</p>

          </div>

        </div>



        <div className="summary-grid">

          {Object.entries(totals).map(([label, value]) => (

            <div key={label} className="summary-card">

              <strong>{value}</strong>

              <span>{label}</span>

            </div>

          ))}

        </div>

      </section>



      <section className="panel panel-spacer">

        <div className="panel-header">

          <div>

            <h3>{editingId !== null ? 'Edit Application' : 'Add Application'}</h3>

            <p>Track your next steps and interviews.</p>

          </div>

        </div>



        <div className="application-form">

          <input value={form.company} onChange={(event) => setForm((prev) => ({ ...prev, company: event.target.value }))} placeholder="Company" />

          <input value={form.role} onChange={(event) => setForm((prev) => ({ ...prev, role: event.target.value }))} placeholder="Role" />

          <select value={form.status} onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value as ApplicationStatus }))}>

            {(['Applied', 'Interview', 'Shortlisted', 'Offer', 'Rejected'] as ApplicationStatus[]).map((status) => (

              <option key={status} value={status}>{status}</option>

            ))}

          </select>

          <input value={form.nextAction} onChange={(event) => setForm((prev) => ({ ...prev, nextAction: event.target.value }))} placeholder="Next action" />

          <input type="date" value={form.interviewDate} onChange={(event) => setForm((prev) => ({ ...prev, interviewDate: event.target.value }))} />

          <textarea value={form.notes} onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))} placeholder="Notes" />

          <button type="button" className="primary-button" onClick={save}>{editingId !== null ? 'Update' : 'Add Application'}</button>

        </div>

      </section>



      <section className="panel panel-spacer">

        <div className="panel-header">

          <div>

            <h3>Applications</h3>

            <p>Search and filter your pipeline.</p>

          </div>

          <div className="table-controls">

            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company or role" />

            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>

              <option value="All">All</option>

              {(['Applied', 'Interview', 'Shortlisted', 'Offer', 'Rejected'] as ApplicationStatus[]).map((status) => (

                <option key={status} value={status}>{status}</option>

              ))}

            </select>

          </div>

        </div>



        {filtered.length === 0 ? (

          <div className="empty-state">

            <div className="empty-icon">◆</div>

            <h3>No applications yet</h3>

            <p>Track roles as soon as you apply.</p>

          </div>

        ) : (

          <div className="table-wrap">

            <table className="records-table">

              <thead>

                <tr>

                  <th>Company</th>

                  <th>Role</th>

                  <th>Applied</th>

                  <th>Status</th>

                  <th>Next Action</th>

                  <th>Interview Date</th>

                  <th>Notes</th>

                  <th>Actions</th>

                </tr>

              </thead>

              <tbody>

                {filtered.map((record) => (

                  <tr key={record.id}>

                    <td>{record.company}</td>

                    <td>{record.role}</td>

                    <td>{new Date(record.appliedDate).toLocaleDateString()}</td>

                    <td><span className="status-pill">{record.status}</span></td>

                    <td>{record.nextAction || '—'}</td>

                    <td>{record.interviewDate ? new Date(record.interviewDate).toLocaleDateString() : '—'}</td>

                    <td>{record.notes || '—'}</td>

                    <td>

                      <div className="mini-actions">

                        <button type="button" onClick={() => {

                          setForm({ company: record.company, role: record.role, status: record.status, nextAction: record.nextAction, interviewDate: record.interviewDate, notes: record.notes });

                          setEditingId(record.id);

                        }}>Edit</button>

                        <button type="button" className="danger" onClick={() => setRecords((prev) => prev.filter((item) => item.id !== record.id))}>Delete</button>

                      </div>

                    </td>

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        )}

      </section>

    </>

  );

}




type ResumeMatchResult = {
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  resume_skills: string[];
  job_skills: string[];
  message: string;
  improvement_suggestions: string[];
};

function ResumeAnalyzerPage({
  resumeName,
  resumeSkills,
  onUpload,
  isUploading,
  setResumeMatchScore,
}: {
  resumeName: string | null;
  resumeSkills: string[];
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
  setResumeMatchScore: (score: number | null) => void;
}) {
  const [jobDescription, setJobDescription] = useState('');
  const [matchResult, setMatchResult] =
    useState<ResumeMatchResult | null>(null);
  const [isMatching, setIsMatching] = useState(false);
  const [matchError, setMatchError] = useState('');

  const handleMatchResume = async () => {
    if (!resumeName) {
      setMatchError('Please upload your resume first.');
      return;
    }

    if (!jobDescription.trim()) {
      setMatchError('Please paste the job description.');
      return;
    }

    setIsMatching(true);
    setMatchError('');
    setMatchResult(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/resume/match`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': getSessionId(),
          },
          body: JSON.stringify({
            job_description: jobDescription,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || 'Resume matching failed.'
        );
      }

      setMatchResult(data as ResumeMatchResult);
      setResumeMatchScore(data.match_score);
    } catch (error) {
      setMatchError(
        error instanceof Error
          ? error.message
          : 'Resume matching failed.'
      );
    } finally {
      setIsMatching(false);
    }
  };

  return (
    <>
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Resume Analyzer</h3>
            <p>
              Analyze your resume and match it against a job
              description.
            </p>
          </div>

          <label className="upload-button">
            <input
              type="file"
              accept="application/pdf"
              onChange={onUpload}
              disabled={isUploading}
            />
            {isUploading
              ? 'Uploading...'
              : resumeName
                ? 'Replace Resume'
                : 'Upload Resume'}
          </label>
        </div>

        <div className="resume-box">
          <div className="score-ring">
            <div className="score-circle">
              <strong>
                {resumeSkills.length ? resumeSkills.length : 0}
              </strong>
              <span>Skills Found</span>
            </div>
          </div>

          <div className="resume-meta">
            <h4>{resumeName || 'No resume uploaded yet'}</h4>

            <p>
              {resumeSkills.length
                ? `${resumeSkills.length} skills extracted from your resume.`
                : 'Upload a text-based PDF to begin analysis.'}
            </p>

            <div className="skill-list">
              {resumeSkills.length ? (
                resumeSkills.map((skill) => (
                  <span key={skill} className="skill-pill">
                    {skill}
                  </span>
                ))
              ) : (
                <span className="empty-inline">
                  Waiting for resume
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="panel panel-spacer">
            <div className="panel-header">
              <div>
                <h3>Resume Improvement Suggestions</h3>
                <p>
                  General suggestions to improve your resume.
                </p>
              </div>
            </div>

            <ul className="suggestions">
              <li>
                Add measurable outcomes to your experience and
                project descriptions.
              </li>
              <li>
                Highlight skills relevant to the target job.
              </li>
              <li>
                Keep formatting clean and ATS-readable.
              </li>
              <li>
                Include clear sections for education, skills,
                projects, and experience.
              </li>
            </ul>
        </section>
        <textarea
          className="job-description-input"
          value={jobDescription}
          onChange={(event) =>
            setJobDescription(event.target.value)
          }
          placeholder="Paste the complete job description here..."
          rows={8}
        />

        <button
          type="button"
          className="primary-button"
          onClick={handleMatchResume}
          disabled={isMatching || isUploading}
        >
          {isMatching
            ? 'Analyzing...'
            : 'Analyze Job Match'}
        </button>

        {matchError && (
          <p className="error-message">{matchError}</p>
        )}

        
        {matchResult && (
          <div className="match-results">
            {/* Match Score */}
            <div className="match-score-card">
              <div className="match-score-header">
                <div>
                  <span className="match-eyebrow">RESUME ANALYSIS</span>
                  <h3>Job Match Overview</h3>
                  <p>{matchResult.message}</p>
                </div>

                <div className="match-score-circle">
                  <strong>{matchResult.match_score}%</strong>
                  <span>Match Score</span>
                </div>
              </div>

              <div className="match-progress-track">
                <div
                  className="match-progress-fill"
                  style={{
                    width: `${Math.max(
                      0,
                      Math.min(100, matchResult.match_score)
                    )}%`,
                  }}
                />
              </div>

              <div className="match-stats">
                <div className="match-stat">
                  <span>Matched Skills</span>
                  <strong>{matchResult.matched_skills.length}</strong>
                </div>

                <div className="match-stat">
                  <span>Missing Skills</span>
                  <strong>{matchResult.missing_skills.length}</strong>
                </div>

                <div className="match-stat">
                  <span>Total Job Skills</span>
                  <strong>{matchResult.job_skills.length}</strong>
                </div>
              </div>
            </div>

            {/* Matched Skills */}
            <div className="match-section matched-section">
              <div className="match-section-header">
                <div>
                  <h4>Matched Skills</h4>
                  <p>Skills found in both your resume and the job description.</p>
                </div>

                <span className="match-count matched-count">
                  {matchResult.matched_skills.length}
                </span>
              </div>

              <div className="skill-list">
                {matchResult.matched_skills.length ? (
                  matchResult.matched_skills.map((skill) => (
                    <span key={skill} className="skill-pill matched-skill">
                      ✓ {skill}
                    </span>
                  ))
                ) : (
                  <p className="match-empty">
                    No matching skills found yet.
                  </p>
                )}
              </div>
            </div>

            {/* Missing Skills */}
            <div className="match-section missing-section">
              <div className="match-section-header">
                <div>
                  <h4>Skills to Improve</h4>
                  <p>Recognized job skills not detected in your resume.</p>
                </div>

                <span className="match-count missing-count">
                  {matchResult.missing_skills.length}
                </span>
              </div>

              <div className="skill-list">
                {matchResult.missing_skills.length ? (
                  matchResult.missing_skills.map((skill) => (
                    <span key={skill} className="skill-pill missing-skill">
                      + {skill}
                    </span>
                  ))
                ) : (
                  <p className="match-empty">
                    No missing recognized skills.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

    </>
  );
}


function SavedJobsPage() {

  const [jobs, setJobs] = useState<Job[]>(() => readSavedJobs());

  const [query, setQuery] = useState('');



  const filtered = jobs.filter((job) => `${job.title} ${job.company} ${job.location}`.toLowerCase().includes(query.toLowerCase()));



  return (

    <section className="panel">

      <div className="panel-header">

        <div>

          <h3>Saved Jobs</h3>

          <p>Keep track of promising opportunities.</p>

        </div>

        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search saved jobs" />

      </div>



      {filtered.length ? (

        <div className="job-grid compact-grid">

          {filtered.map((job) => (

            <div key={`${job.company}-${job.title}-${job.url}`} className="saved-card">

              <div className="saved-card-header">

                <span>{job.company}</span>

                <button type="button" className="ghost-link" onClick={() => setJobs((prev) => prev.filter((item) => `${item.company}-${item.title}-${item.url}` !== `${job.company}-${job.title}-${job.url}`))}>Remove</button>

              </div>

              <h4>{job.title}</h4>

              <p>{job.location}</p>

              <div className="saved-meta">

                <strong>{job.combined_score ? `${Math.round(Number(job.combined_score))}%` : 'N/A'}</strong>

                <span>{job.source}</span>

              </div>

              <a href={job.url} target="_blank" rel="noreferrer">View details</a>

            </div>

          ))}

        </div>

      ) : (

        <div className="empty-state">

          <div className="empty-icon">★</div>

          <h3>No saved jobs</h3>

          <p>Save opportunities from the search page to review later.</p>

        </div>

      )}

    </section>

  );

}



function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingAlertId, setEditingAlertId] = useState<number | null>(null);
  const [alertForm, setAlertForm] = useState<AlertForm>({
    name: '',
    description: '',
    status: 'Enabled',
    lastRun: '',
    nextRun: '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [alertToDelete, setAlertToDelete] = useState<AlertRecord | null>(null);
  const [pendingAlertId, setPendingAlertId] = useState<number | null>(null);
  const { toast, notify, dismiss } = useToast();

  useEffect(() => {
    let active = true;
    const loadAlerts = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/alerts`, {
          headers: getAuthorizationHeaders(),
        });
        if (!response.ok) {
          throw new Error(await getResponseError(response, 'Unable to load alerts.'));
        }
        const data = await response.json() as AlertApiRecord[];
        if (active) {
          setAlerts(data.map(toAlertRecord));
          setLoadError('');
        }
      } catch (error) {
        if (active) {
          const message = error instanceof Error ? error.message : 'Unable to load alerts.';
          setLoadError(message);
          notify(message, 'error');
        }
      } finally {
        if (active) setIsLoading(false);
      }
    };
    void loadAlerts();
    return () => { active = false; };
  }, [notify]);

  const startCreate = () => {
    setEditingAlertId(null);
    setAlertForm({
      name: '',
      description: '',
      status: 'Enabled',
      lastRun: '',
      nextRun: '',
    });
    setIsEditorOpen(true);
  };

  const startEdit = (alert: AlertRecord) => {
    setEditingAlertId(alert.id);
    setAlertForm({
      name: alert.name,
      description: alert.description,
      status: alert.status,
      lastRun: alert.lastRun,
      nextRun: alert.nextRun,
    });
    setIsEditorOpen(true);
  };

  const closeEditor = () => {
    if (isSaving) return;
    setIsEditorOpen(false);
    setEditingAlertId(null);
  };

  const saveAlert = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = alertForm.name.trim();
    if (name.length < 2) {
      notify('Alert title must contain at least 2 characters.', 'error');
      return;
    }

    setIsSaving(true);
    try {
      const isEditing = editingAlertId !== null;
      const response = await fetch(
        `${API_BASE_URL}/api/alerts${isEditing ? `/${editingAlertId}` : ''}`,
        {
          method: isEditing ? 'PUT' : 'POST',
          headers: {
            ...getAuthorizationHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(toAlertPayload({ ...alertForm, name })),
        },
      );
      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Unable to save alert.'));
      }
      const saved = toAlertRecord(await response.json() as AlertApiRecord);
      setAlerts((current) => isEditing
        ? current.map((alert) => alert.id === saved.id ? saved : alert)
        : [...current, saved]);
      setIsEditorOpen(false);
      setEditingAlertId(null);
      notify(isEditing ? 'Alert updated successfully.' : 'Alert created successfully.');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Unable to save alert.', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const toggleAlert = async (alert: AlertRecord) => {
    setPendingAlertId(alert.id);
    try {
      const response = await fetch(`${API_BASE_URL}/api/alerts/${alert.id}`, {
        method: 'PUT',
        headers: {
          ...getAuthorizationHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(toAlertPayload({
          ...alert,
          status: alert.status === 'Enabled' ? 'Paused' : 'Enabled',
        })),
      });
      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Unable to update alert status.'));
      }
      const updated = toAlertRecord(await response.json() as AlertApiRecord);
      setAlerts((current) => current.map((item) => item.id === updated.id ? updated : item));
      notify(updated.status === 'Enabled' ? 'Alert resumed.' : 'Alert paused.');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Unable to update alert status.', 'error');
    } finally {
      setPendingAlertId(null);
    }
  };

  const confirmDelete = async () => {
    if (!alertToDelete) return;
    setPendingAlertId(alertToDelete.id);
    try {
      const response = await fetch(`${API_BASE_URL}/api/alerts/${alertToDelete.id}`, {
        method: 'DELETE',
        headers: getAuthorizationHeaders(),
      });
      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Unable to delete alert.'));
      }
      setAlerts((current) => current.filter((item) => item.id !== alertToDelete.id));
      notify('Alert deleted successfully.');
      setAlertToDelete(null);
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Unable to delete alert.', 'error');
    } finally {
      setPendingAlertId(null);
    }
  };

  return (
    <>
      <section className="panel alerts-page-panel">
        <div className="alerts-page-heading">
          <div>
            <span className="settings-kicker">AUTOMATION CENTER</span>
            <h2>Alerts &amp; Automation</h2>
            <p>Manage your career reminders and scheduled activities.</p>
          </div>
          <button type="button" className="primary-button" onClick={startCreate}>＋ Create alert</button>
        </div>

        {loadError && (
          <div className="error-banner" role="alert">
            {loadError}
            <button type="button" onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}
        {isLoading ? (
          <div className="alerts-loading" aria-live="polite"><span /> Loading your alerts...</div>
        ) : alerts.length ? (
          <div className="automation-grid">
            {alerts.map((item) => (
              <section key={item.id} className="panel automation-card">
                <div className="panel-header compact">
                  <div>
                    <h3>{item.name}</h3>
                    <p>{item.description || 'No description provided.'}</p>
                  </div>
                  <span className={`status-pill ${item.status === 'Enabled' ? 'success' : ''}`}>{item.status}</span>
                </div>
                <div className="automation-meta">
                  <span><b>Last run</b>{item.lastRun || 'Not run yet'}</span>
                  <span><b>Next run</b>{item.nextRun || 'Not scheduled'}</span>
                </div>
                <div className="card-actions automation-actions">
                  <button type="button" className="secondary-button" onClick={() => startEdit(item)}>Edit</button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => void toggleAlert(item)}
                    disabled={pendingAlertId === item.id}
                  >
                    {pendingAlertId === item.id ? 'Updating...' : item.status === 'Enabled' ? 'Pause' : 'Resume'}
                  </button>
                  <button type="button" className="secondary-button danger" onClick={() => setAlertToDelete(item)}>Delete</button>
                </div>
              </section>
            ))}
          </div>
        ) : !loadError ? (
          <div className="empty-state alerts-empty-state">
            <div className="empty-icon">⚡</div>
            <h3>No alerts set up yet</h3>
            <p>Create an alert to organize your job-search reminders and schedules.</p>
            <button type="button" className="primary-button" onClick={startCreate}>Create your first alert</button>
          </div>
        ) : null}
      </section>

      {isEditorOpen && (
        <ModalDialog title={editingAlertId === null ? 'Create an alert' : 'Edit alert'} onClose={closeEditor} wide>
          <form className="app-modal-form" onSubmit={(event) => void saveAlert(event)}>
            <label>
              Alert title
              <input
                autoFocus
                required
                minLength={2}
                maxLength={120}
                value={alertForm.name}
                onChange={(event) => setAlertForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="e.g. Daily job search"
              />
            </label>
            <label>
              Description
              <textarea
                maxLength={1000}
                rows={3}
                value={alertForm.description}
                onChange={(event) => setAlertForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="What should this alert help you remember?"
              />
            </label>
            <div className="app-modal-fields">
              <label>
                Status
                <select
                  value={alertForm.status}
                  onChange={(event) => setAlertForm((current) => ({ ...current, status: event.target.value as AlertStatus }))}
                >
                  <option value="Enabled">Enabled</option>
                  <option value="Paused">Paused</option>
                </select>
              </label>
              <label>
                Last run
                <input
                  maxLength={120}
                  value={alertForm.lastRun}
                  onChange={(event) => setAlertForm((current) => ({ ...current, lastRun: event.target.value }))}
                  placeholder="Not run yet"
                />
              </label>
              <label className="app-modal-fields-wide">
                Schedule / next run
                <input
                  maxLength={120}
                  value={alertForm.nextRun}
                  onChange={(event) => setAlertForm((current) => ({ ...current, nextRun: event.target.value }))}
                  placeholder="e.g. Weekdays at 9:00 AM"
                />
              </label>
            </div>
            <div className="app-modal-actions">
              <button type="button" className="secondary-button" onClick={closeEditor} disabled={isSaving}>Cancel</button>
              <button type="submit" className="primary-button" disabled={isSaving}>
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </ModalDialog>
      )}

      {alertToDelete && (
        <ModalDialog title="Delete this alert?" onClose={() => pendingAlertId === null && setAlertToDelete(null)}>
          <div className="delete-confirmation">
            <p><strong>{alertToDelete.name}</strong> will be permanently removed from your alerts.</p>
            <div className="app-modal-actions">
              <button type="button" className="secondary-button" onClick={() => setAlertToDelete(null)} disabled={pendingAlertId === alertToDelete.id}>Cancel</button>
              <button type="button" className="primary-button danger-button" onClick={() => void confirmDelete()} disabled={pendingAlertId === alertToDelete.id}>
                {pendingAlertId === alertToDelete.id ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </ModalDialog>
      )}

      <ToastRegion toast={toast} onDismiss={dismiss} />
    </>
  );
}

function SettingsPage({ onProfileUpdated }: { onProfileUpdated: (name: string) => void }) {
  const [profile, setProfile] = useState({ fullName: '', email: '', role: '', location: '' });
  const [isLoadingProfile, setIsLoadingProfile] = useState(true);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [preferences, setPreferences] = useState<{ darkMode: boolean; emailNotifications: boolean; animations: boolean; language: string; timezone: string }>({ darkMode: true, emailNotifications: true, animations: true, language: 'English', timezone: 'Asia/Kolkata' });
  const { toast, notify, dismiss } = useToast();

  useEffect(() => {
    let active = true;
    const loadProfile = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/profile`, {
          headers: getAuthorizationHeaders(),
        });
        if (!response.ok) {
          throw new Error(await getResponseError(response, 'Unable to load your profile.'));
        }
        const data = await response.json();
        if (active) {
          setProfile({
            fullName: data.full_name,
            email: data.email,
            role: data.role || '',
            location: data.location || '',
          });
          sessionStorage.setItem('jobhunt_user_name', data.full_name);
          onProfileUpdated(data.full_name);
        }
      } catch (error) {
        if (active) {
          notify(error instanceof Error ? error.message : 'Unable to load your profile.', 'error');
        }
      } finally {
        if (active) setIsLoadingProfile(false);
      }
    };
    void loadProfile();
    return () => { active = false; };
  }, [onProfileUpdated, notify]);

  const saveProfile = async () => {
    const fullName = profile.fullName.trim();
    const role = profile.role.trim();
    const location = profile.location.trim();
    if (fullName.length < 2 || role.length < 2 || location.length < 2) {
      notify('Enter a full name, role, and location (at least 2 characters each).', 'error');
      return;
    }

    setIsSavingProfile(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/profile`, {
        method: 'PUT',
        headers: {
          ...getAuthorizationHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ full_name: fullName, role, location }),
      });
      if (!response.ok) {
        throw new Error(await getResponseError(response, 'Unable to save profile changes.'));
      }
      const saved = await response.json();
      const nextProfile = {
        fullName: saved.full_name,
        email: saved.email,
        role: saved.role,
        location: saved.location,
      };
      setProfile(nextProfile);
      sessionStorage.setItem('jobhunt_user_name', saved.full_name);
      onProfileUpdated(saved.full_name);
      notify('Profile updated successfully!');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Unable to save profile changes.', 'error');
    } finally {
      setIsSavingProfile(false);
    }
  };

  return (
    <>
      <section className="panel settings-profile-panel">
        <div className="panel-header">
          <div>
            <span className="settings-kicker">ACCOUNT DETAILS</span>
            <h3>Profile &amp; Account</h3>
            <p>Keep your professional details current.</p>
          </div>
        </div>
        {isLoadingProfile ? (
          <div className="settings-loading" aria-live="polite"><span /> Loading your profile...</div>
        ) : (
          <>
            <div className="settings-grid">
              <label>
                Full Name
                <input
                  required
                  minLength={2}
                  maxLength={100}
                  autoComplete="name"
                  value={profile.fullName}
                  onChange={(event) => setProfile((current) => ({ ...current, fullName: event.target.value }))}
                />
              </label>
              <label>
                Email
                <input type="email" value={profile.email} readOnly aria-readonly="true" />
              </label>
              <label>
                Role / Title
                <input
                  required
                  minLength={2}
                  maxLength={100}
                  value={profile.role}
                  onChange={(event) => setProfile((current) => ({ ...current, role: event.target.value }))}
                />
              </label>
              <label>
                Location
                <input
                  required
                  minLength={2}
                  maxLength={120}
                  value={profile.location}
                  onChange={(event) => setProfile((current) => ({ ...current, location: event.target.value }))}
                />
              </label>
            </div>
            <button type="button" className="primary-button settings-save-button" onClick={() => void saveProfile()} disabled={isSavingProfile}>
              {isSavingProfile && <span className="button-spinner" aria-hidden="true" />}
              {isSavingProfile ? 'Saving Changes...' : 'Save Changes'}
            </button>
          </>
        )}
      </section>

      <section className="panel panel-spacer">
        <div className="panel-header">
          <div>
            <h3>Preferences</h3>
            <p>Customize your job search experience.</p>
          </div>
        </div>
        <div className="settings-list">
          <label><input type="checkbox" checked={preferences.darkMode} onChange={() => setPreferences((prev) => ({ ...prev, darkMode: !prev.darkMode }))} /> Dark mode</label>
          <label><input type="checkbox" checked={preferences.emailNotifications} onChange={() => setPreferences((prev) => ({ ...prev, emailNotifications: !prev.emailNotifications }))} /> Email notifications</label>
          <label><input type="checkbox" checked={preferences.animations} onChange={() => setPreferences((prev) => ({ ...prev, animations: !prev.animations }))} /> Animations</label>
          <label>Language<select value={preferences.language} onChange={(event) => setPreferences((prev) => ({ ...prev, language: event.target.value }))}><option>English</option><option>Hindi</option><option>Spanish</option></select></label>
          <label>Time zone<select value={preferences.timezone} onChange={(event) => setPreferences((prev) => ({ ...prev, timezone: event.target.value }))}><option value="Asia/Kolkata">Asia/Kolkata</option><option value="UTC">UTC</option></select></label>
        </div>
      </section>

        <ToastRegion toast={toast} onDismiss={dismiss} />
    </>
  );
}



function NotFoundPage() {

  return (

    <div className="empty-state">

      <div className="empty-icon">◆</div>

      <h3>Page not found</h3>

      <p>The page you requested could not be found.</p>

    </div>

  );

}



function JobMiniCard({ job }: { job: Job }) {

  const { toast, notify, dismiss } = useToast();

  const saveJob = () => {
    const current = readSavedJobs();
    const marker = `${job.company}-${job.title}-${job.url}`;

    if (current.some((item) => `${item.company}-${item.title}-${item.url}` === marker)) {
      notify('Job is already saved.', 'success');
      return;
    }

    localStorage.setItem('jobhunt_saved_jobs', JSON.stringify([...current, job]));
    notify('Job details saved successfully!', 'success');
  };

  return (

    <div className="mini-job-card">

      <div className="mini-card-top">

        <div>

          <strong>{job.title}</strong>

          <span>{job.company}</span>

        </div>

        <span className="match-badge">{Math.round(Number(job.combined_score ?? 0))}%</span>

      </div>

      <p>{job.location}</p>

      <div className="mini-actions">

        <button type="button" className="secondary-button" onClick={saveJob}>Save</button>

        <a href={job.url} target="_blank" rel="noreferrer">View details</a>

      </div>

      <ToastRegion toast={toast} onDismiss={dismiss} />

    </div>

  );

}



function JobCard({ job, rank }: { job: Job; rank: number }) {

  const [saved, setSaved] = useState(() => readSavedJobs().some((item) => `${item.company}-${item.title}-${item.url}` === `${job.company}-${job.title}-${job.url}`));

  const { toast, notify, dismiss } = useToast();



  const toggleSaved = () => {

    const current = readSavedJobs();

    const marker = `${job.company}-${job.title}-${job.url}`;

    const exists = current.some((item) => `${item.company}-${item.title}-${item.url}` === marker);

    const next = exists ? current.filter((item) => `${item.company}-${item.title}-${item.url}` !== marker) : [...current, job];

    localStorage.setItem('jobhunt_saved_jobs', JSON.stringify(next));

    setSaved(!exists);

    notify(exists ? 'Job removed from saved jobs.' : 'Job details saved successfully!', 'success');

  };



  return (

    <article className="job-card">

      <div className="job-card-header">

        <span className="rank">#{rank}</span>

        <span className="source-pill">{job.source || 'Unknown'}</span>

      </div>



      <div className="job-role">

        <div className="company-avatar">{(job.company || 'U').charAt(0).toUpperCase()}</div>

        <div>

          <h3>{job.title}</h3>

          <p>{job.company}</p>

        </div>

      </div>



      <div className="job-meta">

        <span>{job.location}</span>

        <span>{job.source || 'Source'}</span>

      </div>



      <div className="skill-list">

        {(job.matched_skills ?? ['React', 'TypeScript']).slice(0, 4).map((skill) => (

          <span key={skill} className="skill-pill">{skill}</span>

        ))}

      </div>



      <div className="score-row">

        <span>Match score</span>

        <strong>{Math.round(Number(job.combined_score ?? 0))}%</strong>

      </div>

      <div className="score-row">

        <span>ATS score</span>

        <strong>{job.ats_score == null || job.ats_score === '' ? 'N/A' : `${Math.round(Number(job.ats_score) <= 1 ? Number(job.ats_score) * 100 : Number(job.ats_score))}%`}</strong>

      </div>



      <div className="job-actions">

        <button type="button" className="secondary-button" onClick={toggleSaved}>{saved ? 'Unsave' : 'Save'}</button>

        <a href={job.url} target="_blank" rel="noreferrer" className="apply-link">Apply Now</a>

      </div>

      <ToastRegion toast={toast} onDismiss={dismiss} />

    </article>

  );

}



export default App;
