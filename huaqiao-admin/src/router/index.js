import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api/client'
import LoginView from '../views/LoginView.vue'
import ShellView from '../views/ShellView.vue'
import DashboardView from '../views/DashboardView.vue'
import UsersView from '../views/UsersView.vue'
import UserDetailView from '../views/UserDetailView.vue'
import StudentsView from '../views/StudentsView.vue'
import Student360View from '../views/Student360View.vue'
import ConsultationsView from '../views/ConsultationsView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    {
      path: '/',
      component: ShellView,
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: DashboardView },
        { path: 'users', component: UsersView },
        { path: 'users/:userId', component: UserDetailView, props: true },
        { path: 'students', component: StudentsView },
        { path: 'students/:studentId', component: Student360View, props: true },
        { path: 'consultations', component: ConsultationsView },
        { path: 'settings', component: SettingsView },
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!getToken()) return '/login'
  return true
})

export default router
