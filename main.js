document.addEventListener('DOMContentLoaded', () => {
  const year = document.getElementById('year')
  if (year) year.textContent = String(new Date().getFullYear())

  const toggle = document.getElementById('mobile-menu-toggle')
  const menu = document.getElementById('mobile-menu')
  const overlay = document.getElementById('mobile-menu-overlay')
  const links = document.querySelectorAll('.mobile-menu-link')

  function closeMenu() {
    if (!toggle || !menu || !overlay) return
    menu.classList.remove('active')
    overlay.classList.remove('active')
    toggle.classList.remove('active')
    toggle.setAttribute('aria-expanded', 'false')
    toggle.setAttribute('aria-label', '打开菜单')
    document.body.classList.remove('nav-open')
  }

  if (toggle && menu && overlay) {
    toggle.addEventListener('click', () => {
      const open = menu.classList.toggle('active')
      overlay.classList.toggle('active', open)
      toggle.classList.toggle('active', open)
      toggle.setAttribute('aria-expanded', String(open))
      toggle.setAttribute('aria-label', open ? '关闭菜单' : '打开菜单')
      document.body.classList.toggle('nav-open', open)
    })
    overlay.addEventListener('click', closeMenu)
    links.forEach((link) => link.addEventListener('click', closeMenu))
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeMenu()
    })
  }

  const revealItems = document.querySelectorAll('.reveal')
  if ('IntersectionObserver' in window && revealItems.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          const delay = Number(entry.target.dataset.delay || 0)
          window.setTimeout(() => entry.target.classList.add('visible'), delay)
          observer.unobserve(entry.target)
        })
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    )
    revealItems.forEach((item) => observer.observe(item))
  } else {
    revealItems.forEach((item) => item.classList.add('visible'))
  }

  const backToTop = document.getElementById('back-to-top')
  if (backToTop) {
    const update = () => backToTop.classList.toggle('visible', window.scrollY > 420)
    update()
    window.addEventListener('scroll', update, { passive: true })
    backToTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }))
  }

  const form = document.getElementById('contact-form')
  const success = document.getElementById('form-success')
  if (form) {
    const rules = {
      name: (value) => (!value.trim() ? '请输入姓名' : value.trim().length < 2 ? '姓名至少需要 2 个字符' : ''),
      phone: (value) => (value.trim() && !/^1[3-9]\d{9}$/.test(value.trim()) ? '请输入有效的手机号码' : ''),
      email: (value) => (!value.trim() ? '请输入邮箱' : !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()) ? '请输入有效的邮箱地址' : ''),
      company: (value) => (value.trim().length > 50 ? '公司名称不能超过 50 个字符' : ''),
      message: (value) => (!value.trim() ? '请输入需求描述' : value.trim().length < 10 ? '需求描述至少需要 10 个字符' : ''),
    }

    function validateField(name) {
      const input = form.elements[name]
      const errorNode = document.getElementById(`${name}-error`)
      if (!input || !rules[name]) return true
      const message = rules[name](input.value || '')
      if (errorNode) errorNode.textContent = message
      return !message
    }

    Object.keys(rules).forEach((name) => {
      const input = form.elements[name]
      if (!input) return
      input.addEventListener('blur', () => validateField(name))
      input.addEventListener('input', () => validateField(name))
    })

    form.addEventListener('submit', (event) => {
      event.preventDefault()
      const ok = Object.keys(rules).every(validateField)
      if (!ok) return
      if (success) success.classList.add('visible')
      form.reset()
    })
  }
})
