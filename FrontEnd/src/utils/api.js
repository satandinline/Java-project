/**
 * 统一的API调用工具函数
 * 提供统一的错误处理和响应格式处理
 */

/**
 * 统一的API请求函数
 * @param {string} url - API地址
 * @param {object} options - fetch选项
 * @returns {Promise} 响应数据
 */
export async function apiRequest(url, options = {}) {
  // 获取用户信息
  const userInfoStr = sessionStorage.getItem('userInfo') || localStorage.getItem('userInfo');
  let userInfo = null;
  if (userInfoStr) {
    try {
      userInfo = JSON.parse(userInfoStr);
    } catch (e) {
    }
  }

  // 设置默认headers
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  // 如果有用户ID，添加到headers
  if (userInfo && userInfo.id) {
    defaultHeaders['X-User-Id'] = userInfo.id.toString();
  }

  // 合并headers
  const headers = {
    ...defaultHeaders,
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    // 检查响应状态
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: '请求失败' }));
      throw new Error(errorData.message || `HTTP ${response.status}`);
    }

    // 解析JSON响应
    const data = await response.json();

    // 检查业务逻辑错误
    if (!data.success) {
      throw new Error(data.message || '操作失败');
    }

    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * GET请求
 */
export async function apiGet(url, params = {}) {
  const queryString = new URLSearchParams(params).toString();
  const fullUrl = queryString ? `${url}?${queryString}` : url;
  return apiRequest(fullUrl, { method: 'GET' });
}

/**
 * POST请求
 */
export async function apiPost(url, data = {}) {
  return apiRequest(url, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * PUT请求
 */
export async function apiPut(url, data = {}) {
  return apiRequest(url, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * DELETE请求
 */
export async function apiDelete(url) {
  return apiRequest(url, { method: 'DELETE' });
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser() {
  const userInfoStr = sessionStorage.getItem('userInfo') || localStorage.getItem('userInfo');
  if (userInfoStr) {
    try {
      return JSON.parse(userInfoStr);
    } catch (e) {
      return null;
    }
  }
  return null;
}

/**
 * 文件上传请求
 */
export async function apiUpload(url, formData) {
  const userInfoStr = sessionStorage.getItem('userInfo') || localStorage.getItem('userInfo');
  let userInfo = null;
  if (userInfoStr) {
    try {
      userInfo = JSON.parse(userInfoStr);
    } catch (e) {
    }
  }

  const headers = {};
  if (userInfo && userInfo.id) {
    headers['X-User-Id'] = userInfo.id.toString();
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: '上传失败' }));
      throw new Error(errorData.message || `HTTP ${response.status}`);
    }

    const data = await response.json();
    if (!data.success) {
      throw new Error(data.message || '上传失败');
    }

    return data;
  } catch (error) {
    throw error;
  }
}

