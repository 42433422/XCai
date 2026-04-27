import { describe, expect, it } from 'vitest'
import { useEmployeeWorkbenchState } from './useEmployeeWorkbenchState'

describe('useEmployeeWorkbenchState', () => {
  it('resolves workflow id from editor JSON before manifest fallback', () => {
    const state = useEmployeeWorkbenchState({
      parseWorkflowIdFromEntry: (entry: any) => Number(entry.workflow_id || 0),
      inferWorkflowIdFromManifest: () => 99,
    })

    state.workflowJsonText.value = '{"workflow_id": 42}'
    state.linkedManifestSnapshot.value = { workflow_employees: [{ workflow_id: 99 }] }

    expect(state.resolvedWorkflowId.value).toBe(42)
    expect(state.safeResolvedWorkflowId.value).toBe(42)
  })

  it('falls back to scanned package workflow id', () => {
    const state = useEmployeeWorkbenchState({
      parseWorkflowIdFromEntry: () => 0,
      inferWorkflowIdFromManifest: () => 0,
    })

    state.packageManifestWorkflowId.value = 17

    expect(state.packageScanFlashClass.value).toBe('flash-info')
    expect(state.resolvedWorkflowId.value).toBe(17)
  })
})
