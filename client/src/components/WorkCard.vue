<script setup>
import { computed } from 'vue'
import { EyeOff, RotateCcw } from '@lucide/vue'
import Cover from './Cover.vue'
import Stars from './Stars.vue'
import { typeName, statuses, authorLabel } from '../store'
import { workLink } from '../api'
const props = defineProps({ work: Object, entry: Object, reason: Object, mode: String })

const addedDate = computed(() => {
  if (!props.entry?.created_at) return null
  const date = new Date(props.entry.created_at)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
})
defineEmits(['add', 'hide', 'restore'])
</script>
<template>
  <article class="work-card">
    <RouterLink :to="workLink(work)" class="cover-link" :aria-label="work.title">
      <Cover :work="work" eager />
    </RouterLink>
    <div class="card-content">
      <div class="card-heading">
        <RouterLink :to="workLink(work)" class="card-title">{{ work.title }}</RouterLink>
        <span
          v-if="mode !== 'library' && work.age_rating"
          class="card-age"
          :aria-label="`Возрастное ограничение: ${work.age_rating}`"
        >
          {{ work.age_rating }}
        </span>
      </div>
      <dl class="card-meta">
        <dt>Тип:</dt>
        <dd>{{ typeName(work.type) }}</dd>
        <template v-if="work.year">
          <dt>Год:</dt>
          <dd>{{ work.year }}</dd>
        </template>
        <template v-if="work.author">
          <dt>{{ authorLabel(work.type) }}:</dt>
          <dd class="clamp" :title="work.author">{{ work.author }}</dd>
        </template>
        <template v-if="work.genres?.length">
          <dt>Жанры:</dt>
          <dd class="clamp">{{ work.genres.map((g) => g.name).join(', ') }}</dd>
        </template>
      </dl>
      <span v-if="work.scope === 'private'" class="private-label">Личное произведение</span>
      <Stars v-if="entry?.rating" :model-value="entry.rating" readonly />
      <p v-if="reason?.source_work" class="card-reason" :title="reason.text">
        Похоже на:
        <RouterLink :to="workLink(reason.source_work)">{{ reason.source_work.title }}</RouterLink>
      </p>
      <p v-else-if="reason?.text" class="card-reason">{{ reason.text }}</p>
      <details v-if="reason?.source_work" class="reason-details">
        <summary>Почему рекомендовано</summary>
        <p>{{ reason.text }}</p>
      </details>
      <div class="card-actions">
        <time v-if="mode === 'library' && addedDate" class="card-added" :datetime="entry.created_at">
          Добавлено {{ addedDate }}
        </time>
        <button
          v-if="mode === 'recommendations' || mode === 'similar'"
          class="icon-button muted"
          aria-label="Скрыть рекомендацию"
          title="Скрыть"
          @click="$emit('hide', work)"
        >
          <EyeOff :size="17" />
        </button>
        <button v-if="mode === 'hidden'" class="button small outline" @click="$emit('restore', work)">
          <RotateCcw :size="14" />
          Вернуть
        </button>
        <RouterLink v-else-if="entry" :to="workLink(work)" class="button small outline">
          {{ statuses[entry.status] }}
        </RouterLink>
        <button v-else class="button small" @click="$emit('add', work)">Добавить в библиотеку</button>
      </div>
    </div>
  </article>
</template>
