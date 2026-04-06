document.addEventListener('DOMContentLoaded', () => {
  // 设置页脚年份
  const yearSpan = document.getElementById('year');
  if (yearSpan) {
    yearSpan.textContent = new Date().getFullYear();
  }

  // 图片懒加载功能
  const lazyImages = document.querySelectorAll('img[data-src]');
  
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          const src = img.dataset.src;
          
          if (src) {
            // 创建新图片预加载
            const tempImg = new Image();
            tempImg.onload = () => {
              img.src = src;
              img.classList.add('loaded');
              img.removeAttribute('data-src');
            };
            tempImg.onerror = () => {
              img.classList.add('error');
              img.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23e5e7eb" width="100" height="100"/%3E%3Ctext x="50" y="50" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="14"%3E图片加载失败%3C/text%3E%3C/svg%3E';
            };
            tempImg.src = src;
            
            observer.unobserve(img);
          }
        }
      });
    }, {
      rootMargin: '50px 0px',
      threshold: 0.01
    });
    
    lazyImages.forEach(img => {
      imageObserver.observe(img);
    });
  } else {
    // 降级方案：直接加载所有图片
    lazyImages.forEach(img => {
      if (img.dataset.src) {
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
      }
    });
  }

  // 滚动动画功能
  const animatedElements = document.querySelectorAll('.animate-on-scroll');
  
  if ('IntersectionObserver' in window && animatedElements.length > 0) {
    const animationObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const element = entry.target;
          const animationType = element.dataset.animate || 'fade-in-up';
          const delay = parseInt(element.dataset.delay) || 0;
          
          // 添加延迟
          setTimeout(() => {
            element.classList.add('visible', animationType);
          }, delay);
          
          observer.unobserve(element);
        }
      });
    }, {
      rootMargin: '0px 0px -50px 0px',
      threshold: 0.1
    });
    
    animatedElements.forEach(element => {
      animationObserver.observe(element);
    });
  }

  // 回到顶部按钮功能
  const backToTopBtn = document.getElementById('back-to-top');
  if (backToTopBtn) {
    // 监听滚动事件
    window.addEventListener('scroll', () => {
      if (window.scrollY > 300) {
        backToTopBtn.classList.add('visible');
      } else {
        backToTopBtn.classList.remove('visible');
      }
    });

    // 点击回到顶部
    backToTopBtn.addEventListener('click', () => {
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    });
  }

  // 移动端菜单功能
  const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
  const mobileMenu = document.getElementById('mobile-menu');
  const mobileMenuOverlay = document.getElementById('mobile-menu-overlay');
  const mobileMenuLinks = document.querySelectorAll('.mobile-menu-link');

  if (mobileMenuToggle && mobileMenu && mobileMenuOverlay) {
    // 切换菜单
    mobileMenuToggle.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.contains('active');
      
      // 切换菜单状态
      mobileMenu.classList.toggle('active');
      mobileMenuOverlay.classList.toggle('active');
      mobileMenuToggle.classList.toggle('active');
      
      // 更新ARIA属性
      mobileMenuToggle.setAttribute('aria-expanded', !isOpen);
      mobileMenuToggle.setAttribute('aria-label', isOpen ? '打开菜单' : '关闭菜单');
      
      // 禁用/启用页面滚动
      document.body.style.overflow = isOpen ? '' : 'hidden';
    });

    // 点击遮罩层关闭菜单
    mobileMenuOverlay.addEventListener('click', () => {
      closeMobileMenu();
    });

    // 点击菜单链接后关闭菜单
    mobileMenuLinks.forEach(link => {
      link.addEventListener('click', () => {
        closeMobileMenu();
      });
    });

    // 关闭菜单函数
    function closeMobileMenu() {
      mobileMenu.classList.remove('active');
      mobileMenuOverlay.classList.remove('active');
      mobileMenuToggle.classList.remove('active');
      mobileMenuToggle.setAttribute('aria-expanded', 'false');
      mobileMenuToggle.setAttribute('aria-label', '打开菜单');
      document.body.style.overflow = '';
    }
  }

  // 表单验证和提交功能
  const form = document.getElementById('contact-form');
  const submitBtn = document.getElementById('submit-btn');
  const formTip = document.getElementById('form-tip');
  const formSuccess = document.getElementById('form-success');

  if (form && submitBtn) {
    // 表单字段配置
    const fields = {
      name: {
        element: document.getElementById('name'),
        errorElement: document.getElementById('name-error'),
        validate: (value) => {
          if (!value.trim()) return '请输入姓名';
          if (value.length < 2) return '姓名至少需要2个字符';
          if (value.length > 20) return '姓名不能超过20个字符';
          return '';
        }
      },
      email: {
        element: document.getElementById('email'),
        errorElement: document.getElementById('email-error'),
        validate: (value) => {
          if (!value.trim()) return '请输入邮箱';
          const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
          if (!emailRegex.test(value)) return '请输入有效的邮箱地址';
          return '';
        }
      },
      phone: {
        element: document.getElementById('phone'),
        errorElement: document.getElementById('phone-error'),
        validate: (value) => {
          if (value.trim()) {
            const phoneRegex = /^1[3-9]\d{9}$/;
            if (!phoneRegex.test(value)) return '请输入有效的手机号码';
          }
          return '';
        }
      },
      company: {
        element: document.getElementById('company'),
        errorElement: document.getElementById('company-error'),
        validate: (value) => {
          if (value.length > 50) return '公司名称不能超过50个字符';
          return '';
        }
      },
      message: {
        element: document.getElementById('message'),
        errorElement: document.getElementById('message-error'),
        validate: (value) => {
          if (!value.trim()) return '请输入留言内容';
          if (value.length < 10) return '留言内容至少需要10个字符';
          if (value.length > 500) return '留言内容不能超过500个字符';
          return '';
        }
      }
    };

    // 验证单个字段
    function validateField(fieldName) {
      const field = fields[fieldName];
      if (!field) return true;

      const value = field.element.value;
      const error = field.validate(value);

      if (error) {
        field.errorElement.textContent = error;
        field.errorElement.style.opacity = '1';
        field.element.setAttribute('aria-invalid', 'true');
        return false;
      } else {
        field.errorElement.textContent = '';
        field.errorElement.style.opacity = '0';
        field.element.setAttribute('aria-invalid', 'false');
        return true;
      }
    }

    // 验证所有字段
    function validateAll() {
      let isValid = true;
      for (const fieldName in fields) {
        if (!validateField(fieldName)) {
          isValid = false;
        }
      }
      return isValid;
    }

    // 实时验证（使用防抖）
    const debounce = (func, wait) => {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    };

    // 为每个字段添加实时验证
    for (const fieldName in fields) {
      const field = fields[fieldName];
      const debouncedValidate = debounce(() => validateField(fieldName), 300);

      field.element.addEventListener('blur', () => validateField(fieldName));
      field.element.addEventListener('input', debouncedValidate);
    }

    // 表单提交
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      // 验证所有字段
      if (!validateAll()) {
        // 滚动到第一个错误字段
        const firstError = form.querySelector('[aria-invalid="true"]');
        if (firstError) {
          firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
          firstError.focus();
        }
        return;
      }

      // 显示加载状态
      submitBtn.classList.add('loading');
      submitBtn.disabled = true;
      submitBtn.textContent = '提交中...';
      formTip.style.display = 'none';

      try {
        // 模拟异步提交
        await new Promise(resolve => setTimeout(resolve, 1500));

        // 显示成功消息
        form.style.display = 'none';
        formSuccess.style.display = 'flex';

        // 3秒后重置表单
        setTimeout(() => {
          form.reset();
          form.style.display = 'block';
          formSuccess.style.display = 'none';
          formTip.style.display = 'block';
          submitBtn.classList.remove('loading');
          submitBtn.disabled = false;
          submitBtn.textContent = '提交信息';

          // 重置所有字段状态
          for (const fieldName in fields) {
            fields[fieldName].element.setAttribute('aria-invalid', 'false');
            fields[fieldName].errorElement.style.opacity = '0';
          }
        }, 3000);

      } catch (error) {
        // 显示错误消息
        formTip.textContent = '提交失败，请稍后重试。';
        formTip.style.color = '#ef4444';
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
        submitBtn.textContent = '提交信息';
      }
    });
  }

  function fetchJsonWithStaticFallback(apiPath, staticFile) {
    return fetch(apiPath)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .catch(() =>
        fetch(new URL(staticFile, window.location.href).toString()).then((res) => {
          if (!res.ok) throw new Error('Failed');
          return res.json();
        }),
      );
  }

  // 从后端加载企业活动并渲染到首页（无 Flask 时回退 activities.json，uploads 仍由静态目录提供）
  const activitiesContainer = document.getElementById('activities-list');
  if (activitiesContainer) {
    fetchJsonWithStaticFallback('/api/activities', 'activities.json')
      .then((list) => {
        if (!Array.isArray(list) || list.length === 0) {
          activitiesContainer.textContent = '暂无企业活动，待后台上传后自动展示。';
          return;
        }

        activitiesContainer.innerHTML = '';
        list.forEach((item) => {
          const wrapper = document.createElement('div');
          wrapper.className = 'activity-item';

          const imgBox = document.createElement('div');
          imgBox.className = 'activity-image';
          const img = document.createElement('img');
          // 动态插入的图片不会进入首屏 lazyImages 查询，不能只用 data-src，否则永远不会被 Observer 挂上
          img.src = item.image;
          img.alt = item.title || '企业活动图片';
          img.loading = 'lazy';
          img.classList.add('loaded');
          imgBox.appendChild(img);

          const content = document.createElement('div');
          content.className = 'activity-content';
          const title = document.createElement('h3');
          title.textContent = item.title || '';
          const desc = document.createElement('p');
          desc.textContent = item.description || '';
          const date = document.createElement('div');
          date.className = 'activity-date';
          date.textContent = item.date || '';

          content.appendChild(title);
          content.appendChild(desc);
          content.appendChild(date);

          wrapper.appendChild(imgBox);
          wrapper.appendChild(content);
          activitiesContainer.appendChild(wrapper);
        });
      })
      .catch(() => {
        console.log('企业活动加载失败，使用占位内容');
        activitiesContainer.innerHTML = '<p>企业活动展示功能开发中...</p>';
      });
  }

  // 加载新闻列表和通知公告
  const newsList = document.getElementById('news-list');
  const noticeList = document.getElementById('notice-list');

  if (newsList || noticeList) {
    fetchJsonWithStaticFallback('/api/news', 'news.json')
      .then((items) => {
        if (!Array.isArray(items) || items.length === 0) {
          if (newsList) {
            newsList.textContent = '暂无新闻数据，待后台发布后自动展示。';
          }
          if (noticeList) {
            noticeList.textContent = '暂无通知公告。';
          }
          return;
        }

        if (newsList) {
          newsList.innerHTML = '';
          items.forEach((n) => {
            const card = document.createElement('article');
            card.className = 'news-card';
            const meta = document.createElement('div');
            meta.className = 'news-meta';
            meta.textContent = `${n.date || ''} | ${n.category || '公司新闻'}`;
            const title = document.createElement('h3');
            title.textContent = n.title || '';
            const summary = document.createElement('p');
            summary.textContent = n.summary || '';
            card.appendChild(meta);
            card.appendChild(title);
            card.appendChild(summary);
            newsList.appendChild(card);
          });
        }

        if (noticeList) {
          noticeList.innerHTML = '';
          const notices = items.filter(
            (n) => (n.category || '').includes('通知') || (n.category || '').includes('公告'),
          );
          if (notices.length === 0) {
            noticeList.textContent = '暂无通知公告。';
          } else {
            notices.forEach((n) => {
              const li = document.createElement('li');
              li.textContent = n.title || '';
              noticeList.appendChild(li);
            });
          }
        }
      })
      .catch(() => {
        if (newsList) {
          newsList.textContent = '新闻数据加载失败，请稍后重试。';
        }
        if (noticeList) {
          noticeList.textContent = '通知公告加载失败。';
        }
      });
  }

  // 多层嵌合导航：左侧菜单切换右侧“子页面”
  const portalSidebar = document.querySelector('.portal-sidebar');
  const portalSections = document.querySelectorAll('.portal-section');

  if (portalSidebar && portalSections.length) {
    portalSidebar.addEventListener('click', (event) => {
      const target = event.target;
      if (target instanceof HTMLAnchorElement && target.dataset.section) {
        event.preventDefault();
        const sectionKey = target.dataset.section;

        // 菜单高亮
        portalSidebar
          .querySelectorAll('li')
          .forEach((li) => li.classList.remove('active'));
        const li = target.closest('li');
        if (li) {
          li.classList.add('active');
        }

        // 内容区切换
        portalSections.forEach((sec) => {
          sec.classList.remove('active');
        });
        const targetSection = document.getElementById(`portal-${sectionKey}`);
        if (targetSection) {
          targetSection.classList.add('active');
          // 滚动到顶部一些，类似多级页面切换效果
          targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  }
});


