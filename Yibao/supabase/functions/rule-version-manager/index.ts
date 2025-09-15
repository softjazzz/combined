// Edge Function: rule-version-manager
// Purpose: 规则版本管理 - 快照、回滚、对比功能
// Methods: POST /create-snapshot, POST /rollback, GET /compare, GET /versions

import { createClient } from 'npm:@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization,Content-Type',
  'Access-Control-Max-Age': '86400'
};

function getSupabase() {
  const url = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? Deno.env.get('SUPABASE_ANON_KEY');
  if (!url || !serviceKey) {
    throw new Error('Missing SUPABASE_URL or service key env');
  }
  return createClient(url, serviceKey, { auth: { persistSession: false } });
}

// 创建规则快照
async function createSnapshot(supabase: any, params: any) {
  const { version_name, description, created_by } = params;
  
  if (!version_name) {
    throw new Error('version_name is required');
  }

  // 检查版本名是否已存在
  const { data: existing } = await supabase
    .from('yibao_rule_versions')
    .select('id')
    .eq('version_name', version_name)
    .single();

  if (existing) {
    throw new Error(`Version ${version_name} already exists`);
  }

  // 调用存储过程创建快照
  const { data, error } = await supabase.rpc('create_rule_snapshot', {
    p_version_name: version_name,
    p_description: description,
    p_created_by: created_by
  });

  if (error) throw error;

  return {
    version_id: data,
    version_name,
    description,
    created_at: new Date().toISOString(),
    message: 'Snapshot created successfully'
  };
}

// 回滚到指定版本
async function rollbackToVersion(supabase: any, params: any) {
  const { version_id, deployed_by, deployment_notes } = params;
  
  if (!version_id) {
    throw new Error('version_id is required');
  }

  // 获取目标版本数据
  const { data: version, error: versionError } = await supabase
    .from('yibao_rule_versions')
    .select('*')
    .eq('id', version_id)
    .single();

  if (versionError || !version) {
    throw new Error('Version not found');
  }

  // 获取当前活跃版本
  const { data: currentVersion } = await supabase.rpc('get_active_rule_version');

  try {
    // 开始事务回滚
    const startTime = Date.now();

    // 1. 清空当前规则表
    await supabase.from('yibao_rule_triggers').delete().neq('id', 0);
    await supabase.from('yibao_rule_actions').delete().neq('id', 0);
    await supabase.from('yibao_rule_conditions').delete().neq('id', 0);
    await supabase.from('yibao_rules').delete().neq('id', 0);

    // 2. 恢复快照数据
    if (version.rules_snapshot && version.rules_snapshot.length > 0) {
      const { error: rulesError } = await supabase
        .from('yibao_rules')
        .insert(version.rules_snapshot);
      if (rulesError) throw rulesError;
    }

    if (version.conditions_snapshot && version.conditions_snapshot.length > 0) {
      const { error: conditionsError } = await supabase
        .from('yibao_rule_conditions')
        .insert(version.conditions_snapshot);
      if (conditionsError) throw conditionsError;
    }

    if (version.actions_snapshot && version.actions_snapshot.length > 0) {
      const { error: actionsError } = await supabase
        .from('yibao_rule_actions')
        .insert(version.actions_snapshot);
      if (actionsError) throw actionsError;
    }

    if (version.triggers_snapshot && version.triggers_snapshot.length > 0) {
      const { error: triggersError } = await supabase
        .from('yibao_rule_triggers')
        .insert(version.triggers_snapshot);
      if (triggersError) throw triggersError;
    }

    // 3. 更新版本状态
    await supabase
      .from('yibao_rule_versions')
      .update({ is_active: false })
      .neq('id', 0);

    await supabase
      .from('yibao_rule_versions')
      .update({ is_active: true })
      .eq('id', version_id);

    // 4. 记录部署历史
    const deploymentDuration = Date.now() - startTime;
    await supabase
      .from('yibao_version_deployments')
      .insert({
        version_id,
        deployed_by,
        rollback_from_version_id: currentVersion?.id,
        deployment_status: 'success',
        deployment_notes,
        deployment_duration_ms: deploymentDuration,
        affected_rules_count: version.total_rules
      });

    return {
      success: true,
      version_id,
      version_name: version.version_name,
      rollback_from: currentVersion?.version_name,
      deployment_duration_ms: deploymentDuration,
      affected_rules_count: version.total_rules,
      message: 'Rollback completed successfully'
    };

  } catch (error) {
    // 记录失败的部署
    await supabase
      .from('yibao_version_deployments')
      .insert({
        version_id,
        deployed_by,
        rollback_from_version_id: currentVersion?.id,
        deployment_status: 'failed',
        deployment_notes: `Rollback failed: ${error.message}`
      });

    throw error;
  }
}

// 比较两个版本
async function compareVersions(supabase: any, params: any) {
  const { version_id_1, version_id_2 } = params;
  
  if (!version_id_1 || !version_id_2) {
    throw new Error('Both version_id_1 and version_id_2 are required');
  }

  const { data: versions, error } = await supabase
    .from('yibao_rule_versions')
    .select('id, version_name, rules_snapshot, total_rules, active_rules, created_at')
    .in('id', [version_id_1, version_id_2]);

  if (error || !versions || versions.length !== 2) {
    throw new Error('Failed to fetch versions for comparison');
  }

  const [v1, v2] = versions.sort((a, b) => a.id - b.id);

  // 简化的差异分析
  const v1Rules = new Map(v1.rules_snapshot.map((r: any) => [r.code, r]));
  const v2Rules = new Map(v2.rules_snapshot.map((r: any) => [r.code, r]));

  const added = [];
  const removed = [];
  const modified = [];

  // 检查新增和修改
  for (const [code, rule] of v2Rules) {
    if (!v1Rules.has(code)) {
      added.push({ code, name: rule.name, type: 'added' });
    } else {
      const oldRule = v1Rules.get(code);
      if (JSON.stringify(oldRule) !== JSON.stringify(rule)) {
        modified.push({ 
          code, 
          name: rule.name, 
          type: 'modified',
          changes: {
            enabled: oldRule.enabled !== rule.enabled,
            severity: oldRule.severity !== rule.severity,
            updated_at: oldRule.updated_at !== rule.updated_at
          }
        });
      }
    }
  }

  // 检查删除
  for (const [code, rule] of v1Rules) {
    if (!v2Rules.has(code)) {
      removed.push({ code, name: rule.name, type: 'removed' });
    }
  }

  return {
    version_1: {
      id: v1.id,
      name: v1.version_name,
      total_rules: v1.total_rules,
      active_rules: v1.active_rules,
      created_at: v1.created_at
    },
    version_2: {
      id: v2.id,
      name: v2.version_name,
      total_rules: v2.total_rules,
      active_rules: v2.active_rules,
      created_at: v2.created_at
    },
    differences: {
      summary: {
        added_count: added.length,
        removed_count: removed.length,
        modified_count: modified.length,
        total_changes: added.length + removed.length + modified.length
      },
      details: {
        added,
        removed,
        modified
      }
    }
  };
}

// 获取版本列表
async function getVersions(supabase: any, params: any) {
  const { limit = 20, offset = 0 } = params;

  const { data: versions, error, count } = await supabase
    .from('yibao_rule_versions')
    .select('id, version_name, description, created_at, is_active, total_rules, active_rules, created_by', { count: 'exact' })
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) throw error;

  return {
    versions: versions || [],
    total_count: count || 0,
    limit,
    offset
  };
}

export async function handler(req: Request): Promise<Response> {
  try {
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const url = new URL(req.url);
    const action = url.pathname.split('/').pop();
    const supabase = getSupabase();

    let result;
    
    if (req.method === 'POST') {
      const body = await req.json();
      
      switch (action) {
        case 'create-snapshot':
          result = await createSnapshot(supabase, body);
          break;
        case 'rollback':
          result = await rollbackToVersion(supabase, body);
          break;
        case 'compare':
          result = await compareVersions(supabase, body);
          break;
        default:
          return Response.json({ error: 'Invalid action' }, { status: 400, headers: corsHeaders });
      }
    } else if (req.method === 'GET') {
      const params = Object.fromEntries(url.searchParams);
      
      switch (action) {
        case 'versions':
          result = await getVersions(supabase, params);
          break;
        case 'compare':
          result = await compareVersions(supabase, params);
          break;
        default:
          return Response.json({ error: 'Invalid action' }, { status: 400, headers: corsHeaders });
      }
    } else {
      return Response.json({ error: 'Method not allowed' }, { status: 405, headers: corsHeaders });
    }

    return Response.json(result, { headers: corsHeaders });

  } catch (error) {
    console.error('Version manager error:', error);
    return Response.json({ 
      error: error.message || 'Internal server error',
      timestamp: new Date().toISOString()
    }, { 
      status: 500, 
      headers: corsHeaders 
    });
  }
}

Deno.serve(handler);
