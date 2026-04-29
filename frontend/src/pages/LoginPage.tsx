import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";

interface LoginPageProps {
  onCreateAccount: () => void;
  variant?: "page" | "modal";
}

export function LoginPage({ onCreateAccount, variant = "page" }: LoginPageProps) {
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(identifier, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败，请稍后再试");
    } finally {
      setLoading(false);
    }
  };

  const content = (
    <section className="auth-panel" aria-labelledby="login-title">
      <p className="auth-kicker">继续使用旅行规划助手</p>
      <h1 id="login-title">登录后开始规划</h1>
      <p className="auth-copy">登录后可生成完整行程、保存对话，并查看历史方案。</p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          <span>账号</span>
          <input
            aria-label="账号"
            autoComplete="username"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
          />
        </label>
        <label>
          <span>密码</span>
          <input
            aria-label="密码"
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button className="primary-button full-width" type="submit" disabled={loading}>
          {loading ? "登录中..." : "登录"}
        </button>
        <button
          className="secondary-button full-width"
          type="button"
          onClick={onCreateAccount}
        >
          创建账号
        </button>
      </form>
    </section>
  );

  if (variant === "modal") {
    return content;
  }

  return <main className="auth-shell">{content}</main>;
}
