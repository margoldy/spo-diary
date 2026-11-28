<script setup>
import { computed, ref } from 'vue'
import { ThumbsUp, ThumbsDown, Search } from '@lucide/vue'
import { state, statuses } from '../store'
import Stars from './Stars.vue'
const props = defineProps({ draft: Object })
const search = ref('')
const tags = computed(() =>
  state.tags.filter((t) => t.name.toLocaleLowerCase('ru').includes(search.value.toLocaleLowerCase('ru'))),
)
const count = computed(
  () =>
    props.draft.liked.trim().length + props.draft.disliked.trim().length + props.draft.comment.trim().length,
)
function choose(id, value) {
  if (props.draft.choices[id] === value) delete props.draft.choices[id]
  else props.draft.choices[id] = value
}
</script>
<template>
  <div class="form-row">
    <label>
      Статус
      <select v-model="draft.status">
        <option v-for="(title, code) in statuses" :key="code" :value="code">{{ title }}</option>
      </select>
    </label>
    <div class="field">
      <span>Моя оценка</span>
      <Stars v-model="draft.rating" />
    </div>
  </div>
  <div class="segmented" aria-label="Способ отзыва">
    <button type="button" :class="{ active: draft.mode === 'review' }" @click="draft.mode = 'review'">
      Написать отзыв
    </button>
    <button type="button" :class="{ active: draft.mode === 'manual' }" @click="draft.mode = 'manual'">
      Выбрать теги
    </button>
  </div>
  <template v-if="draft.mode === 'review'">
    <p class="field-hint">Теги для рекомендаций определятся автоматически.</p>
    <label>
      Что понравилось
      <textarea
        v-model="draft.liked"
        rows="3"
        maxlength="5000"
        placeholder="Герои, темы, атмосфера…"
      ></textarea>
    </label>
    <label>
      Что не понравилось
      <textarea
        v-model="draft.disliked"
        rows="3"
        maxlength="5000"
        placeholder="Что испортило впечатление"
      ></textarea>
    </label>
    <label>
      Комментарий
      <textarea v-model="draft.comment" rows="3" maxlength="5000" placeholder="Другие впечатления"></textarea>
    </label>
    <p class="counter" :class="{ invalid: count > 5000 }">{{ count }} / 5000</p>
  </template>
  <template v-else>
    <p class="field-hint">
      Отметьте то, что понравилось или не понравилось. Повторное нажатие снимает отметку.
    </p>
    <div class="search-input">
      <Search :size="17" />
      <input v-model="search" placeholder="Найти тег" aria-label="Поиск тегов" />
    </div>
    <div class="selected-tags" v-if="Object.keys(draft.choices).length">
      <button
        v-for="tag in state.tags.filter((t) => draft.choices[t.id])"
        :key="tag.id"
        class="chip"
        :class="draft.choices[tag.id] > 0 ? 'positive' : 'negative'"
        type="button"
        @click="delete draft.choices[tag.id]"
      >
        {{ tag.name }} ×
      </button>
    </div>
    <div class="tag-options">
      <div v-for="tag in tags" :key="tag.id" class="tag-choice">
        <span>{{ tag.name }}</span>
        <button
          type="button"
          class="icon-button"
          :class="{ positive: draft.choices[tag.id] === 1 }"
          :aria-label="`${tag.name}: понравилось`"
          :aria-pressed="draft.choices[tag.id] === 1"
          @click="choose(tag.id, 1)"
        >
          <ThumbsUp :size="17" />
        </button>
        <button
          type="button"
          class="icon-button"
          :class="{ negative: draft.choices[tag.id] === -1 }"
          :aria-label="`${tag.name}: не понравилось`"
          :aria-pressed="draft.choices[tag.id] === -1"
          @click="choose(tag.id, -1)"
        >
          <ThumbsDown :size="17" />
        </button>
      </div>
      <p v-if="!tags.length" class="muted">Теги не найдены</p>
    </div>
  </template>
</template>
