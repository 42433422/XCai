import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api'
import { appHref, navigate, replace } from '../navigation'
import '../AuthReact.css'

export default function ForgotPasswordPage() {
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [sending, setSending] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef<number | null>(null)

  const canReset = useMemo(
    () => code.trim().length >= 4 && newPassword.length >= 6 && newPassword === confirmPassword,
    [code, newPassword, confirmPassword],
  )

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
    }
  }, [])

  function startCooldown(sec: number) {
    setCountdown(sec)
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

  async function sendCode() {
    setErr('')
    setMsg('')
    const em = email.trim().toLowerCase()
    if (!em || !em.includes('@')) {
      setErr('请填写有效邮箱')
      return
    }
    setSending(true)
    try {
      const res = await api.sendResetPasswordCode(em)
      setMsg(res?.message || '若邮箱已注册，将收到验证码')
      setStep(2)
      startCooldown(60)
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setSending(false)
    }
  }

  async function resetPw() {
    setErr('')
    setMsg('')
    if (!canReset) return
    setResetting(true)
    try {
      await api.resetPassword(email.trim().toLowerCase(), code.trim(), newPassword)
      setMsg('密码已重置，请使用新密码登录')
      window.setTimeout(() => void replace('/login'), 1200)
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="auth-page auth-page--forgot">
      <div className="auth-card">
        <h2>忘记密码</h2>
        {msg ? <div className="flash flash-ok">{msg}</div> : null}
        {err ? <div className="flash flash-err">{err}</div> : null}

        {step === 1 ? (
          <div className="form-block">
            <div className="form-group">
              <label>注册邮箱</label>
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                className="input"
                required
                autoComplete="email"
              />
            </div>
            <button
              type="button"
              className="btn btn-primary-solid btn-block"
              disabled={sending || countdown > 0}
              onClick={() => void sendCode()}
            >
              {countdown > 0 ? `${countdown}s 后可重发` : sending ? '发送中…' : '发送验证码'}
            </button>
          </div>
        ) : (
          <div className="form-block">
            <div className="form-group">
              <label>验证码</label>
              <input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                className="input"
                maxLength={16}
                autoComplete="one-time-code"
              />
            </div>
            <div className="form-group">
              <label>新密码（至少 6 位）</label>
              <input
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                type="password"
                className="input"
                minLength={6}
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label>确认新密码</label>
              <input
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                type="password"
                className="input"
                minLength={6}
                autoComplete="new-password"
              />
            </div>
            <button
              type="button"
              className="btn btn-primary-solid btn-block"
              disabled={!canReset || resetting}
              onClick={() => void resetPw()}
            >
              {resetting ? '提交中…' : '重置密码'}
            </button>
          </div>
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
            返回登录
          </a>
        </p>
      </div>
    </div>
  )
}
