import { computed, ref } from 'vue'
import { api } from '../api/client'

const me = ref(null)
const loaded = ref(false)

export function useAdminSession() {
  const role = computed(() => me.value?.console_role || '')
  const permissions = computed(() => me.value?.permissions || [])
  const menu = computed(() => me.value?.menu || [])
  const user = computed(() => me.value?.user || {})
  const mustChange = computed(() => !!me.value?.must_change_password)

  function can(cap) {
    return permissions.value.includes(cap)
  }

  async function refresh() {
    me.value = await api.me()
    loaded.value = true
    return me.value
  }

  const groupedMenu = computed(() => {
    const groups = []
    const map = new Map()
    for (const item of menu.value) {
      if (!map.has(item.group)) {
        const g = { title: item.group, items: [] }
        map.set(item.group, g)
        groups.push(g)
      }
      map.get(item.group).items.push(item)
    }
    return groups
  })

  return { me, loaded, role, permissions, menu, groupedMenu, user, mustChange, can, refresh }
}
