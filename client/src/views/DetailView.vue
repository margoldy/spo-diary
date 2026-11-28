<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Pencil, Trash2, Search, Plus, ThumbsUp, ThumbsDown, RefreshCw } from '@lucide/vue'
import { api, workPath, workLink } from '../api'
import { changed, typeName, statuses, authorLabel } from '../store'
import Cover from '../components/Cover.vue'
import Stars from '../components/Stars.vue'
import EntryModal from '../components/EntryModal.vue'
import PrivateModal from '../components/PrivateModal.vue'
import Modal from '../components/Modal.vue'
import ErrorBox from '../components/ErrorBox.vue'
const route = useRoute(),
  router = useRouter()
const data = ref(null),
  loading = ref(true),
  error = ref(null),
  actionError = ref(null),
  edit = ref(false),
  editPrivate = ref(false),
  confirmDelete = ref(false),
  busy = ref(false)
let timer,
  alive = true
const path = () => workPath({ id: route.params.id, scope: route.params.scope })
function schedule() {
  clearTimeout(timer)
  if (['pending', 'running'].includes(data.value?.entry?.analysis.status)) timer = setTimeout(poll, 3500)
}
async function load() {
  error.value = null
  try {
    const result = await api(path())
    if (!alive) return
    data.value = result
    schedule()
  } catch (e) {
    if (alive) error.value = e
  } finally {
    loading.value = false
  }
}
async function poll() {
  if (!alive || !data.value?.entry) return
  try {
    const analysis = await api(`/me/library/${data.value.entry.id}/analysis`)
    if (!alive) return
    Object.assign(data.value.entry, analysis)
    actionError.value = null
    schedule()
  } catch (e) {
    if (alive) actionError.value = e
  }
}
async function retry() {
  busy.value = true
  actionError.value = null
  try {
    Object.assign(
      data.value.entry,
      await api(`/me/library/${data.value.entry.id}/analysis/retry`, { method: 'POST' }),
    )
    schedule()
  } catch (e) {
    actionError.value = e
  } finally {
    busy.value = false
  }
}
async function remove() {
  busy.value = true
  actionError.value = null
  try {
    await api(`/me/library/${data.value.entry.id}`, { method: 'DELETE' })
    confirmDelete.value = false
    changed('Удалено из библиотеки')
    if (data.value.work.scope === 'private') router.push('/library')
    else await load()
  } catch (e) {
    actionError.value = e
  } finally {
    busy.value = false
  }
}
watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => {
  alive = false
  clearTimeout(timer)
})
</script>
<template>
  <main class="page detail-page">
    <button
      class="back-link text-button"
      @click="router.options.history.state.back ? router.back() : router.push('/catalog')"
    >
      <ArrowLeft :size="20" />
      Назад
    </button>
    <h1>Информация о произведении</h1>
    <div v-if="loading" class="page-state">
      <span class="spinner" />
      Загрузка…
    </div>
    <div v-else-if="error" class="empty-state">
      <ErrorBox :error="error" />
      <button class="button outline" @click="load">Повторить</button>
    </div>
    <template v-else-if="data">
      <section class="detail-panel">
        <div class="detail-top">
          <Cover :work="data.work" eager />
          <div class="detail-info">
            <div class="detail-title-row">
              <h2>{{ data.work.title }}</h2>
              <button
                v-if="data.work.scope === 'private'"
                class="icon-button"
                title="Изменить карточку"
                aria-label="Изменить карточку"
                @click="editPrivate = true"
              >
                <Pencil :size="18" />
              </button>
            </div>
            <span v-if="data.work.scope === 'private'" class="private-label">Личное произведение</span>
            <dl class="detail-meta">
              <dt>Тип:</dt>
              <dd>{{ typeName(data.work.type) }}</dd>
              <template v-if="data.work.author">
                <dt>{{ authorLabel(data.work.type) }}:</dt>
                <dd>{{ data.work.author }}</dd>
              </template>
              <template v-if="data.work.year">
                <dt>Год:</dt>
                <dd>{{ data.work.year }}</dd>
              </template>
              <template v-if="data.work.genres.length">
                <dt>Жанры:</dt>
                <dd>{{ data.work.genres.map((g) => g.name).join(', ') }}</dd>
              </template>
              <template v-if="data.work.country">
                <dt>Страна:</dt>
                <dd>{{ data.work.country }}</dd>
              </template>
              <template v-if="data.work.age_rating">
                <dt>Возраст:</dt>
                <dd>{{ data.work.age_rating }}</dd>
              </template>
            </dl>
            <button v-if="!data.entry" class="button small" @click="edit = true">
              <Plus :size="16" />
              Добавить в библиотеку
            </button>
            <span v-else class="status-label">{{ statuses[data.entry.status] }}</span>
          </div>
        </div>
        <p v-if="data.work.description" class="description">{{ data.work.description }}</p>
        <div v-if="data.work.tags.length" class="chips detail-tags">
          <span class="chip" v-for="tag in data.work.tags" :key="tag.id">{{ tag.name }}</span>
        </div>
      </section>
      <section v-if="data.adaptations?.length" class="adaptations">
        <h2>Другие версии</h2>
        <div class="adaptation-list">
          <RouterLink v-for="work in data.adaptations" :key="work.id" :to="workLink(work)" class="adaptation">
            <Cover :work="work" />
            <span>
              {{ work.title }}
              <small>{{ typeName(work.type) }}</small>
            </span>
          </RouterLink>
        </div>
      </section>
      <template v-if="data.entry">
        <div class="section-heading">
          <h2>Мой отзыв</h2>
          <button class="icon-button" aria-label="Редактировать отзыв" @click="edit = true">
            <Pencil :size="18" />
          </button>
        </div>
        <section class="review-panel">
          <div class="review-top">
            <span>{{ statuses[data.entry.status] }}</span>
            <Stars :model-value="data.entry.rating" readonly />
          </div>
          <dl class="review-text">
            <template
              v-for="[key, label] in [
                ['liked', 'Что понравилось'],
                ['disliked', 'Что не понравилось'],
                ['comment', 'Комментарий'],
              ]"
              :key="key"
            >
              <template v-if="data.entry[key]">
                <dt>{{ label }}</dt>
                <dd>{{ data.entry[key] }}</dd>
              </template>
            </template>
          </dl>
          <p
            v-if="
              !data.entry.liked && !data.entry.disliked && !data.entry.comment && !data.entry.signals.length
            "
            class="muted"
          >
            Отзыв пока не добавлен.
          </p>
          <div
            v-if="['pending', 'running'].includes(data.entry.analysis.status)"
            class="analysis-state"
            role="status"
          >
            <span class="spinner small-spinner" />
            {{
              data.entry.analysis.status === 'pending' ? 'Отзыв ожидает анализа' : 'Определяем теги из отзыва'
            }}
          </div>
          <div v-else-if="data.entry.analysis.status === 'error'" class="analysis-state negative">
            <span>Не удалось проанализировать отзыв</span>
            <button class="text-button" :disabled="busy" @click="retry">
              <RefreshCw :size="16" />
              Повторить
            </button>
          </div>
          <template v-if="data.entry.signals.length">
            <h3 class="signal-heading">
              {{
                { review: 'Теги из отзыва', manual: 'Мои теги', rating: 'Предположение по оценке' }[
                  data.entry.effective_source
                ]
              }}
            </h3>
            <div class="signals">
              <div
                v-for="signal in data.entry.signals"
                :key="signal.tag.id"
                class="signal"
                :class="signal.value > 0 ? 'positive' : signal.value < 0 ? 'negative' : 'neutral'"
              >
                <span>
                  <ThumbsUp v-if="signal.value > 0" :size="14" />
                  <ThumbsDown v-else-if="signal.value < 0" :size="14" />
                  {{ signal.tag.name }}
                </span>
                <blockquote v-if="signal.quote">{{ signal.quote }}</blockquote>
              </div>
            </div>
          </template>
          <p v-else-if="data.entry.analysis.status === 'done'" class="muted">
            В отзыве не найдены теги для рекомендаций.
          </p>
        </section>
        <ErrorBox :error="actionError" />
        <button
          v-if="actionError && ['pending', 'running'].includes(data.entry.analysis.status)"
          class="text-button"
          @click="poll"
        >
          Обновить анализ
        </button>
      </template>
      <div class="detail-footer">
        <button v-if="data.entry" class="text-button muted" @click="confirmDelete = true">
          <Trash2 :size="16" />
          Удалить из библиотеки
        </button>
        <RouterLink :to="`${workLink(data.work)}/similar`" class="button">
          <Search :size="17" />
          Найти похожие
        </RouterLink>
      </div>
      <EntryModal v-if="edit" :work="data.work" :entry="data.entry" @close="edit = false" @saved="load" />
      <PrivateModal v-if="editPrivate" :work="data.work" @close="editPrivate = false" @saved="load" />
      <Modal v-if="confirmDelete" title="Удалить из библиотеки?" :busy="busy" @close="confirmDelete = false">
        <p>«{{ data.work.title }}»</p>
        <p class="muted">
          {{
            data.work.scope === 'private'
              ? 'Личная карточка, обложка и отзыв будут удалены.'
              : 'Оценка и отзыв будут удалены.'
          }}
        </p>
        <ErrorBox :error="actionError" />
        <div class="modal-actions">
          <button class="button outline" :disabled="busy" @click="confirmDelete = false">Отмена</button>
          <button class="button danger-button" :disabled="busy" @click="remove">
            {{ busy ? 'Удаление…' : 'Удалить' }}
          </button>
        </div>
      </Modal>
    </template>
  </main>
</template>
