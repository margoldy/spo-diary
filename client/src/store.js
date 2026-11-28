import { reactive } from 'vue'
import { api } from './api'

export const state = reactive({
  user: null,
  ready: false,
  types: [],
  genres: [],
  tags: [],
  revision: 0,
  toast: '',
})
export const statuses = {
  planned: 'В планах',
  in_progress: 'В процессе',
  completed: 'Завершено',
  dropped: 'Брошено',
}
export const typeName = (code) => state.types.find((type) => type.code === code)?.name || code
export const authorLabel = (type) =>
  ['movie', 'series'].includes(type)
    ? 'Режиссёр'
    : ['anime', 'animated_movie', 'animated_series', 'visual_novel', 'other'].includes(type)
      ? 'Создатели'
      : ['manga', 'manhwa', 'manhua', 'comic'].includes(type)
        ? 'Авторы'
        : 'Автор'
let toastTimer
export function notify(message) {
  state.toast = message
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (state.toast = ''), 4500)
}
export function changed(message) {
  state.revision++
  if (message) notify(message)
}
export async function loadReferences() {
  const [types, genres, tags] = await Promise.all([
    api('/types'),
    api('/genres'),
    api('/tags', { query: { limit: 100 } }),
  ])
  const allTags = [...tags.items]
  while (allTags.length < tags.total) {
    const next = await api('/tags', { query: { limit: 100, offset: allTags.length } })
    if (!next.items.length) break
    allTags.push(...next.items)
  }
  state.types = types.items
  state.genres = genres.items
  state.tags = allTags
}
export async function bootstrap() {
  try {
    state.user = await api('/me')
    await loadReferences()
  } finally {
    state.ready = true
  }
}
