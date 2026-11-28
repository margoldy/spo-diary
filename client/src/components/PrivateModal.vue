<script setup>
import { ref, reactive, computed, onBeforeUnmount } from 'vue'
import { Upload, X } from '@lucide/vue'
import Modal from './Modal.vue'
import ErrorBox from './ErrorBox.vue'
import FeedbackForm from './FeedbackForm.vue'
import { state, changed, authorLabel } from '../store'
import { api } from '../api'
import { feedbackDraft, feedbackBody, feedbackError } from '../feedback'
const props = defineProps({ work: Object })
const emit = defineEmits(['close', 'saved'])
const draft = reactive({
  title: props.work?.title || '',
  type: props.work?.type || 'book',
  description: props.work?.description || '',
  author: props.work?.author || '',
  year: props.work?.year || '',
  country: props.work?.country || '',
  age_rating: props.work?.age_rating || '',
  genre_ids: props.work?.genres?.map((g) => g.id) || [],
})
const feedback = ref(feedbackDraft()),
  busy = ref(false),
  error = ref(null),
  file = ref(null),
  preview = ref(props.work?.cover_url || ''),
  removeCover = ref(false),
  savedId = ref(props.work?.id || null),
  savedResult = ref(null)
const created = computed(() => !props.work && savedId.value)
let objectUrl
function selectFile(event) {
  const selected = event.target.files[0]
  if (!selected) return
  if (
    !['image/jpeg', 'image/png', 'image/webp'].includes(selected.type) ||
    selected.size > 10 * 1024 * 1024
  ) {
    error.value = 'Обложка: JPEG, PNG или WebP до 10 МиБ'
    event.target.value = ''
    return
  }
  error.value = null
  file.value = selected
  removeCover.value = false
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = URL.createObjectURL(selected)
  preview.value = objectUrl
}
function clearCover() {
  file.value = null
  preview.value = ''
  removeCover.value = true
  if (objectUrl) URL.revokeObjectURL(objectUrl)
}
function close() {
  if (savedResult.value) {
    changed('Личная карточка сохранена')
    emit('saved', savedResult.value)
  }
  emit('close')
}
async function save() {
  error.value = !props.work ? feedbackError(feedback.value) : null
  if (error.value) return
  busy.value = true
  try {
    const body = {
      ...draft,
      title: draft.title.trim(),
      description: draft.description.trim() || null,
      author: draft.author.trim() || null,
      country: draft.country.trim() || null,
      year: draft.year === '' ? null : Number(draft.year),
      age_rating: draft.age_rating || null,
    }
    if (!created.value) {
      const result = props.work
        ? await api(`/me/private-works/${savedId.value}`, { method: 'PATCH', body })
        : await api('/me/private-works', {
            method: 'POST',
            body: { ...body, entry: feedbackBody(feedback.value) },
          })
      savedId.value = result.work.id
      savedResult.value = result
    }
    if (file.value) {
      const body = new FormData()
      body.append('file', file.value)
      await api(`/me/private-works/${savedId.value}/cover`, { method: 'PUT', body })
    } else if (removeCover.value && props.work?.cover_url)
      await api(`/me/private-works/${savedId.value}/cover`, { method: 'DELETE' })
    changed('Личная карточка сохранена')
    emit('saved', savedResult.value)
    emit('close')
  } catch (e) {
    error.value = created.value
      ? `Карточка создана, но обложка не загружена. ${e.message} Повторите загрузку или закройте окно.`
      : e
  } finally {
    busy.value = false
  }
}
onBeforeUnmount(() => {
  if (objectUrl) URL.revokeObjectURL(objectUrl)
})
</script>
<template>
  <Modal :title="work ? 'Изменить произведение' : 'Личное произведение'" wide :busy="busy" @close="close">
    <p class="dialog-subtitle">Карточка будет видна только вам.</p>
    <form @submit.prevent="save">
      <fieldset :disabled="busy">
        <div class="private-top">
          <div class="upload-box">
            <img v-if="preview" :src="preview" alt="Предпросмотр обложки" />
            <Upload v-else :size="30" />
            <label class="button small outline upload-label">
              {{ preview ? 'Заменить' : 'Обложка' }}
              <input type="file" accept="image/jpeg,image/png,image/webp" @change="selectFile" />
            </label>
            <button v-if="preview" type="button" class="text-button small" @click="clearCover">
              <X :size="13" />
              Удалить
            </button>
          </div>
          <div class="private-title">
            <label>
              Название *
              <input
                v-model="draft.title"
                required
                maxlength="300"
                :disabled="!!created"
                placeholder="Название произведения"
              />
            </label>
            <label>
              Тип *
              <select v-model="draft.type" :disabled="!!created">
                <option v-for="type in state.types" :key="type.code" :value="type.code">
                  {{ type.name }}
                </option>
              </select>
            </label>
            <span class="field-hint">JPEG, PNG, WebP · до 10 МиБ</span>
          </div>
        </div>
      </fieldset>
      <fieldset :disabled="busy || !!created">
        <label>
          Описание
          <textarea v-model="draft.description" rows="3" maxlength="10000"></textarea>
        </label>
        <label>
          {{ authorLabel(draft.type) }}
          <input v-model="draft.author" maxlength="1000" />
        </label>
        <div class="form-row">
          <label>
            Год
            <input v-model="draft.year" type="number" min="1" max="9999" step="1" />
          </label>
          <label>
            Страна
            <input v-model="draft.country" maxlength="100" />
          </label>
          <label>
            Возраст
            <select v-model="draft.age_rating">
              <option value="">Не указан</option>
              <option v-for="age in ['0+', '6+', '12+', '16+', '18+']" :key="age">{{ age }}</option>
            </select>
          </label>
        </div>
        <fieldset>
          <legend>Жанры</legend>
          <div class="chips">
            <label
              v-for="genre in state.genres"
              :key="genre.id"
              class="chip checkbox-chip"
              :class="{ active: draft.genre_ids.includes(genre.id) }"
            >
              <input type="checkbox" v-model="draft.genre_ids" :value="genre.id" />
              {{ genre.name }}
            </label>
          </div>
        </fieldset>
        <template v-if="!work">
          <h3>Мой отзыв</h3>
          <FeedbackForm :draft="feedback" />
        </template>
      </fieldset>
      <ErrorBox :error="error" />
      <div class="modal-actions">
        <button type="button" class="button outline" :disabled="busy" @click="close">
          {{ created ? 'Закрыть' : 'Отмена' }}
        </button>
        <button class="button" :disabled="busy">
          {{ busy ? 'Сохранение…' : created ? 'Повторить загрузку' : 'Сохранить' }}
        </button>
      </div>
    </form>
  </Modal>
</template>
