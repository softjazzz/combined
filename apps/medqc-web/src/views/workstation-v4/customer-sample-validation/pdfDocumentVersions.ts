import type { EditableMedicalRecordDocument } from './types'

/** 仅改变目录层级；所有PDF仍保留原key、正文及可选择入口。 */
export function groupPdfDocumentVersions(documents: EditableMedicalRecordDocument[]) {
  const parentCounts = new Map<string, number>()
  documents
    .filter((document) => document.document_type !== 'pdf_candidate')
    .forEach((document) => {
      parentCounts.set(document.key, (parentCounts.get(document.key) || 0) + 1)
    })
  const versionsByParent = new Map<string, EditableMedicalRecordDocument[]>()
  const parentByVersion = new Map<string, string>()
  documents.forEach((document) => {
    const parent = document.pdf_review_parent_key || ''
    if (document.document_type !== 'pdf_candidate' || parentCounts.get(parent) !== 1) return
    versionsByParent.set(parent, [...(versionsByParent.get(parent) || []), document])
    parentByVersion.set(document.key, parent)
  })
  return {
    primaryDocuments: documents.filter((document) => !parentByVersion.has(document.key)),
    versionsByParent,
    parentByVersion,
  }
}
