import { createApp } from "vue"
import App from "./App.vue"
import ComfyuiManagerWindow from "./views/ComfyuiManagerWindow.vue"
import "ant-design-vue/dist/reset.css"
import "./style.css"
import "./media.css"
import "./retry.css"
import "./styles/global.css"

const params = new URLSearchParams(window.location.search)

if (params.get("view") === "comfyui-manager") {
  document.body.classList.add("manager-window-body")
  createApp(ComfyuiManagerWindow, { url: params.get("url") ?? "" }).mount("#app")
} else {
  createApp(App).mount("#app")
}
