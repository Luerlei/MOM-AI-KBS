import { get, post } from './request'

export interface LoginResult {
  token: string
  username: string
}

export interface AuthStatus {
  auth_enabled: boolean
}

/** 获取认证开关状态 */
export async function getAuthStatus(): Promise<AuthStatus> {
  return get('/auth/status')
}

/** 用户登录 */
export async function login(username: string, password: string): Promise<LoginResult> {
  return post('/auth/login', { username, password })
}

/** 获取当前用户信息 */
export async function getMe(): Promise<{ username: string }> {
  return get('/auth/me')
}
