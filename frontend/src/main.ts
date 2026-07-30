import { createApp } from "vue"
import App from "./App.vue"
import { prepareDesktopAgent, recordDesktopStartupError } from "./lib/desktop"
import "./style.css"
import "./media.css"
import "./retry.css"

async function bootstrap() {
  await prepareDesktopAgent().catch(recordDesktopStartupError)
  createApp(App).mount("#app")
}

void bootstrap()
