import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api'
import { appHref, navigate, replace } from '../navigation'
import '../AuthReact.css'

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [sendCodeLoading, setSendCodeLoading] = useState(false)
  const [err, setErr] = useState('')
  const [cooldown, setCooldown] = useState(0)
  const timerRef = useRef<number | null>(null)

  const emailTrimmed = useMemo(() => email.trim(), [email])
  const sendDisabled = cooldown > 0 || loading || sendCodeLoading || !emailTrimmed
  const sendLabel = sendCodeLoading
    ? '发送中…'
    : cooldown > 0
      ? `${cooldown}s 后可重新获取`
      : '获取验证码'

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
    }
  }, [])

  function startCooldown(sec = 60) {
    setCooldown(sec)
    if (timerRef.current) window.clearInterval(timerRef.current)
    timerRef.current = window.setInterval(() => {
      setCooldown((prev) => {
        const next = prev - 1
        if (next <= 0 && timerRef.current) {
          window.clearInterval(timerRef.current)
          timerRef.current = null
        }
        return Math.max(0, next)
      })
    }, 1000)
  }

  async function sendCode() {
    setErr('')
    if (!emailTrimmed) {
      setErr('请先填写邮箱')
      return
    }
    if (sendCodeLoading) return
    setSendCodeLoading(true)
    try {
      await api.sendRegisterVerificationCode(emailTrimmed)
      startCooldown(60)
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setSendCodeLoading(false)
    }
  }

  async function doRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setErr('')
    try {
      const code = verificationCode.trim()
      if (!emailTrimmed) {
        setErr('请填写邮箱')
        return
      }
      if (!code) {
        setErr('请先点击「获取验证码」，填写邮件中的 6 位验证码')
        return
      }
      await api.register(username, password, emailTrimmed, code)
      await replace('/workbench')
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>注册</h2>
        {err ? <div className="flash flash-err">{err}</div> : null}
        <form onSubmit={doRegister}>
          <div className="form-group">
            <label>用户名</label>
            <input
              className="input"
              value={username}
              required
              minLength={2}
              maxLength={64}
              autoComplete="username"
              onChange={(event) => setUsername(event.target.value)}
            />
          </div>
          <div className="form-group">
            <label>邮箱（必填）</label>
            <p className="field-hint">用于登录与找回，请先填写邮箱再获取验证码。</p>
            <input
              className="input"
              type="email"
              value={email}
              required
              autoComplete="email"
              placeholder="name@example.com"
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="form-group form-group-code">
            <label>邮箱验证码</label>
            <div className="code-row">
              <input
                className="input input-code"
                value={verificationCode}
                required
                maxLength={8}
                autoComplete="one-time-code"
                placeholder="6 位数字"
                onChange={(event) => setVerificationCode(event.target.value)}
              />
              <button
                type="button"
                className="btn btn-send"
                disabled={sendDisabled}
                aria-busy={sendCodeLoading}
                onClick={() => void sendCode()}
              >
                {sendLabel}
              </button>
            </div>
          </div>
          <div className="form-group">
            <label>密码</label>
            <input
              className="input"
              type="password"
              value={password}
              required
              minLength={6}
              autoComplete="new-password"
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary-solid btn-block" disabled={loading}>
            {loading ? '注册中...' : '注册'}
          </button>
        </form>
        <p className="auth-footer">
          已有账号？
          <a
            href={appHref('/login')}
            className="link"
            onClick={(event) => {
              event.preventDefault()
              void navigate('/login')
            }}
          >
            登录
          </a>
        </p>
      </div>
    </div>
  )
}
