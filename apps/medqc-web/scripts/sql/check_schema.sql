-- Check the actual schema of qc_rules table
SELECT 
  column_name,
  data_type,
  udt_name,
  is_nullable,
  column_default
FROM information_schema.columns 
WHERE table_name = 'qc_rules' 
  AND table_schema = 'public'
  AND column_name IN ('document_categories', 'primary_document_category')
ORDER BY ordinal_position;

-- Check if there are any enum types related to document categories
SELECT 
  t.typname as enum_name,
  e.enumlabel as enum_value
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid  
WHERE t.typname LIKE '%document%' OR t.typname LIKE '%category%'
ORDER BY t.typname, e.enumsortorder;

-- Sample data to understand current structure
SELECT 
  id,
  rule_code,
  primary_document_category,
  document_categories,
  pg_typeof(document_categories) as categories_type,
  pg_typeof(primary_document_category) as primary_type
FROM public.qc_rules 
LIMIT 5;
