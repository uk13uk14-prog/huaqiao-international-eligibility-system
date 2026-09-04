import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api/client'
import { isMobileViewport } from '../composables/useIsMobile'
import LoginView from '../views/LoginView.vue'
import ShellView from '../views/ShellView.vue'
import DashboardView from '../views/DashboardView.vue'
import UsersView from '../views/UsersView.vue'
import UserDetailView from '../views/UserDetailView.vue'
import StudentsView from '../views/StudentsView.vue'
import Student360View from '../views/Student360View.vue'
import ConsultationsView from '../views/ConsultationsView.vue'
import SettingsView from '../views/SettingsView.vue'
import MobileHomeView from '../mobile/MobileHomeView.vue'
import MobileStudentsView from '../mobile/MobileStudentsView.vue'
import MobileStudent360View from '../mobile/MobileStudent360View.vue'
import MobileApprovalView from '../mobile/MobileApprovalView.vue'
import MobileAiView from '../mobile/MobileAiView.vue'
import MobilePublishedView from '../mobile/MobilePublishedView.vue'
import MobileMeView from '../mobile/MobileMeView.vue'
import MobileNotificationsView from '../mobile/MobileNotificationsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    {
      path: '/',
      component: ShellView,
      children: [
        { path: '', redirect: () => (isMobileViewport() ? '/m/home' : '/dashboard') },
        { path: 'dashboard', component: DashboardView },
        { path: 'users', component: UsersView },
        { path: 'users/:userId', component: UserDetailView, props: true },
        { path: 'students', component: StudentsView },
        { path: 'students/:studentId', component: Student360View, props: true },
        { path: 'consultations', component: ConsultationsView },
        { path: 'settings', component: SettingsView },

        /* Mobile ops shell — same API / JWT as desktop */
        { path: 'm/home', component: MobileHomeView, meta: { mobile: true } },
        { path: 'm/students', component: MobileStudentsView, meta: { mobile: true } },
        {
          path: 'm/students/:studentId',
          component: MobileStudent360View,
          props: true,
          meta: { mobile: true, mobileTab: false },
        },
        { path: 'm/approval', component: MobileApprovalView, meta: { mobile: true } },
        { path: 'm/ai', component: MobileAiView, meta: { mobile: true } },
        {
          path: 'm/ai/:studentId',
          component: MobileAiView,
          props: true,
          meta: { mobile: true, mobileTab: false },
        },
        { path: 'm/published', component: MobilePublishedView, meta: { mobile: true } },
        { path: 'm/notifications', component: MobileNotificationsView, meta: { mobile: true } },
        { path: 'm/me', component: MobileMeView, meta: { mobile: true } },
      ],
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!getToken()) return '/login'
  return true
})

export default router
