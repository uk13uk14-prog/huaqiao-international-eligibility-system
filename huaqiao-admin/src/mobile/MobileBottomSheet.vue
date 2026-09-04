<template>
  <div v-if="modelValue" class="sheet-root" @click.self="close">
    <div class="sheet" role="dialog" aria-modal="true">
      <div class="grab" />
      <header class="sheet-hd">
        <strong>{{ title }}</strong>
        <button type="button" class="x" @click="close">关闭</button>
      </header>
      <div class="sheet-bd"><slot /></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.sheet-root {
  position: fixed; inset: 0; z-index: 80;
  background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: flex-end;
}
.sheet {
  width: 100%; max-height: min(88vh, 720px); background: #fff;
  border-radius: 16px 16px 0 0; display: flex; flex-direction: column;
  animation: up 0.22s ease-out;
}
@keyframes up {
  from { transform: translateY(24px); opacity: 0.6; }
  to { transform: translateY(0); opacity: 1; }
}
.grab {
  width: 40px; height: 4px; border-radius: 99px; background: #cbd5e1;
  margin: 8px auto 0;
}
.sheet-hd {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px 8px; border-bottom: 1px solid var(--gq-border);
}
.x { border: 0; background: transparent; color: var(--gq-sea); font-size: 14px; }
.sheet-bd {
  overflow: auto; padding: 12px 16px calc(16px + env(safe-area-inset-bottom, 0px));
  -webkit-overflow-scrolling: touch;
}
</style>
