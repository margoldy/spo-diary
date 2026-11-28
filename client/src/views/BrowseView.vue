<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Search,
  SlidersHorizontal,
  Plus,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  EyeOff,
  BookOpen,
  X,
} from '@lucide/vue'
import { api, workPath, workLink } from '../api'
import { state, changed, typeName } from '../store'
import WorkCard from '../components/WorkCard.vue'
import FilterModal from '../components/FilterModal.vue'
import EntryModal from '../components/EntryModal.vue'
import PrivateModal from '../components/PrivateModal.vue'
import ErrorBox from '../components/ErrorBox.vue'
const props = defineProps({ mode: String })
const route = useRoute(),
  router = useRouter()
const result = ref({ items: [], total: 0 }),
  loading = ref(true),
  error = ref(null),
  actionError = ref(null),
  source = ref(null),
  filterOpen = ref(false),
  addWork = ref(null),
  privateOpen = ref(false),
  actionBusy = ref(false)
const limit = 12
const plural = new Intl.PluralRules('ru')
const totalLabel = computed(
  () =>
    `${result.value.total} ${{ one: 'произведение', few: 'произведения', many: 'произведений', other: 'произведения' }[plural.select(result.value.total)]}`,
)
const array = (value) => (!value ? [] : Array.isArray(value) ? value : [value])
const defaultSort =
  props.mode === 'library' ? 'added_desc' : props.mode === 'recommendations' ? 'relevance' : 'title_asc'
const filters = computed(() => ({
  q: String(route.query.q || ''),
  types: array(route.query.types),
  genre_ids: array(route.query.genre_ids),
  statuses: array(route.query.statuses),
  scope: route.query.scope || '',
  tag_ids: array(route.query.tag_ids),
  exclude_tag_ids: array(route.query.exclude_tag_ids),
  sort: route.query.sort || defaultSort,
}))
const search = ref(filters.value.q)
const offset = computed(() => Math.max(0, parseInt(route.query.offset) || 0))
const countFilters = computed(
  () =>
    filters.value.types.length +
    filters.value.genre_ids.length +
    filters.value.statuses.length +
    filters.value.tag_ids.length +
    filters.value.exclude_tag_ids.length +
    Number(!!filters.value.scope),
)
const title = computed(
  () =>
    ({
      catalog: 'Каталог',
      library: 'Моя библиотека',
      recommendations: 'Рекомендации',
      hidden: 'Скрытые произведения',
      similar: 'Похожие произведения',
    })[props.mode],
)
const sorts = computed(() =>
  props.mode === 'library'
    ? [
        ['added_desc', 'Сначала новые'],
        ['title_asc', 'По названию'],
        ['rating_desc', 'По моей оценке'],
      ]
    : [
        ...(props.mode === 'recommendations' ? [['relevance', 'По соответствию']] : []),
        ['title_asc', 'По названию'],
        ['year_desc', 'По году выпуска'],
      ],
)
const commonTypes = ['anime', 'book', 'manga', 'manhwa', 'light_novel', 'movie', 'series']
let controller,
  requestId = 0,
  searchTimer
function updateQuery(values) {
  const query = { ...route.query, ...values }
  for (const key of Object.keys(query))
    if (query[key] === '' || query[key] == null || (Array.isArray(query[key]) && !query[key].length))
      delete query[key]
  router.replace({ query })
}
function applyFilters(values) {
  updateQuery({ ...values, offset: undefined })
}
function toggleType(code) {
  updateQuery({
    types: code
      ? filters.value.types.includes(code)
        ? filters.value.types.filter((t) => t !== code)
        : [...filters.value.types, code]
      : [],
    offset: undefined,
  })
}
function submitSearch() {
  clearTimeout(searchTimer)
  updateQuery({ q: search.value.trim(), offset: undefined })
}
function clearSearch() {
  search.value = ''
  submitSearch()
}
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(submitSearch, 350)
})
async function load() {
  controller?.abort()
  controller = new AbortController()
  const id = ++requestId
  loading.value = true
  error.value = null
  let path,
    query = { limit, offset: offset.value }
  if (props.mode === 'hidden') path = '/me/hidden'
  else {
    query = { ...query, q: filters.value.q, types: filters.value.types, genre_ids: filters.value.genre_ids }
    if (props.mode === 'similar')
      path = `${workPath({ id: route.params.id, scope: route.params.scope })}/similar`
    else {
      query.sort = filters.value.sort
      if (props.mode === 'library') {
        path = '/me/library'
        query.statuses = filters.value.statuses
        query.scope = filters.value.scope
      } else {
        path = props.mode === 'catalog' ? '/works' : '/me/recommendations'
        query.tag_ids = filters.value.tag_ids
        query.exclude_tag_ids = filters.value.exclude_tag_ids
      }
    }
  }
  try {
    const data = await api(path, { query, signal: controller.signal })
    if (id !== requestId) return
    result.value = data
    if (offset.value > 0 && !data.items.length)
      updateQuery({ offset: Math.max(0, Math.ceil(data.total / limit) - 1) * limit || undefined })
    if (props.mode === 'similar' && !source.value)
      source.value = (
        await api(workPath({ id: route.params.id, scope: route.params.scope }), { signal: controller.signal })
      ).work
  } catch (e) {
    if (e.name !== 'AbortError' && id === requestId) error.value = e
  } finally {
    if (id === requestId) loading.value = false
  }
}
watch(
  () => route.query,
  () => {
    search.value = filters.value.q
    load()
  },
  { immediate: true },
)
watch(() => state.revision, load)
onBeforeUnmount(() => {
  controller?.abort()
  clearTimeout(searchTimer)
})
async function hide(work, restore = false) {
  if (actionBusy.value) return
  actionBusy.value = true
  actionError.value = null
  try {
    await api(`/me/hidden/${work.id}`, { method: restore ? 'DELETE' : 'PUT' })
    changed(restore ? 'Произведение возвращено в рекомендации' : 'Рекомендация скрыта')
  } catch (e) {
    actionError.value = e
  } finally {
    actionBusy.value = false
  }
}
const cards = computed(() =>
  result.value.items.map((item) => ({
    work: item.work || item,
    entry: props.mode === 'library' ? item : item.library || null,
    reason: item.reason,
  })),
)
</script>
<template>
  <main class="page browse-page">
    <RouterLink v-if="mode === 'hidden'" to="/recommendations" class="back-link">
      <ArrowLeft :size="19" />
      К рекомендациям
    </RouterLink>
    <RouterLink v-if="mode === 'similar' && source" :to="workLink(source)" class="back-link">
      <ArrowLeft :size="19" />
      {{ source.title }}
    </RouterLink>
    <h1>{{ title }}</h1>
    <p v-if="mode === 'similar' && source" class="page-subtitle">Похожее на «{{ source.title }}»</p>
    <template v-if="mode !== 'hidden'">
      <form class="search-row" @submit.prevent="submitSearch">
        <div class="search-input">
          <Search :size="18" />
          <input
            v-model="search"
            maxlength="200"
            placeholder="Поиск по названию…"
            aria-label="Поиск по названию"
          />
          <button
            v-if="search"
            type="button"
            class="icon-button"
            aria-label="Очистить поиск"
            @click="clearSearch"
          >
            <X :size="16" />
          </button>
        </div>
        <button
          type="button"
          class="button outline filters-button"
          aria-label="Фильтры"
          @click="filterOpen = true"
        >
          <SlidersHorizontal :size="17" />
          <span>Фильтры</span>
          <span v-if="countFilters" class="filter-count">{{ countFilters }}</span>
        </button>
      </form>
      <div class="type-tabs" aria-label="Тип произведения">
        <button class="chip" :class="{ active: !filters.types.length }" @click="toggleType(null)">Все</button>
        <button
          v-for="code in commonTypes"
          :key="code"
          class="chip"
          :class="{ active: filters.types.includes(code) }"
          :aria-pressed="filters.types.includes(code)"
          @click="toggleType(code)"
        >
          {{ typeName(code) }}
        </button>
        <button class="chip more-types" @click="filterOpen = true">Ещё</button>
      </div>
    </template>
    <div class="list-toolbar">
      <span class="muted">
        {{ loading ? 'Загрузка…' : totalLabel }}
        <span v-if="mode === 'recommendations' && result.mode === 'general'">· Общая подборка</span>
      </span>
      <div class="toolbar-right">
        <RouterLink
          v-if="mode === 'recommendations'"
          to="/hidden"
          class="text-button muted"
          title="Скрытые произведения"
        >
          <EyeOff :size="16" />
          <span>Скрытые</span>
        </RouterLink>
        <select
          v-if="mode !== 'hidden' && mode !== 'similar'"
          :value="filters.sort"
          aria-label="Сортировка"
          class="sort-select"
          @change="updateQuery({ sort: $event.target.value, offset: undefined })"
        >
          <option v-for="[value, name] in sorts" :key="value" :value="value">{{ name }}</option>
        </select>
      </div>
    </div>
    <div v-if="countFilters" class="active-filter-row">
      <span>Применено фильтров: {{ countFilters }}</span>
      <button
        class="text-button"
        @click="
          applyFilters({
            types: [],
            genre_ids: [],
            statuses: [],
            scope: '',
            tag_ids: [],
            exclude_tag_ids: [],
          })
        "
      >
        Сбросить
      </button>
    </div>
    <ErrorBox :error="actionError" />
    <div v-if="loading" class="cards-grid" aria-busy="true" aria-label="Загрузка произведений">
      <div class="skeleton-card" v-for="n in 6" :key="n">
        <div></div>
        <span></span>
      </div>
    </div>
    <div v-else-if="error" class="empty-state">
      <ErrorBox :error="error" />
      <button class="button outline" @click="load">Повторить</button>
    </div>
    <template v-else-if="cards.length">
      <div class="cards-grid">
        <WorkCard
          v-for="card in cards"
          :key="card.work.id"
          v-bind="card"
          :mode="mode"
          @add="addWork = $event"
          @hide="hide"
          @restore="hide($event, true)"
        />
      </div>
      <nav v-if="result.total > limit" class="pagination" aria-label="Страницы">
        <button
          class="button outline small"
          :disabled="offset === 0"
          @click="updateQuery({ offset: Math.max(0, offset - limit) || undefined })"
        >
          <ChevronLeft :size="16" />
          Назад
        </button>
        <span>{{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(result.total / limit) }}</span>
        <button
          class="button outline small"
          :disabled="offset + limit >= result.total"
          @click="updateQuery({ offset: offset + limit })"
        >
          Далее
          <ChevronRight :size="16" />
        </button>
      </nav>
    </template>
    <div v-else class="empty-state">
      <BookOpen :size="38" />
      <h2>
        {{
          mode === 'library' && !search && !countFilters
            ? 'В библиотеке пока пусто'
            : mode === 'hidden'
              ? 'Нет скрытых произведений'
              : 'Ничего не найдено'
        }}
      </h2>
      <p v-if="search || countFilters">Попробуйте изменить запрос или фильтры.</p>
      <p v-else-if="mode === 'similar'">Пока недостаточно общих тегов и жанров.</p>
      <p v-else-if="mode === 'recommendations'">
        Добавьте оценки и отзывы в библиотеку, чтобы уточнить подборку.
      </p>
      <RouterLink v-if="mode === 'library'" to="/catalog" class="button outline">
        Перейти в каталог
      </RouterLink>
      <button v-if="search || countFilters" class="button outline" @click="router.replace({ query: {} })">
        Сбросить поиск
      </button>
    </div>
    <button
      v-if="mode === 'library' || mode === 'catalog'"
      class="button add-private"
      @click="privateOpen = true"
    >
      <Plus :size="19" />
      Добавить произведение
    </button>
    <FilterModal
      v-if="filterOpen"
      :filters="filters"
      :mode="mode"
      @close="filterOpen = false"
      @apply="applyFilters"
    />
    <EntryModal v-if="addWork" :work="addWork" @close="addWork = null" />
    <PrivateModal
      v-if="privateOpen"
      @close="privateOpen = false"
      @saved="router.push(workLink($event.work))"
    />
  </main>
</template>
