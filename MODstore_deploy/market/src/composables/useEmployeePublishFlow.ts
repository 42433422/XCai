import { computed, ref } from 'vue'
import { api } from '../api'

export function useEmployeePublishFlow({
  form,
  selectedFile,
  resolvedWorkflowId,
  linkedModId,
  listingHints,
  employeeConfigV2,
}) {
  const publishWizardStep = ref('compose')
  const listingDefaultsApplied = ref(false)
  const wfSandboxInputJson = ref('{\n  "topic": "示例主题"\n}')
  const wfSandboxLoading = ref(false)
  const wfSandboxErr = ref('')
  const wfSandboxReport = ref(null)
  const wfSandboxOk = ref(false)
  const dockerLocalAck = ref(false)
  const auditReport = ref(null)
  const auditLoading = ref(false)
  const auditErr = ref('')

  const sandboxGateOk = computed(() => {
    if (!selectedFile.value) return false
    if (resolvedWorkflowId.value > 0) return wfSandboxOk.value === true && wfSandboxReport.value?.ok === true
    return dockerLocalAck.value === true
  })

  const canConfirmListingUpload = computed(() => {
    if (publishWizardStep.value !== 'listing') return false
    if (!selectedFile.value) return false
    if (!sandboxGateOk.value) return false
    if (auditLoading.value || auditErr.value) return false
    if (auditReport.value?.summary?.pass !== true) return false
    if (!String(form.value.industry || '').trim()) return false
    const pr = Number(form.value.price)
    return Number.isFinite(pr) && pr >= 0
  })

  function applyListingDefaultsFromHints() {
    form.value.industry = listingHints.value.industryCoerced || '通用'
    const p = listingHints.value.priceFromManifest
    form.value.price = p != null && Number.isFinite(p) ? p : 0
  }

  async function runEmployeeWorkflowSandbox() {
    const wid = resolvedWorkflowId.value
    if (!wid || !selectedFile.value) return
    wfSandboxLoading.value = true
    wfSandboxErr.value = ''
    wfSandboxReport.value = null
    wfSandboxOk.value = false
    try {
      let input = {}
      const raw = (wfSandboxInputJson.value || '').trim()
      if (raw) {
        const o = JSON.parse(raw)
        input = typeof o === 'object' && o !== null && !Array.isArray(o) ? o : {}
      }
      const r1 = await api.workflowSandboxRun(wid, { input_data: input, mock_employees: true, validate_only: true })
      if (!r1.ok) { wfSandboxReport.value = r1; return }
      const r2 = await api.workflowSandboxRun(wid, { input_data: input, mock_employees: true, validate_only: false })
      wfSandboxReport.value = r2
      wfSandboxOk.value = r2.ok === true
    } catch (e) {
      wfSandboxErr.value = e.message || String(e)
    } finally {
      wfSandboxLoading.value = false
    }
  }

  async function runFiveDimAuditClick(packageArtifact) {
    if (!selectedFile.value || !sandboxGateOk.value) return
    auditLoading.value = true
    auditErr.value = ''
    auditReport.value = null
    listingDefaultsApplied.value = false
    try {
      const art = (packageArtifact || '').trim().toLowerCase()
      const meta: Record<string, unknown> = { employee_config_v2: employeeConfigV2.value }
      if (art === 'mod' || art === 'employee_pack') meta.artifact = art
      if (linkedModId.value) meta.probe_mod_id = linkedModId.value
      auditReport.value = await api.auditPackage(selectedFile.value, meta)
    } catch (e) {
      auditErr.value = e.message || String(e)
    } finally {
      auditLoading.value = false
    }
  }

  function backToComposeFromTesting() {
    publishWizardStep.value = 'compose'
    wfSandboxOk.value = false
    wfSandboxReport.value = null
    wfSandboxErr.value = ''
    dockerLocalAck.value = false
    auditReport.value = null
    auditErr.value = ''
    listingDefaultsApplied.value = false
  }

  function goListingStep() {
    if (!auditReport.value?.summary?.pass) return
    if (!listingDefaultsApplied.value) {
      applyListingDefaultsFromHints()
      listingDefaultsApplied.value = true
    }
    publishWizardStep.value = 'listing'
  }

  function backToTestingFromListing() {
    publishWizardStep.value = 'testing'
  }

  return {
    publishWizardStep,
    listingDefaultsApplied,
    wfSandboxInputJson,
    wfSandboxLoading,
    wfSandboxErr,
    wfSandboxReport,
    wfSandboxOk,
    dockerLocalAck,
    auditReport,
    auditLoading,
    auditErr,
    sandboxGateOk,
    canConfirmListingUpload,
    runEmployeeWorkflowSandbox,
    runFiveDimAuditClick,
    backToComposeFromTesting,
    goListingStep,
    backToTestingFromListing,
  }
}
