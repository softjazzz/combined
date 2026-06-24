-- Check the distribution of rules across document categories
SELECT 'Primary document category distribution:' as info;
SELECT 
  primary_document_category,
  COUNT(*) as rule_count
FROM public.qc_rules 
WHERE primary_document_category IS NOT NULL
GROUP BY primary_document_category
ORDER BY rule_count DESC;

SELECT 'Document categories array distribution:' as info;
WITH expanded AS (
  SELECT unnest(document_categories) as category
  FROM public.qc_rules
  WHERE document_categories IS NOT NULL AND array_length(document_categories, 1) > 0
)
SELECT 
  category,
  COUNT(*) as rule_count
FROM expanded
GROUP BY category
ORDER BY rule_count DESC;

SELECT 'Rules with empty or null categories:' as info;
SELECT 
  COUNT(*) as total_rules,
  COUNT(CASE WHEN primary_document_category IS NULL THEN 1 END) as null_primary,
  COUNT(CASE WHEN document_categories IS NULL OR array_length(document_categories, 1) = 0 THEN 1 END) as empty_categories
FROM public.qc_rules;

SELECT 'Sample rules for each category:' as info;
SELECT 
  primary_document_category,
  rule_code,
  name,
  document_categories
FROM public.qc_rules 
WHERE primary_document_category IS NOT NULL
ORDER BY primary_document_category, rule_code
LIMIT 20;
