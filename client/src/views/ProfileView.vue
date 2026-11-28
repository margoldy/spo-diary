<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { LogOut } from '@lucide/vue'
import { api } from '../api'
import { state, notify } from '../store'
import ErrorBox from '../components/ErrorBox.vue'
const router = useRouter(),
  name = ref(state.user?.name || ''),
  busy = ref(false),
  error = ref(null)
async function save() {
  busy.value = true
  error.value = null
  try {
    state.user = await api('/me', { method: 'PATCH', body: { name: name.value.trim() } })
    notify('Имя сохранено')
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}
async function logout() {
  busy.value = true
  error.value = null
  try {
    await api('/auth/logout', { method: 'POST' })
    state.user = null
    await router.replace('/login')
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <main class="page profile-page">
    <h1>Профиль</h1>
    <section class="profile-panel">
      <img src="/miku-shiba.png" alt="Сиба-ину Мику" class="profile-mascot" />
      <form @submit.prevent="save">
        <label>
          Имя
          <input v-model="name" required maxlength="80" autocomplete="nickname" :disabled="busy" />
        </label>
        <label>
          Электронная почта
          <input :value="state.user?.email" readonly />
        </label>
        <ErrorBox :error="error" />
        <button class="button full" :disabled="busy || !name.trim()">Сохранить</button>
      </form>
      <button class="text-button logout-button" :disabled="busy" @click="logout">
        <LogOut :size="17" />
        Выйти из аккаунта
      </button>
    </section>
  </main>
</template>
