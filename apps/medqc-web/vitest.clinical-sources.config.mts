import { defineConfig } from 'vitest/config'
import base from './vitest.config'

export default defineConfig({
  ...base,
  test: {
    ...base.test,
    setupFiles: ['./tests/setup.ts', './tests/clinical-source-network-guard.ts'],
    include: [
      'tests/unit/views/workstation-v4/usePatientRecords.spec.ts',
      'tests/unit/views/workstation-v4/RecordPoolPreviewPanel.spec.ts',
      'tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts',
      'tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts',
      'tests/unit/clinicalSources.spec.ts',
      'tests/unit/views/workstation-v4/semantic-rules/QCRecordCompareWorkbench.spec.ts',
      'tests/unit/views/workstation-v4/components/qc/QcRunSelectedControl.spec.ts',
    ],
    maxWorkers: 1,
    minWorkers: 1,
  },
})
