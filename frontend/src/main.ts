import { createApp } from "vue"
import App from "./App.vue"
import ComfyuiManagerWindow from "./views/ComfyuiManagerWindow.vue"
import "ant-design-vue/dist/reset.css"
import "./style.css"
import "./media.css"
import "./retry.css"
import "./styles/global.css"

type ManagerWindow = Window & {
  __COMFYUI_MANAGER_URL__?: string
}

const managerUrl = (window as ManagerWindow).__COMFYUI_MANAGER_URL__

if (managerUrl) {
  document.body.classList.add("manager-window-body")
  createApp(ComfyuiManagerWindow, { url: managerUrl }).mount("#app")
} else {
  createApp(App).mount("#app")
}
