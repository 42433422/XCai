import { computed, ref } from 'vue'
import { applyTemplateV2 } from '../employeeConfigV2'

export function useEmployeeWorkbenchState({
  parseWorkflowIdFromEntry,
  inferWorkflowIdFromManifest,
}) {
  const employeeTemplateId = ref('workflow')
  const employeeConfigV2 = ref(applyTemplateV2('workflow'))
  const employeeConfigErrors = ref([])
  const currentStep = ref(0)
  const cardModeEnabled = ref(true)

  const wizardSteps = [
    { id: 0, label: '0 模板' },
    { id: 1, label: '1 身份' },
    { id: 2, label: '2 感知' },
    { id: 3, label: '3 记忆' },
    { id: 4, label: '4 认知' },
    { id: 5, label: '5 行动' },
    { id: 6, label: '6 协作(心脏)' },
    { id: 7, label: '7 管理' },
    { id: 8, label: '8 测试审核' },
    { id: 9, label: '9 上架发布' },
  ]

  const listingHints = ref({
    industryRaw: '',
    industryCoerced: '',
    priceFromManifest: null,
  })

  const selectedFile = ref(null)
  const packageScanMessage = ref('')
  const packageScanKind = ref('info')
  const uploading = ref(false)
  const loading = ref(false)
  const v1CatalogLoadError = ref('')
  const error = ref('')
  const success = ref('')
  const myEmployees = ref([])

  const linkedModId = ref('')
  const linkedWorkflowIndex = ref(0)
  const linkedModName = ref('')
  const linkedModArtifact = ref('mod')
  const workflowJsonText = ref('')
  const workflowSaving = ref(false)
  const exportZipBusy = ref(false)
  const workflowPanelErr = ref('')
  const workflowPanelOk = ref('')
  const linkedManifestSnapshot = ref(null)
  const showLinkedModPanel = ref(false)
  const packageManifestWorkflowId = ref(0)

  const packageScanFlashClass = computed(() => {
    if (packageScanKind.value === 'ok') return 'flash-success'
    if (packageScanKind.value === 'warn') return 'flash-warn'
    return 'flash-info'
  })

  const resolvedWorkflowId = computed(() => {
    try {
      const o = JSON.parse(workflowJsonText.value || '{}')
      const fromEditor = parseWorkflowIdFromEntry(o)
      if (fromEditor > 0) return fromEditor
    } catch {
      /* fall through */
    }
    const snap = linkedManifestSnapshot.value
    if (snap && typeof snap === 'object') {
      const fromManifest = inferWorkflowIdFromManifest(snap, linkedWorkflowIndex.value)
      if (fromManifest > 0) return fromManifest
    }
    const p = packageManifestWorkflowId.value
    return Number.isFinite(p) && p > 0 ? p : 0
  })

  const safeResolvedWorkflowId = computed(() => {
    const n = Number(resolvedWorkflowId.value || 0)
    return Number.isFinite(n) && n > 0 ? n : 0
  })

  return {
    employeeTemplateId,
    employeeConfigV2,
    employeeConfigErrors,
    currentStep,
    cardModeEnabled,
    wizardSteps,
    listingHints,
    selectedFile,
    packageScanMessage,
    packageScanKind,
    uploading,
    loading,
    v1CatalogLoadError,
    error,
    success,
    myEmployees,
    linkedModId,
    linkedWorkflowIndex,
    linkedModName,
    linkedModArtifact,
    workflowJsonText,
    workflowSaving,
    exportZipBusy,
    workflowPanelErr,
    workflowPanelOk,
    linkedManifestSnapshot,
    showLinkedModPanel,
    packageManifestWorkflowId,
    packageScanFlashClass,
    resolvedWorkflowId,
    safeResolvedWorkflowId,
  }
}
