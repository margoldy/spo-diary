<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { X } from '@lucide/vue'
const props = defineProps({ title: String, wide: Boolean, busy: Boolean })
const emit = defineEmits(['close'])
const panel = ref(null)
const previous = document.activeElement
const oldOverflow = document.body.style.overflow
function keydown(event) {
  if (event.key === 'Escape' && !props.busy) emit('close')
  if (event.key !== 'Tab') return
  const elements = [
    ...panel.value.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]',
    ),
  ].filter((el) => el.getClientRects().length)
  const first = elements[0],
    last = elements.at(-1)
  if (!first) {
    event.preventDefault()
    return
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
onMounted(async () => {
  document.body.style.overflow = 'hidden'
  document.addEventListener('keydown', keydown)
  await nextTick()
  panel.value.focus()
})
onBeforeUnmount(() => {
  document.body.style.overflow = oldOverflow
  document.removeEventListener('keydown', keydown)
  previous?.focus()
})
</script>
<template>
  <Teleport to="body">
    <div class="modal-backdrop" @mousedown.self="!busy && emit('close')">
      <section
        ref="panel"
        class="modal"
        :class="{ wide }"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        tabindex="-1"
      >
        <header class="modal-heading">
          <h2 id="dialog-title">{{ title }}</h2>
          <button class="icon-button" :disabled="busy" aria-label="Закрыть" @click="emit('close')">
            <X :size="21" />
          </button>
        </header>
        <slot />
      </section>
    </div>
  </Teleport>
</template>
