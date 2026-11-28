export class ApiError extends Error {
  constructor(status, error = {}) {
    super(error.message || 'Не удалось выполнить запрос')
    this.status = status
    this.code = error.code
    this.fields = error.fields || []
    this.details = error.details || {}
  }
}

let refreshing
let authGeneration = 0
export function queryString(values = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== '' && item != null) query.append(key, String(item))
    }
  }
  return query.toString()
}

export async function api(path, { method = 'GET', body, query, signal } = {}) {
  const generation = authGeneration
  const options = { method, credentials: 'include', signal }
  if (body !== undefined) {
    options.body = body instanceof FormData ? body : JSON.stringify(body)
    if (!(body instanceof FormData)) options.headers = { 'Content-Type': 'application/json' }
  }
  const url = `/api/v1${path}${query ? `?${queryString(query)}` : ''}`
  const send = async () => {
    try {
      return await fetch(url, options)
    } catch (error) {
      if (error.name === 'AbortError') throw error
      throw new ApiError(0, { message: 'Нет соединения с сервером. Повторите запрос.' })
    }
  }
  let response = await send()
  if (response.status === 401 && !path.startsWith('/auth/')) {
    if (generation === authGeneration) {
      refreshing ??= fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
        .then((result) => {
          if (result.ok) authGeneration++
          return result
        })
        .finally(() => {
          refreshing = null
        })
      let refresh
      try {
        refresh = await refreshing
      } catch {
        throw new ApiError(0, { message: 'Нет соединения с сервером. Повторите запрос.' })
      }
      if (!refresh.ok) {
        if (refresh.status === 401) window.dispatchEvent(new Event('auth-expired'))
        throw new ApiError(refresh.status, {
          message:
            refresh.status === 401
              ? 'Войдите по коду из письма'
              : 'Не удалось продлить вход. Повторите запрос.',
        })
      }
    }
    response = await send()
    if (response.status === 401) window.dispatchEvent(new Event('auth-expired'))
  }
  if (response.status === 204) return null
  const result = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, result?.error)
  return result
}

export const workPath = (work) =>
  work.scope === 'private' ? `/me/private-works/${work.id}` : `/works/${work.id}`
export const workLink = (work) => `/works/${work.scope || 'catalog'}/${work.id}`
