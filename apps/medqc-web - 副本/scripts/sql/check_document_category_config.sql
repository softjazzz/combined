-- Check document_category_config table
SELECT 'document_category_config table contents:' as info;
SELECT * FROM public.document_category_config ORDER BY sort_order;

-- Check if table exists
SELECT 'Table exists check:' as info;
SELECT EXISTS (
  SELECT FROM information_schema.tables 
  WHERE table_schema = 'public' 
  AND table_name = 'document_category_config'
) as table_exists;

-- Check table structure
SELECT 'Table structure:' as info;
SELECT 
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns 
WHERE table_name = 'document_category_config' 
  AND table_schema = 'public'
ORDER BY ordinal_position;
