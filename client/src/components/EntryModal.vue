<script setup>
import { ref } from 'vue'
import Modal from './Modal.vue'
import ErrorBox from './ErrorBox.vue'
import FeedbackForm from './FeedbackForm.vue'
import { api } from '../api'
import { changed } from '../store'
import { feedbackDraft, feedbackBody, feedbackError } from '../feedback'
const props = defineProps({ work: Object, entry: Object })
const emit = defineEmits(['close', 'saved'])
const draft = ref(feedbackDraft(props.entry)),
  busy = ref(false),
  error = ref(null)
async function save() {
  error.value = feedbackError(draft.value)
  if (error.value) return
  busy.value = true
  try {
    const body = feedbackBody(draft.value)
    const result = props.entry
      ? await api(`/me/library/${props.entry.id}`, { method: 'PATCH', body })
      : await api('/me/library', { method: 'POST', body: { work_id: props.work.id, ...body } })
    changed(props.entry ? 'Отзыв сохранён' : 'Добавлено в библиотеку')
    emit('saved', result)
    emit('close')
  } catch (e) {
    error.value = e
    if (e.code === 'ALREADY_IN_LIBRARY') changed()
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <Modal :title="entry ? 'Мой отзыв' : 'Добавить в библиотеку'" :busy="busy" @close="emit('close')">
    <p class="dialog-subtitle">{{ work.title }}</p>
    <form @submit.prevent="save">
      <fieldset :disabled="busy"><FeedbackForm :draft="draft" /></fieldset>
      <ErrorBox :error="error" />
      <div class="modal-actions">
        <button type="button" class="button outline" :disabled="busy" @click="emit('close')">Отмена</button>
        <button class="button" :disabled="busy">{{ busy ? 'Сохранение…' : 'Сохранить' }}</button>
      </div>
    </form>
  </Modal>
</template>
