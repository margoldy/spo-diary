<script setup>
import { computed, reactive, ref } from 'vue'
import Modal from './Modal.vue'
import { state, statuses } from '../store'
const props = defineProps({ filters: Object, mode: String })
const emit = defineEmits(['close', 'apply'])
const draft = reactive(JSON.parse(JSON.stringify(props.filters))),
  search = ref('')
const tags = computed(() =>
  state.tags.filter((t) => t.name.toLowerCase().includes(search.value.toLowerCase())),
)
function toggle(key, value) {
  const list = draft[key],
    i = list.indexOf(value)
  if (i !== -1) list.splice(i, 1)
  else if (list.length < (key.includes('tag_ids') ? 30 : 100)) {
    list.push(value)
    if (key.includes('tag_ids')) {
      const other = key === 'tag_ids' ? 'exclude_tag_ids' : 'tag_ids'
      draft[other] = draft[other].filter((id) => id !== value)
    }
  }
}
function apply() {
  emit('apply', draft)
  emit('close')
}
function reset() {
  Object.assign(draft, {
    types: [],
    genre_ids: [],
    statuses: [],
    tag_ids: [],
    exclude_tag_ids: [],
    scope: '',
  })
}
</script>
<template>
  <Modal title="Фильтры" wide @close="emit('close')">
    <form @submit.prevent="apply">
      <fieldset>
        <legend>Тип произведения</legend>
        <div class="chips">
          <button
            v-for="type in state.types"
            type="button"
            :key="type.code"
            class="chip"
            :class="{ active: draft.types.includes(type.code) }"
            :aria-pressed="draft.types.includes(type.code)"
            @click="toggle('types', type.code)"
          >
            {{ type.name }}
          </button>
        </div>
      </fieldset>
      <fieldset>
        <legend>Жанры</legend>
        <div class="chips">
          <button
            v-for="genre in state.genres"
            type="button"
            :key="genre.id"
            class="chip"
            :class="{ active: draft.genre_ids.includes(genre.id) }"
            :aria-pressed="draft.genre_ids.includes(genre.id)"
            @click="toggle('genre_ids', genre.id)"
          >
            {{ genre.name }}
          </button>
        </div>
      </fieldset>
      <template v-if="mode === 'library'">
        <fieldset>
          <legend>Статус</legend>
          <div class="chips">
            <button
              v-for="(name, code) in statuses"
              type="button"
              :key="code"
              class="chip"
              :class="{ active: draft.statuses.includes(code) }"
              @click="toggle('statuses', code)"
            >
              {{ name }}
            </button>
          </div>
        </fieldset>
        <label>
          Произведения
          <select v-model="draft.scope">
            <option value="">Все</option>
            <option value="catalog">Из каталога</option>
            <option value="private">Личные</option>
          </select>
        </label>
      </template>
      <fieldset v-if="mode === 'catalog' || mode === 'recommendations'">
        <legend>Теги</legend>
        <input v-model="search" placeholder="Поиск тегов" aria-label="Поиск тегов фильтра" />
        <p class="field-hint">«Есть» включает тег в поиск, «Нет» исключает. До 30 тегов в каждом списке.</p>
        <div class="selected-tags">
          <button
            v-for="tag in state.tags.filter(
              (t) => draft.tag_ids.includes(t.id) || draft.exclude_tag_ids.includes(t.id),
            )"
            :key="tag.id"
            class="chip"
            type="button"
            :class="draft.tag_ids.includes(tag.id) ? 'positive' : 'negative'"
            @click="toggle(draft.tag_ids.includes(tag.id) ? 'tag_ids' : 'exclude_tag_ids', tag.id)"
          >
            {{ tag.name }} ×
          </button>
        </div>
        <div class="tag-options">
          <div v-for="tag in tags" :key="tag.id" class="tag-choice">
            <span>{{ tag.name }}</span>
            <button
              type="button"
              class="chip"
              :class="{ active: draft.tag_ids.includes(tag.id) }"
              @click="toggle('tag_ids', tag.id)"
            >
              Есть
            </button>
            <button
              type="button"
              class="chip"
              :class="{ negative: draft.exclude_tag_ids.includes(tag.id) }"
              @click="toggle('exclude_tag_ids', tag.id)"
            >
              Нет
            </button>
          </div>
          <p v-if="!tags.length" class="muted">Теги не найдены</p>
        </div>
      </fieldset>
      <div class="modal-actions">
        <button type="button" class="text-button muted" @click="reset">Сбросить</button>
        <button class="button">Применить</button>
      </div>
    </form>
  </Modal>
</template>
