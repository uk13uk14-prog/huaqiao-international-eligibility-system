<template>
  <div v-if="visible" class="preview-build-badge" role="status">
    <span>PREVIEW BUILD</span>
    <span>{{ shortHead }}</span>
  </div>
</template>

<script setup>
const enabled = String(import.meta.env.VITE_PREVIEW_DIAGNOSTIC || '') === '1'
const shortHead = String(import.meta.env.VITE_PREVIEW_HEAD || '').trim()
const visible = enabled && !!shortHead
</script>

<style scoped>
.preview-build-badge {
  position: fixed;
  top: 90px;
  right: 8px;
  z-index: 2147483647;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  background: #ffffff;
  color: #b91c1c;
  border: 2px solid #b91c1c;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: 0.02em;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
}
</style>
