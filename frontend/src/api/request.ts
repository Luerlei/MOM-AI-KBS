import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { message } from 'ant-design-vue'
import type { ApiResponse } from '@/types'

// 防止 401 时重复跳转
let isRedirecting = false

/**
 * Axios 实例
 */
const service: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

/**
 * 请求拦截器
 */
service.interceptors.request.use(
  (config) => {
    // 添加 token（如需要）
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

/**
 * 响应拦截器：统一处理 {code, message, data} 格式
 */
service.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data
    // 文件流或非标准响应直接返回
    if (response.config.responseType === 'blob' || res instanceof Blob) {
      return response as unknown as AxiosResponse
    }
    // 标准响应
    if (res.code === undefined) {
      return res as unknown as AxiosResponse
    }
    if (res.code !== 0) {
      message.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || 'Error'))
    }
    return res as unknown as AxiosResponse
  },
  (error) => {
    const status = error.response?.status
    const msg = error.response?.data?.message || error.message || '网络异常'
    if (status === 401) {
      // 清除 token，跳转登录页（防重复跳转）
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      if (!isRedirecting) {
        isRedirecting = true
        message.error('登录已过期，请重新登录')
        import('@/router').then(({ default: router }) => {
          router.replace({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
          isRedirecting = false
        })
      }
    } else if (status === 403) {
      message.error('禁止访问')
    } else if (status === 404) {
      message.error('请求的资源不存在')
    } else if (status && status >= 500) {
      message.error('服务器错误，请稍后重试')
    } else {
      message.error(msg)
    }
    return Promise.reject(error)
  }
)

/**
 * 封装 GET 请求
 */
export async function get<T = unknown>(
  url: string,
  params?: object,
  config?: AxiosRequestConfig
): Promise<T> {
  const res = await service.get<unknown, ApiResponse<T>>(url, {
    params,
    ...config
  })
  return res.data
}

/**
 * 封装 POST 请求
 */
export async function post<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const res = await service.post<unknown, ApiResponse<T>>(url, data, config)
  return res.data
}

/**
 * 封装 PUT 请求
 */
export async function put<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const res = await service.put<unknown, ApiResponse<T>>(url, data, config)
  return res.data
}

/**
 * 封装 DELETE 请求
 */
export async function del<T = unknown>(
  url: string,
  params?: object,
  config?: AxiosRequestConfig
): Promise<T> {
  const res = await service.delete<unknown, ApiResponse<T>>(url, {
    params,
    ...config
  })
  return res.data
}

/**
 * 用于上传文件的 axios 实例方法
 */
export async function upload<T = unknown>(
  url: string,
  formData: FormData,
  config?: AxiosRequestConfig
): Promise<T> {
  const res = await service.post<unknown, ApiResponse<T>>(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    ...config
  })
  return res.data
}

export default service
