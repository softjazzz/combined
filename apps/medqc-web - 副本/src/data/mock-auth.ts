// @ts-nocheck
/**
 * Mock 认证数据
 * 用于前端开发时模拟后端认证接口
 */

import type { LoginResponse, User } from '@/types'

// 模拟用户数据库
export const mockUsers = [
    {
        id: 'user-001',
        email: 'admin@hospital.com',
        password: 'admin123', // 实际应用中不应明文存储
        display_name: '张医生',
        department: '心内科',
        hospital_id: 'hospital-001',
        roles: ['admin', 'doctor'],
        is_active: true,
        phone: '13800138000',
        avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=admin',
        created_at: '2024-01-01T00:00:00Z',
        last_login: new Date().toISOString()
    },
    {
        id: 'user-002',
        email: 'doctor@hospital.com',
        password: 'doctor123',
        display_name: '李医生',
        department: '呼吸内科',
        hospital_id: 'hospital-001',
        roles: ['doctor'],
        is_active: true,
        phone: '13900139000',
        avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=doctor',
        created_at: '2024-01-15T00:00:00Z',
        last_login: new Date().toISOString()
    },
    {
        id: 'user-003',
        email: 'coder@hospital.com',
        password: 'coder123',
        display_name: '王编码员',
        department: '病案科',
        hospital_id: 'hospital-001',
        roles: ['coder'],
        is_active: true,
        phone: '13700137000',
        avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=coder',
        created_at: '2024-02-01T00:00:00Z',
        last_login: new Date().toISOString()
    },
    {
        id: 'user-004',
        email: 'test@test.com',
        password: '123456',
        display_name: '测试用户',
        department: '测试部门',
        hospital_id: 'hospital-001',
        roles: ['user'],
        is_active: true,
        phone: '13600136000',
        avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=test',
        created_at: '2024-03-01T00:00:00Z',
        last_login: new Date().toISOString()
    }
]

/**
 * 模拟登录
 */
export function mockLogin(email: string, password: string): LoginResponse | null {
    const user = mockUsers.find(u => u.email === email && u.password === password)

    if (!user) {
        return null
    }

    // 生成模拟 token (实际应用中应该是 JWT)
    const accessToken = `mock_access_token_${user.id}_${Date.now()}`
    const refreshToken = `mock_refresh_token_${user.id}_${Date.now()}`

    return {
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: 'Bearer',
        expires_in: 3600,
        user: {
            id: user.id,
            email: user.email,
            display_name: user.display_name,
            department: user.department,
            hospital_id: user.hospital_id,
            roles: user.roles,
            is_active: user.is_active,
            avatar: user.avatar,
            phone: user.phone,
            created_at: user.created_at,
            last_login: user.last_login
        }
    }
}

/**
 * 根据 token 获取用户信息
 */
export function mockGetCurrentUser(token: string): User | null {
    // 从 token 中提取用户 ID
    const match = token.match(/mock_access_token_([^_]+)_/)
    if (!match) {
        return null
    }

    const userId = match[1]
    const user = mockUsers.find(u => u.id === userId)

    if (!user) {
        return null
    }

    return {
        id: user.id,
        email: user.email,
        display_name: user.display_name,
        department: user.department,
        hospital_id: user.hospital_id,
        roles: user.roles,
        is_active: user.is_active,
        avatar: user.avatar,
        phone: user.phone,
        created_at: user.created_at,
        last_login: user.last_login,
        updated_at: new Date().toISOString()
    }
}

/**
 * 模拟注册
 */
export function mockRegister(userData: {
    email: string
    password: string
    display_name: string
    department?: string
    phone?: string
}): User {
    const newUser = {
        id: `user-${Date.now()}`,
        email: userData.email,
        password: userData.password,
        display_name: userData.display_name,
        department: userData.department || '未分配',
        hospital_id: 'hospital-001',
        roles: ['user'],
        is_active: false, // 新注册用户需要审核
        phone: userData.phone || '',
        avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${userData.email}`,
        created_at: new Date().toISOString(),
        last_login: new Date().toISOString()
    }

    mockUsers.push(newUser)

    return {
        id: newUser.id,
        email: newUser.email,
        display_name: newUser.display_name,
        department: newUser.department,
        hospital_id: newUser.hospital_id,
        roles: newUser.roles,
        is_active: newUser.is_active,
        avatar: newUser.avatar,
        phone: newUser.phone,
        created_at: newUser.created_at,
        last_login: newUser.last_login
    }
}

/**
 * 模拟刷新 token
 */
export function mockRefreshToken(refreshToken: string): LoginResponse | null {
    // 从 refresh token 中提取用户 ID
    const match = refreshToken.match(/mock_refresh_token_([^_]+)_/)
    if (!match) {
        return null
    }

    const userId = match[1]
    const user = mockUsers.find(u => u.id === userId)

    if (!user) {
        return null
    }

    // 生成新的 token
    const newAccessToken = `mock_access_token_${user.id}_${Date.now()}`
    const newRefreshToken = `mock_refresh_token_${user.id}_${Date.now()}`

    return {
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
        token_type: 'Bearer',
        expires_in: 3600,
        user: {
            id: user.id,
            email: user.email,
            display_name: user.display_name,
            department: user.department,
            hospital_id: user.hospital_id,
            roles: user.roles,
            is_active: user.is_active,
            avatar: user.avatar,
            phone: user.phone,
            created_at: user.created_at,
            last_login: user.last_login
        }
    }
}

