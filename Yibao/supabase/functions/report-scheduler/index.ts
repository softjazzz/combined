// Edge Function: report-scheduler
// @ts-nocheck
// Purpose: Automated report generation and scheduling for medical insurance quality control
// Endpoints:
//   POST /report-scheduler/schedule - Schedule a new report
//   GET /report-scheduler/jobs - Get scheduled jobs
//   PUT /report-scheduler/jobs/:id - Update a scheduled job
//   DELETE /report-scheduler/jobs/:id - Delete a scheduled job
//   POST /report-scheduler/execute/:id - Manually execute a job
//   GET /report-scheduler/history - Get execution history

import { createClient } from 'npm:@supabase/supabase-js@2';

const ALLOWED_ORIGIN = Deno.env.get('ALLOWED_ORIGIN') || '*'
const corsHeaders = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization,Content-Type',
  'Access-Control-Max-Age': '86400'
};

// 报表调度任务接口
interface ScheduledReport {
  id?: string;
  name: string;
  description: string;
  template_id: string;
  schedule_type: 'daily' | 'weekly' | 'monthly' | 'custom';
  schedule_config: {
    time?: string; // HH:MM format
    day_of_week?: number; // 0-6, Sunday = 0
    day_of_month?: number; // 1-31
    cron_expression?: string; // For custom schedules
  };
  parameters: Record<string, any>;
  output_format: 'csv' | 'excel' | 'pdf';
  recipients: Array<{
    email: string;
    name?: string;
    type: 'to' | 'cc' | 'bcc';
  }>;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
  last_execution?: string;
  next_execution?: string;
}

// 执行历史接口
interface ExecutionHistory {
  id: string;
  job_id: string;
  execution_time: string;
  status: 'success' | 'failed' | 'running';
  duration_ms?: number;
  error_message?: string;
  output_size?: number;
  recipients_count?: number;
}

function getSupabase() {
  const url = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? Deno.env.get('SUPABASE_ANON_KEY');
  if (!url || !serviceKey) {
    throw new Error('Missing SUPABASE_URL or service key env');
  }
  return createClient(url, serviceKey, { auth: { persistSession: false } });
}

// 计算下次执行时间
function calculateNextExecution(schedule: ScheduledReport['schedule_config'], scheduleType: string): Date {
  const now = new Date();
  const next = new Date(now);

  switch (scheduleType) {
    case 'daily':
      if (schedule.time) {
        const [hours, minutes] = schedule.time.split(':').map(Number);
        next.setHours(hours, minutes, 0, 0);
        if (next <= now) {
          next.setDate(next.getDate() + 1);
        }
      } else {
        next.setDate(next.getDate() + 1);
      }
      break;

    case 'weekly':
      if (schedule.day_of_week !== undefined) {
        const targetDay = schedule.day_of_week;
        const currentDay = next.getDay();
        const daysUntilTarget = (targetDay - currentDay + 7) % 7;
        
        if (daysUntilTarget === 0) {
          // Same day, check time
          if (schedule.time) {
            const [hours, minutes] = schedule.time.split(':').map(Number);
            next.setHours(hours, minutes, 0, 0);
            if (next <= now) {
              next.setDate(next.getDate() + 7);
            }
          } else if (next <= now) {
            next.setDate(next.getDate() + 7);
          }
        } else {
          next.setDate(next.getDate() + daysUntilTarget);
          if (schedule.time) {
            const [hours, minutes] = schedule.time.split(':').map(Number);
            next.setHours(hours, minutes, 0, 0);
          }
        }
      }
      break;

    case 'monthly':
      if (schedule.day_of_month) {
        next.setDate(schedule.day_of_month);
        if (schedule.time) {
          const [hours, minutes] = schedule.time.split(':').map(Number);
          next.setHours(hours, minutes, 0, 0);
        }
        if (next <= now) {
          next.setMonth(next.getMonth() + 1);
        }
      }
      break;

    case 'custom':
      // 简化的 cron 解析，实际应用中应使用专门的 cron 库
      if (schedule.cron_expression) {
        // 这里应该实现 cron 表达式解析
        // 暂时设置为明天同一时间
        next.setDate(next.getDate() + 1);
      }
      break;

    default:
      next.setDate(next.getDate() + 1);
  }

  return next;
}

// 发送邮件通知（模拟实现）
async function sendEmailNotification(
  recipients: ScheduledReport['recipients'],
  subject: string,
  content: string,
  attachment?: { filename: string; content: string; mimeType: string }
): Promise<boolean> {
  try {
    // 在实际应用中，这里应该集成真实的邮件服务
    // 如 SendGrid, AWS SES, 或其他邮件服务提供商
    
    console.log('发送邮件通知:');
    console.log('收件人:', recipients.map(r => r.email).join(', '));
    console.log('主题:', subject);
    console.log('内容长度:', content.length);
    if (attachment) {
      console.log('附件:', attachment.filename);
    }
    
    // 模拟邮件发送延迟
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    return true;
  } catch (error) {
    console.error('邮件发送失败:', error);
    return false;
  }
}

// 执行报表生成任务
async function executeReportJob(job: ScheduledReport): Promise<ExecutionHistory> {
  const startTime = Date.now();
  const executionId = crypto.randomUUID();
  
  const history: ExecutionHistory = {
    id: executionId,
    job_id: job.id!,
    execution_time: new Date().toISOString(),
    status: 'running'
  };

  try {
    // 调用数据导出服务生成报表
    const exportResponse = await fetch(`${Deno.env.get('SUPABASE_URL')}/functions/v1/data-export/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${Deno.env.get('SUPABASE_ANON_KEY')}`
      },
      body: JSON.stringify({
        templateId: job.template_id,
        format: job.output_format,
        parameters: job.parameters
      })
    });

    if (!exportResponse.ok) {
      throw new Error(`报表生成失败: ${exportResponse.statusText}`);
    }

    const reportContent = await exportResponse.text();
    const outputSize = reportContent.length;

    // 发送邮件通知
    const emailSubject = `${job.name} - 定时报表`;
    const emailContent = `
      您好，

      这是您订阅的定时报表：${job.name}

      报表描述：${job.description}
      生成时间：${new Date().toLocaleString('zh-CN')}
      报表格式：${job.output_format.toUpperCase()}
      数据大小：${(outputSize / 1024).toFixed(2)} KB

      请查看附件中的详细报表。

      此邮件由智慧医保质控系统自动发送，请勿回复。
    `;

    const emailSent = await sendEmailNotification(
      job.recipients,
      emailSubject,
      emailContent,
      {
        filename: `${job.name}_${new Date().toISOString().split('T')[0]}.${job.output_format}`,
        content: reportContent,
        mimeType: job.output_format === 'csv' ? 'text/csv' : 
                  job.output_format === 'excel' ? 'application/vnd.ms-excel' : 
                  'application/pdf'
      }
    );

    if (!emailSent) {
      throw new Error('邮件发送失败');
    }

    // 更新执行历史
    history.status = 'success';
    history.duration_ms = Date.now() - startTime;
    history.output_size = outputSize;
    history.recipients_count = job.recipients.length;

  } catch (error) {
    history.status = 'failed';
    history.duration_ms = Date.now() - startTime;
    history.error_message = error.message;
  }

  return history;
}

export async function handler(req: Request): Promise<Response> {
  try {
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const supabase = getSupabase();
    const url = new URL(req.url);
    const pathParts = url.pathname.split('/').filter(Boolean);
    const action = pathParts[pathParts.length - 1];
    const id = pathParts[pathParts.length - 2];

    switch (req.method) {
      case 'GET': {
        if (action === 'jobs') {
          // 获取所有调度任务
          const { data: jobs, error } = await supabase
            .from('yibao_scheduled_reports')
            .select('*')
            .order('created_at', { ascending: false });

          if (error) {
            throw new Error(`获取调度任务失败: ${error.message}`);
          }

          return Response.json({
            jobs: jobs || [],
            total: jobs?.length || 0
          }, { headers: corsHeaders });

        } else if (action === 'history') {
          // 获取执行历史
          const jobId = url.searchParams.get('job_id');
          const limit = parseInt(url.searchParams.get('limit') || '50');
          
          let query = supabase
            .from('yibao_report_executions')
            .select('*')
            .order('execution_time', { ascending: false })
            .limit(limit);

          if (jobId) {
            query = query.eq('job_id', jobId);
          }

          const { data: history, error } = await query;

          if (error) {
            throw new Error(`获取执行历史失败: ${error.message}`);
          }

          return Response.json({
            history: history || [],
            total: history?.length || 0
          }, { headers: corsHeaders });
        }

        return Response.json({ error: 'Unknown endpoint' }, { status: 404, headers: corsHeaders });
      }

      case 'POST': {
        if (action === 'schedule') {
          // 创建新的调度任务
          const body = await req.json();
          const job: ScheduledReport = {
            ...body,
            id: crypto.randomUUID(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          };

          // 计算下次执行时间
          job.next_execution = calculateNextExecution(job.schedule_config, job.schedule_type).toISOString();

          const { data, error } = await supabase
            .from('yibao_scheduled_reports')
            .insert([job])
            .select()
            .single();

          if (error) {
            throw new Error(`创建调度任务失败: ${error.message}`);
          }

          return Response.json({
            job: data,
            message: '调度任务创建成功'
          }, { headers: corsHeaders });

        } else if (action === 'execute' && id) {
          // 手动执行任务
          const { data: job, error } = await supabase
            .from('yibao_scheduled_reports')
            .select('*')
            .eq('id', id)
            .single();

          if (error || !job) {
            return Response.json({ error: '任务不存在' }, { status: 404, headers: corsHeaders });
          }

          const history = await executeReportJob(job);

          // 保存执行历史
          await supabase
            .from('yibao_report_executions')
            .insert([history]);

          return Response.json({
            execution: history,
            message: history.status === 'success' ? '任务执行成功' : '任务执行失败'
          }, { headers: corsHeaders });
        }

        return Response.json({ error: 'Unknown endpoint' }, { status: 404, headers: corsHeaders });
      }

      case 'PUT': {
        if (id) {
          // 更新调度任务
          const body = await req.json();
          const updateData = {
            ...body,
            updated_at: new Date().toISOString()
          };

          // 如果调度配置发生变化，重新计算下次执行时间
          if (body.schedule_config || body.schedule_type) {
            updateData.next_execution = calculateNextExecution(
              body.schedule_config || {},
              body.schedule_type || 'daily'
            ).toISOString();
          }

          const { data, error } = await supabase
            .from('yibao_scheduled_reports')
            .update(updateData)
            .eq('id', id)
            .select()
            .single();

          if (error) {
            throw new Error(`更新调度任务失败: ${error.message}`);
          }

          return Response.json({
            job: data,
            message: '调度任务更新成功'
          }, { headers: corsHeaders });
        }

        return Response.json({ error: 'Missing job ID' }, { status: 400, headers: corsHeaders });
      }

      case 'DELETE': {
        if (id) {
          // 删除调度任务
          const { error } = await supabase
            .from('yibao_scheduled_reports')
            .delete()
            .eq('id', id);

          if (error) {
            throw new Error(`删除调度任务失败: ${error.message}`);
          }

          return Response.json({
            message: '调度任务删除成功'
          }, { headers: corsHeaders });
        }

        return Response.json({ error: 'Missing job ID' }, { status: 400, headers: corsHeaders });
      }

      default:
        return Response.json({ error: 'Method not allowed' }, { status: 405, headers: corsHeaders });
    }

  } catch (e) {
    console.error('Report scheduler error:', e);
    return Response.json({ error: String(e) }, { status: 500, headers: corsHeaders });
  }
}

Deno.serve(handler);
