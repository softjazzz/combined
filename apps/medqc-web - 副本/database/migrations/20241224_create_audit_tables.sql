-- 人工审核模块数据库表结构
-- 创建时间: 2024-12-24

-- 1. 审核任务表
CREATE TABLE qc_audit_tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_code VARCHAR(50) UNIQUE NOT NULL,
    task_name VARCHAR(200) NOT NULL,
    task_type VARCHAR(30) NOT NULL CHECK (task_type IN ('routine', 'special', 'spot_check', 'complaint_driven')),
    
    -- 审核配置
    audit_level VARCHAR(20) NOT NULL CHECK (audit_level IN ('department', 'hospital', 'expert')),
    audit_scope JSONB NOT NULL DEFAULT '{}', -- 科室范围、病历类型等
    sampling_config JSONB NOT NULL DEFAULT '{}', -- 抽样配置
    
    -- 任务状态
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    progress_percentage DECIMAL(5,2) DEFAULT 0,
    
    -- 时间管理
    planned_start_date DATE NOT NULL,
    planned_end_date DATE NOT NULL,
    actual_start_date TIMESTAMP WITH TIME ZONE,
    actual_end_date TIMESTAMP WITH TIME ZONE,
    
    -- 分配信息
    created_by UUID NOT NULL REFERENCES auth.users(id),
    assigned_reviewers JSONB DEFAULT '[]', -- 分配的审核员列表
    
    -- 统计信息
    total_records INTEGER DEFAULT 0,
    completed_records INTEGER DEFAULT 0,
    defect_rate DECIMAL(5,2),
    
    -- 元数据
    description TEXT,
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    INDEX idx_audit_tasks_status (status, created_at),
    INDEX idx_audit_tasks_level (audit_level, status),
    INDEX idx_audit_tasks_assignee USING GIN (assigned_reviewers)
);

-- 2. 审核任务明细表
CREATE TABLE qc_audit_task_items (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES qc_audit_tasks(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    medical_record_id UUID NOT NULL,
    
    -- 病历基本信息
    patient_name VARCHAR(100),
    admission_date DATE,
    discharge_date DATE,
    department_id UUID,
    department_name VARCHAR(100),
    
    -- 风险等级和复杂度
    risk_level VARCHAR(10) CHECK (risk_level IN ('A', 'B', 'C')), -- A:高风险 B:中风险 C:低风险
    complexity_score INTEGER DEFAULT 0,
    
    -- 审核状态
    audit_status VARCHAR(20) DEFAULT 'pending' CHECK (audit_status IN ('pending', 'in_review', 'completed', 'appealed', 'cancelled')),
    assigned_reviewer_id UUID REFERENCES auth.users(id),
    
    -- 审核结果汇总
    overall_score DECIMAL(5,2),
    defect_count INTEGER DEFAULT 0,
    has_critical_defects BOOLEAN DEFAULT FALSE,
    
    -- 时间记录
    assigned_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- 备注
    reviewer_notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    INDEX idx_task_items_task (task_id, audit_status),
    INDEX idx_task_items_reviewer (assigned_reviewer_id, audit_status),
    INDEX idx_task_items_patient (patient_id),
    INDEX idx_task_items_risk (risk_level, complexity_score)
);

-- 3. 多级审核结果表
CREATE TABLE qc_audit_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_item_id UUID NOT NULL REFERENCES qc_audit_task_items(id) ON DELETE CASCADE,
    audit_level VARCHAR(20) NOT NULL CHECK (audit_level IN ('department', 'hospital', 'expert')),
    reviewer_id UUID NOT NULL REFERENCES auth.users(id),
    reviewer_name VARCHAR(100),
    
    -- 审核结果
    audit_score DECIMAL(5,2) NOT NULL,
    audit_conclusion TEXT,
    defects_found JSONB DEFAULT '[]', -- 发现的缺陷列表
    
    -- 状态管理
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'modified')),
    is_final BOOLEAN DEFAULT FALSE,
    
    -- 审核时间和效率
    review_duration INTEGER, -- 审核耗时（分钟）
    submitted_at TIMESTAMP WITH TIME ZONE,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- 修改记录（上级修改下级结果）
    modified_by UUID REFERENCES auth.users(id),
    modification_reason TEXT,
    original_score DECIMAL(5,2),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 约束：确保每个任务项的每个级别只有一个最终结果
    UNIQUE(task_item_id, audit_level, is_final) WHERE is_final = TRUE,
    
    -- 索引
    INDEX idx_audit_results_task_item (task_item_id, audit_level),
    INDEX idx_audit_results_reviewer (reviewer_id, status),
    INDEX idx_audit_results_level (audit_level, is_final)
);

-- 4. 质控缺陷表
CREATE TABLE qc_defects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    audit_result_id UUID NOT NULL REFERENCES qc_audit_results(id) ON DELETE CASCADE,
    task_item_id UUID NOT NULL REFERENCES qc_audit_task_items(id) ON DELETE CASCADE,
    
    -- 缺陷基本信息
    defect_code VARCHAR(50),
    defect_type VARCHAR(50) NOT NULL,
    defect_category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor')),
    
    -- 缺陷描述
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(200), -- 缺陷位置
    evidence TEXT, -- 支持证据
    
    -- 整改要求
    rectification_requirement TEXT,
    rectification_suggestion TEXT,
    estimated_rectification_time INTEGER, -- 预计整改时间（分钟）
    
    -- 状态管理
    status VARCHAR(20) DEFAULT 'identified' CHECK (status IN (
        'identified', 'rectification_required', 'rectification_submitted', 
        'rectification_approved', 'rectification_rejected', 'appealed', 
        'appeal_approved', 'appeal_rejected', 'closed', 'dismissed'
    )),
    
    -- 评分影响
    score_deduction DECIMAL(5,2) NOT NULL DEFAULT 0,
    
    -- AI辅助标识
    ai_assisted BOOLEAN DEFAULT FALSE,
    ai_confidence DECIMAL(5,2),
    
    -- 时间戳
    identified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    rectification_deadline TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    INDEX idx_defects_task_item (task_item_id, status),
    INDEX idx_defects_severity (severity, status),
    INDEX idx_defects_type (defect_type, defect_category),
    INDEX idx_defects_ai (ai_assisted, ai_confidence)
);

-- 5. 消息通知表
CREATE TABLE qc_notifications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- 消息基本信息
    type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'delivered', 'read', 'processed', 'expired')),
    
    -- 发送方信息
    sender_id UUID REFERENCES auth.users(id),
    sender_name VARCHAR(100),
    sender_role VARCHAR(50),
    
    -- 接收方信息
    recipient_id UUID NOT NULL REFERENCES auth.users(id),
    recipient_type VARCHAR(20) NOT NULL CHECK (recipient_type IN ('clinician', 'reviewer', 'admin')),
    
    -- 消息内容
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    summary VARCHAR(500),
    
    -- 关联数据
    related_data JSONB DEFAULT '{}',
    
    -- 行为配置
    actions JSONB DEFAULT '[]',
    auto_expire BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- 状态时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- 分发信息
    distribution_channel VARCHAR(50),
    delivery_attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    
    -- 索引
    INDEX idx_notifications_recipient_status (recipient_id, status, created_at DESC),
    INDEX idx_notifications_type_priority (type, priority, created_at DESC),
    INDEX idx_notifications_expires (expires_at) WHERE expires_at IS NOT NULL,
    INDEX idx_notifications_related_data USING GIN (related_data)
);

-- 6. 消息分发日志表
CREATE TABLE message_distribution_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    message_id UUID NOT NULL REFERENCES qc_notifications(id) ON DELETE CASCADE,
    
    -- 分发信息
    distribution_channel VARCHAR(50) NOT NULL,
    attempt_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'timeout', 'retry')),
    
    -- 性能指标
    response_time INTEGER, -- 毫秒
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- 时间戳
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_distribution_logs_message (message_id, attempted_at),
    INDEX idx_distribution_logs_status (status, attempted_at)
);

-- 7. 用户通知偏好表
CREATE TABLE user_notification_preferences (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- 通道偏好
    preferred_channel VARCHAR(50) DEFAULT 'realtime',
    enable_browser_notifications BOOLEAN DEFAULT TRUE,
    enable_email_notifications BOOLEAN DEFAULT TRUE,
    enable_sms_notifications BOOLEAN DEFAULT FALSE,
    
    -- 消息类型偏好
    message_type_preferences JSONB DEFAULT '{}',
    
    -- 免打扰设置
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    quiet_days INTEGER[], -- 0=周日, 1=周一, ...
    
    -- 批量设置
    enable_batch_digest BOOLEAN DEFAULT FALSE,
    batch_digest_frequency VARCHAR(20) DEFAULT 'daily', -- hourly, daily, weekly
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id)
);

-- 8. 缺陷状态变更日志表
CREATE TABLE defect_status_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    defect_id UUID NOT NULL REFERENCES qc_defects(id) ON DELETE CASCADE,
    
    -- 状态变更信息
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    change_reason TEXT,
    
    -- 操作人信息
    changed_by UUID NOT NULL REFERENCES auth.users(id),
    changed_by_name VARCHAR(100),
    changed_by_role VARCHAR(50),
    
    -- 附加数据
    additional_data JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_defect_status_logs_defect (defect_id, created_at),
    INDEX idx_defect_status_logs_user (changed_by, created_at)
);

-- 创建更新时间戳的触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为相关表添加更新时间戳触发器
CREATE TRIGGER update_qc_audit_tasks_updated_at BEFORE UPDATE ON qc_audit_tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_qc_audit_task_items_updated_at BEFORE UPDATE ON qc_audit_task_items FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_qc_audit_results_updated_at BEFORE UPDATE ON qc_audit_results FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_qc_defects_updated_at BEFORE UPDATE ON qc_defects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_qc_notifications_updated_at BEFORE UPDATE ON qc_notifications FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_notification_preferences_updated_at BEFORE UPDATE ON user_notification_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
