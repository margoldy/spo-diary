<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Check, X } from '@lucide/vue'
import { state, bootstrap } from './store'
import ErrorBox from './components/ErrorBox.vue'
const router = useRouter(),
  route = useRoute()
const loading = ref(true),
  error = ref(null)
async function start() {
  loading.value = true
  error.value = null
  try {
    await bootstrap()
  } catch (e) {
    if (e.status !== 401) error.value = e
  }
  if (!error.value && !state.user && route.path !== '/login')
    await router.replace({ path: '/login', query: { next: route.fullPath } })
  else if (state.user && route.path === '/login') await router.replace('/catalog')
  loading.value = false
}
function expire() {
  state.user = null
  if (state.ready && route.path !== '/login')
    router.replace({ path: '/login', query: { next: route.fullPath } })
}
onMounted(() => {
  window.addEventListener('auth-expired', expire)
  start()
})
onBeforeUnmount(() => window.removeEventListener('auth-expired', expire))
</script>
<template>
  <header class="site-header" v-if="state.user && !loading && !error">
    <RouterLink to="/catalog" class="brand" aria-label="На главную">
      <img src="/miku-shiba.png" alt="Сиба-ину Мику" />
    </RouterLink>
    <nav aria-label="Основная навигация">
      <RouterLink to="/catalog">Каталог</RouterLink>
      <RouterLink to="/library">Моя библиотека</RouterLink>
      <RouterLink
        to="/recommendations"
        :class="{ 'router-link-active': route.path === '/hidden' || route.path.endsWith('/similar') }"
      >
        Рекомендации
      </RouterLink>
    </nav>
    <RouterLink to="/profile" class="profile-link" aria-label="Профиль">
      <img src="/miku-shiba.png" alt="" />
      <span>{{ state.user.name }}</span>
    </RouterLink>
  </header>
  <main v-if="loading" class="page-state" role="status">
    <span class="spinner" />
    Загрузка…
  </main>
  <main v-else-if="error" class="page-state">
    <ErrorBox :error="error" />
    <button class="button" @click="start">Повторить</button>
  </main>
  <RouterView v-else v-slot="{ Component }"><component :is="Component" :key="route.path" /></RouterView>
  <Transition name="toast">
    <div v-if="state.toast" class="toast" role="status">
      <Check :size="18" />
      <span>{{ state.toast }}</span>
      <button class="icon-button" aria-label="Закрыть уведомление" @click="state.toast = ''">
        <X :size="16" />
      </button>
    </div>
  </Transition>
</template>
