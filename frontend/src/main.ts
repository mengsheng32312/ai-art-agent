import { createApp } from "vue"
import { createPinia } from "pinia"
import "ant-design-vue/dist/reset.css"
import App from "./App.vue"
import "./style.css"

createApp(App).use(createPinia()).mount("#app")
