import { FormEvent, useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import { appHref, navigate, redirectAfterAuth, replace } from '../navigation'
import '../AuthReact.css'

export default function LoginByEmailPage() {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [codeSent, setCodeSent] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    const storedEmail = sessionStorage.getItem('login_email')
    if (storedEmail) setEmail(storedEmail)
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
    }
  }, [])

  function startCountdown() {
    setCountdown(60)
    if (timerRef.current) window.clearInterval(timerRef.current)
    timerRef.current = window.setInterval(() => {
      setCountdown((prev) => {
        const next = prev - 1
        if (next <= 0 && timerRef.current) {
          window.clearInterval(timerRef.current)
          timerRef.current = null
        }
        return Math.max(0, next)
      })
    }, 1000)
  }

  async function sendCode(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    setErr('')
    setLoading(true)
    try {
      await api.sendVerificationCode(email)
      setCodeSent(true)
      setSent(true)
      sessionStorage.setItem('login_email', email)
      startCountdown()
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  async function resendCode() {
    setSent(false)
    await sendCode()
  }

  async function doLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErr('')
    setLoading(true)
    try {
      await api.loginWithCode(email, code)
      await replace(redirectAfterAuth())
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page auth-page--email">
      <div className="auth-card">
        <h2>邮箱验证码登录</h2>
        {err ? <div className="flash flash-err">{err}</div> : null}
        {sent ? <div className="flash flash-ok">验证码已发送，请查收邮箱</div> : null}

        {!codeSent ? (
          <form onSubmit={sendCode}>
            <div className="form-group">
              <label>邮箱地址</label>
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                className="input"
                required
                placeholder="your@email.com"
              />
            </div>
            <button type="submit" className="btn btn-primary-solid btn-block" disabled={loading}>
              {loading ? '发送中...' : '发送验证码'}
            </button>
          </form>
        ) : (
          <form onSubmit={doLogin}>
            <div className="form-group">
              <label>邮箱地址</label>
              <input value={email} type="email" className="input" disabled />
            </div>
            <div className="form-group">
              <label>验证码</label>
              <input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                type="text"
                className="input"
                required
                placeholder="6位验证码"
                maxLength={6}
              />
            </div>
            {countdown > 0 ? (
              <div className="countdown">{countdown}s 后可重新发送</div>
            ) : (
              <button type="button" className="btn btn-text" onClick={() => void resendCode()}>
                重新发送验证码
              </button>
            )}
            <button type="submit" className="btn btn-primary-solid btn-block" disabled={loading}>
              {loading ? '登录中...' : '登录'}
            </button>
          </form>
        )}

        <p className="auth-footer">
          <a
            href={appHref('/login')}
            className="link"
            onClick={(event) => {
              event.preventDefault()
              void navigate('/login')
            }}
          >
            ← 返回密码登录
          </a>
        </p>
      </div>
    </div>
  )
}
