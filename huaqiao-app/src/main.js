import { createApp } from 'vue'
import Vant from 'vant'
import 'vant/lib/index.css'
import '@vant/touch-emulator'
import App from './App.vue'
import './styles.css'

createApp(App).use(Vant).mount('#app')
