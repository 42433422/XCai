import { serializeVisibleDom } from '../../utils/agent/pageSerializer'
import { captureViewport } from '../../utils/agent/screenshotCapture'
import { useRoute } from 'vue-router'

export function usePageAnalyzer() {
  const route = useRoute()

  function getPageContext(): string {
    const dom = serializeVisibleDom()
    return `路由：${route.fullPath}\n${dom}`
  }

  async function getPageContextWithScreenshot(): Promise<{
    textSummary: string
    screenshotDataUrl: string | null
  }> {
    const textSummary = getPageContext()
    const screenshotDataUrl = await captureViewport()
    return { textSummary, screenshotDataUrl }
  }

  return { getPageContext, getPageContextWithScreenshot }
}
