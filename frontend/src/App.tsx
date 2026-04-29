import { useEffect, useState } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ChatPage } from "./pages/ChatPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";

type AuthScreen = "login" | "register";

function AppShell() {
  const { user } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [screen, setScreen] = useState<AuthScreen>("login");

  useEffect(() => {
    if (user) {
      setAuthOpen(false);
      setScreen("login");
    }
  }, [user]);

  const openLogin = () => {
    setScreen("login");
    setAuthOpen(true);
  };

  return (
    <>
      <ChatPage onLoginRequired={openLogin} />

      {authOpen && (
        <div
          className="auth-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setAuthOpen(false);
            }
          }}
        >
          <div
            className="auth-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={screen === "login" ? "login-title" : "register-title"}
          >
            <button
              className="icon-button auth-modal-close"
              type="button"
              aria-label="关闭登录窗口"
              onClick={() => setAuthOpen(false)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
            {screen === "register" ? (
              <RegisterPage
                variant="modal"
                onBackToLogin={() => setScreen("login")}
              />
            ) : (
              <LoginPage
                variant="modal"
                onCreateAccount={() => setScreen("register")}
              />
            )}
          </div>
        </div>
      )}
    </>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}

export default App;
