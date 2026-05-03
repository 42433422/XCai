import { ref, computed } from 'vue'

const hostUrl = ref('')
const connected = ref(false)
const hostInfo = ref(null)

export function useHostConnection() {
  const statusText = computed(() => {
    if (connected.value) return '已连接'
    return '未连接'
  })

  const statusClass = computed(() => {
    return connected.value ? 'ok' : 'pending'
  })

  function setConnected(url, info) {
    hostUrl.value = url
    connected.value = true
    hostInfo.value = info
  }

  function setDisconnected() {
    connected.value = false
    hostInfo.value = null
  }

  return {
    hostUrl,
    connected,
    hostInfo,
    statusText,
    statusClass,
    setConnected,
    setDisconnected,
  }
}
