<script setup>
import { Star } from '@lucide/vue'
defineProps({ modelValue: Number, readonly: Boolean })
const emit = defineEmits(['update:modelValue'])
</script>
<template>
  <div class="stars" :aria-label="modelValue ? `Оценка: ${modelValue} из 5` : 'Без оценки'">
    <template v-for="n in 5" :key="n">
      <Star v-if="readonly" :size="17" :class="{ filled: n <= (modelValue || 0) }" />
      <button
        v-else
        type="button"
        :aria-label="`Оценка ${n}`"
        :aria-pressed="n === modelValue"
        @click="emit('update:modelValue', n === modelValue ? null : n)"
      >
        <Star :size="23" :class="{ filled: n <= (modelValue || 0) }" />
      </button>
    </template>
    <button
      v-if="!readonly && modelValue"
      type="button"
      class="text-button muted"
      @click="emit('update:modelValue', null)"
    >
      Сбросить
    </button>
  </div>
</template>
