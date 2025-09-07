import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface BatchUploadRequest {
  taskId: string
  files: Array<{
    name: string
    content: string
    size: number
    type: string
  }>
}

interface MedicalRecordData {
  patient_name: string
  patient_age: number
  patient_gender: 'M' | 'F' | 'U'
  department: string
  admission_date: string
  record_type: 'inpatient' | 'outpatient' | 'emergency'
  content: string
  file_name?: string
  file_size?: number
  status: 'pending'
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Initialize Supabase client
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    )

    // Get user from Authorization header
    const authHeader = req.headers.get('Authorization')
    if (!authHeader) {
      throw new Error('Missing authorization header')
    }

    const { data: { user }, error: authError } = await supabaseClient.auth.getUser(
      authHeader.replace('Bearer ', '')
    )

    if (authError || !user) {
      throw new Error('Invalid authorization token')
    }

    // Parse request body
    const { taskId, files }: BatchUploadRequest = await req.json()

    if (!taskId || !files || !Array.isArray(files)) {
      throw new Error('Invalid request body')
    }

    console.log(`Processing batch upload for task ${taskId} with ${files.length} files`)

    // Update task status to processing
    await supabaseClient
      .from('batch_processing_tasks')
      .update({
        status: 'processing',
        started_at: new Date().toISOString()
      })
      .eq('id', taskId)
      .eq('user_id', user.id)

    const results = []
    let processedCount = 0
    let failedCount = 0

    // Process files in batches of 5
    const batchSize = 5
    for (let i = 0; i < files.length; i += batchSize) {
      const batch = files.slice(i, i + batchSize)
      
      // Process current batch
      const batchPromises = batch.map(async (file, batchIndex) => {
        const globalIndex = i + batchIndex
        
        try {
          // Extract basic patient info from filename or content
          const patientInfo = extractPatientInfo(file.name, file.content)
          
          // Create medical record data
          const recordData: MedicalRecordData = {
            patient_name: patientInfo.name || `批量导入患者-${globalIndex + 1}`,
            patient_age: patientInfo.age || 50,
            patient_gender: patientInfo.gender || 'U',
            department: patientInfo.department || '批量导入',
            admission_date: patientInfo.admissionDate || new Date().toISOString().split('T')[0],
            record_type: patientInfo.recordType || 'inpatient',
            content: file.content,
            file_name: file.name,
            file_size: file.size,
            status: 'pending'
          }

          // Insert medical record
          const { data: record, error: insertError } = await supabaseClient
            .from('medical_records')
            .insert(recordData)
            .select()
            .single()

          if (insertError) {
            throw new Error(`Database insert failed: ${insertError.message}`)
          }

          processedCount++
          
          return {
            success: true,
            fileName: file.name,
            recordId: record.id,
            index: globalIndex
          }
        } catch (error) {
          failedCount++
          console.error(`Failed to process file ${file.name}:`, error)
          
          return {
            success: false,
            fileName: file.name,
            error: error instanceof Error ? error.message : 'Unknown error',
            index: globalIndex
          }
        }
      })

      // Wait for current batch to complete
      const batchResults = await Promise.all(batchPromises)
      results.push(...batchResults)

      // Update task progress
      const progress = Math.round(((i + batch.length) / files.length) * 100)
      await supabaseClient
        .from('batch_processing_tasks')
        .update({
          processed_items: processedCount + failedCount,
          failed_items: failedCount,
          progress_percentage: progress
        })
        .eq('id', taskId)

      // Small delay between batches to avoid overwhelming the database
      if (i + batchSize < files.length) {
        await new Promise(resolve => setTimeout(resolve, 100))
      }
    }

    // Update final task status
    const finalStatus = failedCount === 0 ? 'completed' : (processedCount === 0 ? 'failed' : 'completed')
    await supabaseClient
      .from('batch_processing_tasks')
      .update({
        status: finalStatus,
        completed_at: new Date().toISOString(),
        processed_items: processedCount + failedCount,
        failed_items: failedCount,
        progress_percentage: 100,
        error_details: failedCount > 0 ? {
          message: `${failedCount} files failed to process`,
          failedFiles: results.filter(r => !r.success).map(r => ({
            fileName: r.fileName,
            error: r.error
          }))
        } : null
      })
      .eq('id', taskId)

    console.log(`Batch upload completed: ${processedCount} success, ${failedCount} failed`)

    return new Response(
      JSON.stringify({
        success: true,
        data: {
          taskId,
          totalFiles: files.length,
          processedCount,
          failedCount,
          successRate: Math.round((processedCount / files.length) * 100),
          results
        }
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      }
    )

  } catch (error) {
    console.error('Batch upload error:', error)
    
    return new Response(
      JSON.stringify({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred'
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 500,
      }
    )
  }
})

/**
 * Extract patient information from filename and content
 */
function extractPatientInfo(fileName: string, content: string) {
  const info: {
    name?: string
    age?: number
    gender?: 'M' | 'F' | 'U'
    department?: string
    admissionDate?: string
    recordType?: 'inpatient' | 'outpatient' | 'emergency'
  } = {}

  // Try to extract patient name from filename
  const nameMatch = fileName.match(/^([^_\-\d]+)/)
  if (nameMatch) {
    info.name = nameMatch[1].trim()
  }

  // Try to extract information from content
  const lines = content.split('\n').slice(0, 20) // Check first 20 lines
  
  for (const line of lines) {
    const cleanLine = line.trim()
    
    // Extract patient name
    if (!info.name) {
      const namePatterns = [
        /姓名[：:]\s*([^\s,，]+)/,
        /患者[：:]\s*([^\s,，]+)/,
        /病人[：:]\s*([^\s,，]+)/
      ]
      
      for (const pattern of namePatterns) {
        const match = cleanLine.match(pattern)
        if (match) {
          info.name = match[1]
          break
        }
      }
    }

    // Extract age
    if (!info.age) {
      const ageMatch = cleanLine.match(/年龄[：:]\s*(\d+)/)
      if (ageMatch) {
        info.age = parseInt(ageMatch[1])
      }
    }

    // Extract gender
    if (!info.gender) {
      if (cleanLine.includes('性别：男') || cleanLine.includes('性别:男')) {
        info.gender = 'M'
      } else if (cleanLine.includes('性别：女') || cleanLine.includes('性别:女')) {
        info.gender = 'F'
      }
    }

    // Extract department
    if (!info.department) {
      const deptPatterns = [
        /科室[：:]\s*([^\s,，]+)/,
        /入院科室[：:]\s*([^\s,，]+)/,
        /所属科室[：:]\s*([^\s,，]+)/
      ]
      
      for (const pattern of deptPatterns) {
        const match = cleanLine.match(pattern)
        if (match) {
          info.department = match[1]
          break
        }
      }
    }

    // Extract admission date
    if (!info.admissionDate) {
      const dateMatch = cleanLine.match(/入院时间[：:]\s*(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})/)
      if (dateMatch) {
        info.admissionDate = dateMatch[1].replace(/\//g, '-')
      }
    }
  }

  // Determine record type based on content
  if (content.includes('急诊') || content.includes('急救')) {
    info.recordType = 'emergency'
  } else if (content.includes('门诊') || content.includes('outpatient')) {
    info.recordType = 'outpatient'
  } else {
    info.recordType = 'inpatient'
  }

  return info
}

/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/batch-upload' \
    --header 'Authorization: Bearer [YOUR_ANON_KEY]' \
    --header 'Content-Type: application/json' \
    --data '{"taskId":"test-task-id","files":[{"name":"test.txt","content":"test content","size":100,"type":"text/plain"}]}'

*/
