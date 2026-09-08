<template>
  <div class="coop-page">
    <div v-if="loading" class="pad muted">加载中…</div>
    <van-empty v-else-if="loadError" description="合作信息暂时无法加载" />
    <template v-else>
      <article class="form-card coop-intro">
        <h2 class="coop-title">{{ data.page_title || '合作中心' }}</h2>
        <p v-if="data.intro" class="coop-lead">{{ data.intro }}</p>
        <p v-else class="coop-lead muted">合作信息由后台维护，欢迎通过以下方式联系。</p>
      </article>

      <article v-if="hasContact" class="form-card coop-contact">
        <h3 class="coop-block-title">合作联系方式</h3>
        <p v-if="contact.contact_name" class="coop-line"><span>联系人</span><b>{{ contact.contact_name }}</b></p>
        <p v-if="contact.wechat" class="coop-line"><span>微信</span><b>{{ contact.wechat }}</b></p>
        <p v-if="contact.phone" class="coop-line">
          <span>电话</span>
          <a :href="`tel:${contact.phone}`">{{ contact.phone }}</a>
        </p>
        <p v-if="contact.email" class="coop-line">
          <span>Email</span>
          <a :href="`mailto:${contact.email}`">{{ contact.email }}</a>
        </p>
        <p v-if="contact.contact_note" class="coop-note">{{ contact.contact_note }}</p>
        <div v-if="contact.qr_url" class="coop-qr">
          <img :src="mediaUrl(contact.qr_url)" alt="合作联系二维码" />
        </div>
      </article>

      <section class="coop-brands">
        <h3 class="coop-block-title">品牌背书</h3>
        <van-empty v-if="!brands.length" description="品牌内容即将发布" />
        <article v-for="item in brands" :key="item.id" class="school-card coop-brand">
          <div class="coop-brand-head">
            <img v-if="item.logo_url" :src="mediaUrl(item.logo_url)" :alt="item.brand_name" class="coop-logo" />
            <div class="coop-brand-copy">
              <h4 class="coop-brand-name">{{ item.brand_name }}</h4>
              <p v-if="item.description" class="coop-brand-desc">{{ item.description }}</p>
              <a v-if="item.link" class="coop-brand-link" :href="item.link" target="_blank" rel="noopener noreferrer">了解更多</a>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from './api'

const loading = ref(true)
const loadError = ref(false)
const data = ref({ page_title: '合作中心', intro: '', contact: {}, brands: [] })

const contact = computed(() => data.value.contact || {})
const brands = computed(() => data.value.brands || [])
const hasContact = computed(() => Object.keys(contact.value).length > 0)

function mediaUrl(u) {
  if (!u) return ''
  if (/^https?:\/\//i.test(u)) return u
  const base = import.meta.env.VITE_API_BASE || ''
  return `${base}${u}`
}

onMounted(async () => {
  loading.value = true
  try {
    data.value = await api.cooperation()
    loadError.value = false
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
})
</script>
