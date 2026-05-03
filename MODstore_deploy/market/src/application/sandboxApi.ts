const MODSTORE_API_BASE = ''

async function apiFetch(path, options = {}) {
  const url = `${MODSTORE_API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  return res.json()
}

export const sandboxApi = {
  async connectHost(hostUrl) {
    return apiFetch('/api/sandbox/connect', {
      method: 'POST',
      body: JSON.stringify({ host_url: hostUrl }),
    })
  },

  async pushAndTest(hostUrl, modId) {
    return apiFetch('/api/sandbox/push-and-test', {
      method: 'POST',
      body: JSON.stringify({ host_url: hostUrl, mod_id: modId }),
    })
  },

  async getHostStatus() {
    return apiFetch('/api/sandbox/host-status')
  },
}
