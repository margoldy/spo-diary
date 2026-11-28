<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, ArrowLeft, Mail } from '@lucide/vue'
import { api } from '../api'
import { state, loadReferences } from '../store'
import ErrorBox from '../components/ErrorBox.vue'
const router = useRouter(),
  route = useRoute()
const email = ref(''),
  code = ref(''),
  name = ref(''),
  register = ref(true),
  challenge = ref(null),
  busy = ref(false),
  error = ref(null),
  seconds = ref(0),
  signedInUser = ref(null)
let saveName = false
const next =
  typeof route.query.next === 'string' &&
  /^\/(catalog|library|recommendations|hidden|works|profile)(\/|\?|$)/.test(route.query.next)
    ? route.query.next
    : '/catalog'
let resendAt = 0
const timer = setInterval(() => {
  seconds.value = Math.max(0, Math.ceil((resendAt - Date.now()) / 1000))
}, 1000)
onBeforeUnmount(() => clearInterval(timer))
function changeEmail() {
  signedInUser.value = null
  saveName = false
  challenge.value = null
  error.value = null
  seconds.value = 0
  resendAt = 0
}
async function requestCode() {
  busy.value = true
  error.value = null
  try {
    challenge.value = await api('/auth/request-code', { method: 'POST', body: { email: email.value.trim() } })
    code.value = ''
    resendAt = Date.now() + challenge.value.resend_after * 1000
    seconds.value = challenge.value.resend_after
  } catch (e) {
    error.value = e
    if (e.details.retry_after) {
      resendAt = Date.now() + e.details.retry_after * 1000
      seconds.value = e.details.retry_after
    }
  } finally {
    busy.value = false
  }
}
async function verify() {
  busy.value = true
  error.value = null
  try {
    if (!signedInUser.value) {
      const result = await api('/auth/verify-code', {
        method: 'POST',
        body: { code_id: challenge.value.code_id, code: code.value },
      })
      signedInUser.value = result.user
      saveName = result.is_new_user && !!name.value.trim()
    }
    if (saveName) {
      signedInUser.value = await api('/me', { method: 'PATCH', body: { name: name.value.trim() } })
      saveName = false
    }
    await loadReferences()
    state.user = signedInUser.value
    await router.replace(next)
  } catch (e) {
    error.value = e
    if (e.status === 401) changeEmail()
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <main class="auth-page">
    <section class="auth-art" aria-label="Сиба-ину в парике Хатсуне Мику">
      <div class="art-disc"></div>
      <img src="/miku-shiba.png" alt="Мемный сиба-ину с бирюзовыми хвостиками Мику" />
      <span class="art-caption">Моя библиотека</span>
    </section>
    <section class="auth-form">
      <div class="auth-tabs" v-if="!challenge">
        <button :class="{ active: register }" @click="register = true">Регистрация</button>
        <button :class="{ active: !register }" @click="register = false">Вход</button>
      </div>
      <template v-if="!challenge">
        <h1>{{ register ? 'Создать аккаунт' : 'Войти в библиотеку' }}</h1>
        <p class="muted auth-hint">
          {{ register ? 'Регистрация по коду из письма.' : 'Отправим код на вашу почту.' }}
        </p>
        <form @submit.prevent="requestCode">
          <label v-if="register">
            Имя
            <input
              v-model="name"
              maxlength="80"
              autocomplete="nickname"
              placeholder="Как к вам обращаться"
              :disabled="busy"
            />
          </label>
          <label>
            Электронная почта
            <input
              v-model="email"
              type="email"
              required
              maxlength="254"
              autocomplete="email"
              placeholder="name@example.com"
              :disabled="busy"
            />
          </label>
          <ErrorBox :error="error" />
          <button class="button full" :disabled="busy || seconds > 0">
            {{ busy ? 'Отправляем…' : seconds ? `Повторить через ${seconds} с` : 'Получить код' }}
            <ArrowRight :size="19" />
          </button>
        </form>
      </template>
      <template v-else>
        <button class="text-button back-link" :disabled="busy" @click="changeEmail">
          <ArrowLeft :size="18" />
          Изменить почту
        </button>
        <Mail class="mail-icon" :size="32" />
        <h1>Проверьте почту</h1>
        <p class="muted auth-hint">
          Код отправлен на
          <strong>{{ email }}</strong>
        </p>
        <form @submit.prevent="verify">
          <label>
            Код из письма
            <input
              class="code-input"
              v-model="code"
              inputmode="numeric"
              autocomplete="one-time-code"
              pattern="[0-9]{6}"
              maxlength="6"
              minlength="6"
              required
              placeholder="000000"
              autofocus
              :disabled="busy"
            />
          </label>
          <ErrorBox :error="error" />
          <button class="button full" :disabled="busy || code.length !== 6">
            {{ busy ? 'Проверяем…' : 'Продолжить' }}
            <ArrowRight :size="19" />
          </button>
        </form>
        <button class="text-button resend" :disabled="busy || seconds > 0" @click="requestCode">
          {{ seconds ? `Отправить ещё раз через ${seconds} с` : 'Отправить код ещё раз' }}
        </button>
      </template>
    </section>
  </main>
</template>
