<script setup>
import { ref, watch, nextTick } from 'vue'
import { BookOpen } from '@lucide/vue'
import { api } from '../api'
const props = defineProps({ work: Object, eager: Boolean })
const failed = ref(false),
  retrying = ref(false)
let attempted = false
watch(
  () => props.work.cover_url,
  () => {
    failed.value = false
    attempted = false
  },
)
async function retry() {
  if (attempted) {
    failed.value = true
    return
  }
  attempted = true
  try {
    await api('/me')
    retrying.value = true
    await nextTick()
    retrying.value = false
  } catch {
    failed.value = true
  }
}
</script>
<template>
  <div class="cover">
    <img
      v-if="work.cover_url && !failed && !retrying"
      :src="work.cover_url"
      :alt="work.title"
      :loading="eager ? 'eager' : 'lazy'"
      @error="retry"
    />
    <div v-else class="cover-empty">
      <BookOpen :size="30" />
      <span>Нет обложки</span>
    </div>
  </div>
</template>
