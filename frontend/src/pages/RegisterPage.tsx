import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";

interface RegisterPageProps {
  onBackToLogin: () => void;
  variant?: "page" | "modal";
}

export function RegisterPage({ onBackToLogin, variant = "page" }: RegisterPageProps) {
  const { register } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("两次密码输入不一致");
      return;
    }

    setLoading(true);

    try {
      await register(username, email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败，请稍后再试");
    } finally {
      setLoading(false);
    }
  };

  const content = (
    <section className="auth-panel" aria-labelledby="register-title">
      <p className="auth-kicker">创建你的旅行空间</p>
      <h1 id="register-title">创建账号</h1>
      <p className="auth-copy">注册后可持续保存行程、预算与偏好。</p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          <span>用户名</span>
          <input
            aria-label="用户名"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label>
          <span>邮箱</span>
          <input
            aria-label="邮箱"
            autoComplete="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          <span>密码</span>
          <input
            aria-label="密码"
            autoComplete="new-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <label>
          <span>确认密码</span>
          <input
            aria-label="确认密码"
            autoComplete="new-password"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </label>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button className="primary-button full-width" type="submit" disabled={loading}>
          {loading ? "注册中..." : "注册"}
        </button>
        <button className="secondary-button full-width" type="button" onClick={onBackToLogin}>
          返回登录
        </button>
      </form>
    </section>
  );

  if (variant === "modal") {
    return content;
  }

  return <main className="auth-shell">{content}</main>;
}
