-- 迁移：为 medical_documents 增加摘要与位置信息字段
ALTER TABLE medical_documents
  ADD COLUMN IF NOT EXISTS summary TEXT,
  ADD COLUMN IF NOT EXISTS position JSONB DEFAULT '{}';

COMMENT ON COLUMN medical_documents.summary IS 'AI生成的摘要内容（目录默认显示）';
COMMENT ON COLUMN medical_documents.position IS '在原文中的位置信息：startMarker、endMarker、startIndex、endIndex 等';

