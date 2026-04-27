import { FormEvent, useState } from 'react'
import { api } from '../../api'
import { appHref, navigate, redirectAfterAuth, replace } from '../navigation'
import '../AuthReact.css'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function doLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setErr('')
    try {
      await api.login(username, password)
      await replace(redirectAfterAuth())
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>登录</h2>
        {err ? <div className="flash flash-err">{err}</div> : null}
        <form onSubmit={doLogin}>
          <div className="form-group">
            <label>用户名</label>
            <input
              className="input"
              value={username}
              required
              autoComplete="username"
              onChange={(event) => setUsername(event.target.value)}
            />
          </div>
          <div className="form-group">
            <label>密码</label>
            <input
              className="input"
              type="password"
              value={password}
              required
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary-solid btn-block" disabled={loading}>
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
        <p className="auth-footer">
          <a
            href={appHref('/login-email')}
            className="link"
            onClick={(event) => {
              event.preventDefault()
              void navigate('/login-email')
            }}
          >
            邮箱验证码登录
          </a>
          {' · '}
          <a
            href={appHref('/forgot-password')}
            className="link"
            onClick={(event) => {
              event.preventDefault()
              void navigate('/forgot-password')
            }}
          >
            忘记密码
          </a>
          {' · 没有账号？'}
          <a
            href={appHref('/register')}
            className="link"
            onClick={(event) => {
              event.preventDefault()
              void navigate('/register')
            }}
          >
            注册
          </a>
        </p>
      </div>
    </div>
  )
}
