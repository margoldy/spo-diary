import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import AuthView from './views/AuthView.vue'
import BrowseView from './views/BrowseView.vue'
import DetailView from './views/DetailView.vue'
import ProfileView from './views/ProfileView.vue'
import { state } from './store'
import './style.css'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', redirect: '/catalog' },
    { path: '/login', component: AuthView },
    { path: '/catalog', component: BrowseView, props: { mode: 'catalog' } },
    { path: '/library', component: BrowseView, props: { mode: 'library' } },
    { path: '/recommendations', component: BrowseView, props: { mode: 'recommendations' } },
    { path: '/hidden', component: BrowseView, props: { mode: 'hidden' } },
    { path: '/works/:scope(catalog|private)/:id', component: DetailView },
    { path: '/works/:scope(catalog|private)/:id/similar', component: BrowseView, props: { mode: 'similar' } },
    { path: '/profile', component: ProfileView },
    { path: '/:pathMatch(.*)*', redirect: '/catalog' },
  ],
})
router.beforeEach((to) => {
  if (state.ready && !state.user && to.path !== '/login')
    return { path: '/login', query: { next: to.fullPath } }
  if (state.user && to.path === '/login') return '/catalog'
})
createApp(App).use(router).mount('#app')
