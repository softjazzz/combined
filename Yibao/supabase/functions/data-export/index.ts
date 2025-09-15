// Edge Function: data-export
// @ts-nocheck
// Purpose: Data export and report generation for medical insurance quality control
// Endpoints:
//   POST /data-export/generate - Generate reports in various formats
//   GET /data-export/templates - Get available report templates
//   POST /data-export/schedule - Schedule automated reports
//   GET /data-export/jobs - Get export job status

import { createClient } from 'npm:@supabase/supabase-js@2';

const ALLOWED_ORIGIN = Deno.env.get('ALLOWED_ORIGIN') || '*'
const corsHeaders = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization,Content-Type',
  'Access-Control-Max-Age': '86400'
};

// 报表模板定义
interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  type: 'violations' | 'departments' | 'doctors' | 'trends' | 'summary';
  fields: string[];
  defaultFormat: 'csv' | 'excel' | 'pdf';
  parameters: Record<string, any>;
}

const REPORT_TEMPLATES: ReportTemplate[] = [
  {
    id: 'violations_summary',
    name: '违规汇总报告',
    description: '按时间范围统计的违规数据汇总',
    type: 'violations',
    fields: ['date', 'total_violations', 'block_count', 'warn_count', 'info_count', 'unique_visits', 'unique_rules'],
    defaultFormat: 'excel',
    parameters: {
      timeRange: '30d',
      granularity: 'day',
      includeDetails: false
    }
  },
  {
    id: 'department_performance',
    name: '科室质控绩效报告',
    description: '各科室质控表现对比分析',
    type: 'departments',
    fields: ['department_name', 'total_violations', 'violation_rate', 'risk_level', 'quality_score', 'trend'],
    defaultFormat: 'excel',
    parameters: {
      timeRange: '30d',
      includeComparison: true,
      sortBy: 'total_violations'
    }
  },
  {
    id: 'doctor_quality_profile',
    name: '医生质控档案',
    description: '医生个人质控表现详细档案',
    type: 'doctors',
    fields: ['doctor_name', 'department_name', 'total_violations', 'violation_rate', 'quality_score', 'performance_grade', 'improvement_suggestions'],
    defaultFormat: 'pdf',
    parameters: {
      timeRange: '30d',
      includeProfile: true,
      departmentFilter: null
    }
  },
  {
    id: 'trend_analysis',
    name: '趋势分析报告',
    description: '违规趋势变化分析和预测',
    type: 'trends',
    fields: ['date', 'violations', 'trend', 'moving_average', 'anomalies', 'predictions'],
    defaultFormat: 'excel',
    parameters: {
      timeRange: '90d',
      includeAnalysis: true,
      includePredictions: true
    }
  },
  {
    id: 'executive_summary',
    name: '管理层汇总报告',
    description: '面向管理层的综合质控报告',
    type: 'summary',
    fields: ['kpi_summary', 'department_ranking', 'risk_alerts', 'improvement_recommendations'],
    defaultFormat: 'pdf',
    parameters: {
      timeRange: '30d',
      includeCharts: true,
      executiveLevel: true
    }
  }
];

function getSupabase() {
  const url = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? Deno.env.get('SUPABASE_ANON_KEY');
  if (!url || !serviceKey) {
    throw new Error('Missing SUPABASE_URL or service key env');
  }
  return createClient(url, serviceKey, { auth: { persistSession: false } });
}

// CSV 生成器
function generateCSV(data: any[], fields: string[]): string {
  if (!data.length) return '';
  
  // 生成表头
  const headers = fields.join(',');
  
  // 生成数据行
  const rows = data.map(row => {
    return fields.map(field => {
      const value = getNestedValue(row, field);
      // 处理包含逗号或引号的值
      if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value ?? '';
    }).join(',');
  });
  
  return [headers, ...rows].join('\n');
}

// 获取嵌套对象的值
function getNestedValue(obj: any, path: string): any {
  return path.split('.').reduce((current, key) => current?.[key], obj);
}

// Excel 生成器（简化版，生成 CSV 格式）
function generateExcel(data: any[], fields: string[]): string {
  // 在实际应用中，这里应该使用专门的 Excel 库
  // 目前返回 CSV 格式作为简化实现
  return generateCSV(data, fields);
}

// PDF 生成器（简化版，返回 HTML）
function generatePDF(data: any[], template: ReportTemplate): string {
  // 在实际应用中，这里应该使用 PDF 生成库
  // 目前返回 HTML 格式作为简化实现
  
  let html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>${template.name}</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .title { font-size: 24px; font-weight: bold; color: #333; }
        .subtitle { font-size: 14px; color: #666; margin-top: 10px; }
        .section { margin: 20px 0; }
        .section-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 2px solid #1890ff; padding-bottom: 5px; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f5f5f5; font-weight: bold; }
        .metric { display: inline-block; margin: 10px 20px 10px 0; }
        .metric-value { font-size: 24px; font-weight: bold; color: #1890ff; }
        .metric-label { font-size: 12px; color: #666; }
        .risk-high { color: #ff4d4f; }
        .risk-medium { color: #faad14; }
        .risk-low { color: #52c41a; }
      </style>
    </head>
    <body>
      <div class="header">
        <div class="title">${template.name}</div>
        <div class="subtitle">${template.description}</div>
        <div class="subtitle">生成时间: ${new Date().toLocaleString('zh-CN')}</div>
      </div>
  `;

  if (template.type === 'summary') {
    // 管理层汇总报告格式
    html += `
      <div class="section">
        <div class="section-title">关键指标概览</div>
        <div class="metric">
          <div class="metric-value">${data[0]?.total_violations || 0}</div>
          <div class="metric-label">总违规数</div>
        </div>
        <div class="metric">
          <div class="metric-value">${data[0]?.total_departments || 0}</div>
          <div class="metric-label">涉及科室</div>
        </div>
        <div class="metric">
          <div class="metric-value">${data[0]?.high_risk_count || 0}</div>
          <div class="metric-label">高风险项目</div>
        </div>
      </div>
    `;
  }

  // 生成数据表格
  if (data.length > 0) {
    html += `
      <div class="section">
        <div class="section-title">详细数据</div>
        <table>
          <thead>
            <tr>
              ${template.fields.map(field => `<th>${getFieldDisplayName(field)}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
    `;

    data.forEach(row => {
      html += '<tr>';
      template.fields.forEach(field => {
        const value = getNestedValue(row, field);
        let displayValue = value ?? '';
        
        // 特殊格式化
        if (field.includes('risk_level')) {
          displayValue = `<span class="risk-${value}">${value}</span>`;
        } else if (field.includes('rate') || field.includes('score')) {
          displayValue = typeof value === 'number' ? value.toFixed(2) : value;
        }
        
        html += `<td>${displayValue}</td>`;
      });
      html += '</tr>';
    });

    html += `
          </tbody>
        </table>
      </div>
    `;
  }

  html += `
    </body>
    </html>
  `;

  return html;
}

// 字段显示名称映射
function getFieldDisplayName(field: string): string {
  const fieldNames: Record<string, string> = {
    'date': '日期',
    'total_violations': '总违规数',
    'block_count': '阻断数',
    'warn_count': '警告数',
    'info_count': '提醒数',
    'unique_visits': '涉及就诊',
    'unique_rules': '触发规则',
    'department_name': '科室名称',
    'violation_rate': '违规率',
    'risk_level': '风险等级',
    'quality_score': '质控评分',
    'trend': '趋势',
    'doctor_name': '医生姓名',
    'performance_grade': '绩效等级',
    'improvement_suggestions': '改进建议'
  };
  
  return fieldNames[field] || field;
}

export async function handler(req: Request): Promise<Response> {
  try {
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const supabase = getSupabase();
    const url = new URL(req.url);
    const path = url.pathname.split('/').pop();

    switch (path) {
      case 'templates': {
        if (req.method !== 'GET') {
          return new Response('Method Not Allowed', { status: 405, headers: corsHeaders });
        }

        return Response.json({
          templates: REPORT_TEMPLATES,
          total: REPORT_TEMPLATES.length
        }, { headers: corsHeaders });
      }

      case 'generate': {
        if (req.method !== 'POST') {
          return new Response('Method Not Allowed', { status: 405, headers: corsHeaders });
        }

        const body = await req.json();
        const { templateId, format, parameters = {}, customFields } = body;

        // 查找模板
        const template = REPORT_TEMPLATES.find(t => t.id === templateId);
        if (!template) {
          return Response.json({ error: 'Template not found' }, { status: 404, headers: corsHeaders });
        }

        // 合并参数
        const mergedParams = { ...template.parameters, ...parameters };
        const outputFormat = format || template.defaultFormat;
        const fields = customFields || template.fields;

        // 根据模板类型获取数据
        let data: any[] = [];
        let filename = `${template.name}_${new Date().toISOString().split('T')[0]}`;

        // 这里应该调用相应的统计 API 获取数据
        // 为了演示，我们使用模拟数据
        if (template.type === 'violations') {
          // 调用违规统计 API
          const response = await fetch(`${url.origin}/supabase/functions/statistics/trends?days=${mergedParams.timeRange}&granularity=${mergedParams.granularity}&analysis=true`);
          if (response.ok) {
            const result = await response.json();
            data = result.trends || [];
          }
        } else if (template.type === 'departments') {
          // 调用科室统计 API
          const response = await fetch(`${url.origin}/supabase/functions/statistics/departments?range=${mergedParams.timeRange}&comparison=${mergedParams.includeComparison}`);
          if (response.ok) {
            const result = await response.json();
            data = result.departments || [];
          }
        } else if (template.type === 'doctors') {
          // 调用医生统计 API
          const response = await fetch(`${url.origin}/supabase/functions/statistics/doctors?range=${mergedParams.timeRange}&profile=${mergedParams.includeProfile}`);
          if (response.ok) {
            const result = await response.json();
            data = result.doctors || [];
          }
        }

        // 生成报告内容
        let content: string;
        let contentType: string;

        switch (outputFormat) {
          case 'csv':
            content = generateCSV(data, fields);
            contentType = 'text/csv';
            filename += '.csv';
            break;
          case 'excel':
            content = generateExcel(data, fields);
            contentType = 'application/vnd.ms-excel';
            filename += '.xlsx';
            break;
          case 'pdf':
            content = generatePDF(data, template);
            contentType = 'text/html'; // 实际应该是 application/pdf
            filename += '.html'; // 实际应该是 .pdf
            break;
          default:
            return Response.json({ error: 'Unsupported format' }, { status: 400, headers: corsHeaders });
        }

        // 返回生成的报告
        return new Response(content, {
          headers: {
            ...corsHeaders,
            'Content-Type': contentType,
            'Content-Disposition': `attachment; filename="${encodeURIComponent(filename)}"`,
            'X-Report-Template': templateId,
            'X-Report-Records': data.length.toString()
          }
        });
      }

      default:
        return Response.json({ error: 'Unknown endpoint' }, { status: 404, headers: corsHeaders });
    }

  } catch (e) {
    console.error('Data export error:', e);
    return Response.json({ error: String(e) }, { status: 500, headers: corsHeaders });
  }
}

Deno.serve(handler);
