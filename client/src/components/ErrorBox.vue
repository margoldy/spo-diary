<script setup>
defineProps({ error: [Object, String] })
</script>
<template>
  <div v-if="error" class="error-box" role="alert">
    <p>{{ error.message || error }}</p>
    <ul v-if="error.fields?.length">
      <li v-for="(field, i) in error.fields" :key="i">{{ field.message }}</li>
    </ul>
  </div>
</template>
