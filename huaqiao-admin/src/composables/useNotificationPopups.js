import { onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { api } from '../api/client'

/** HIGH once / CRITICAL until read — admin mobile popup gate. */
export function useNotificationPopups() {
  const loading = ref(false)

  async function showPendingPopups() {
    loading.value = true
    try {
      const data = await api.notificationPopups()
      const items = data.items || []
      for (const n of items) {
        const isCrit = n.priority === 'CRITICAL'
        await ElMessageBox.alert(n.body || '', n.title || '重要提醒', {
          confirmButtonText: isCrit ? '我已知晓' : '知道了',
          closeOnClickModal: !isCrit,
          closeOnPressEscape: !isCrit,
          showClose: !isCrit,
        })
        try {
          await api.notificationPopupShown(n.id)
        } catch {
          /* ignore */
        }
        if (isCrit) {
          try {
            await api.notificationRead(n.id)
          } catch {
            /* ignore */
          }
        }
      }
    } catch {
      /* offline / unauthorized — ignore */
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    showPendingPopups()
  })

  return { showPendingPopups, loading }
}
