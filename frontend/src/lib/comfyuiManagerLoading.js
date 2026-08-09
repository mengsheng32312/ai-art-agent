(function () {
  const overlayId = "ai-art-agent-manager-loading"

  window.__installComfyuiManagerLoading = function () {
    window.__disposeComfyuiManagerLoading?.()

    const host = document.body || document.documentElement
    if (!host) {
      const installWhenReady = () => window.__installComfyuiManagerLoading()
      document.addEventListener("DOMContentLoaded", installWhenReady, { once: true })
      window.__disposeComfyuiManagerLoading = () => {
        document.removeEventListener("DOMContentLoaded", installWhenReady)
      }
      return
    }

    let observer
    let timeoutId
    let settled = false
    const overlay = document.createElement("div")
    overlay.id = overlayId
    overlay.setAttribute("role", "status")
    overlay.setAttribute("aria-live", "polite")
    const styleMarkup = `
      <style>
        #${overlayId} {
          position: fixed;
          inset: 0;
          z-index: 2147483647;
          display: grid;
          place-items: center;
          background: #f5f5f7;
          color: #1d1d1f;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        #${overlayId} .manager-loading-card {
          min-width: 280px;
          padding: 28px 32px;
          border: 1px solid rgba(0, 0, 0, 0.08);
          border-radius: 18px;
          background: #fff;
          box-shadow: 0 12px 36px rgba(0, 0, 0, 0.08);
          text-align: center;
        }
        #${overlayId} strong { display: block; font-size: 16px; }
        #${overlayId} p { margin: 8px 0 0; color: #6e6e73; font-size: 12px; }
        #${overlayId} .manager-loading-dots {
          display: flex;
          justify-content: center;
          gap: 6px;
          margin-bottom: 16px;
        }
        #${overlayId} .manager-loading-dots span {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #007aff;
          animation: manager-loading-pulse 1.2s ease-in-out infinite;
        }
        #${overlayId} .manager-loading-dots span:nth-child(2) { animation-delay: 0.15s; }
        #${overlayId} .manager-loading-dots span:nth-child(3) { animation-delay: 0.3s; }
        #${overlayId} button {
          margin-top: 16px;
          padding: 8px 18px;
          border: 0;
          border-radius: 10px;
          background: #007aff;
          color: #fff;
          cursor: pointer;
          font-size: 14px;
        }
        @keyframes manager-loading-pulse {
          0%, 60%, 100% { opacity: 0.35; transform: translateY(0); }
          30% { opacity: 1; transform: translateY(-3px); }
        }
      </style>
    `
    overlay.innerHTML = `${styleMarkup}
      <div class="manager-loading-card">
        <div class="manager-loading-dots" aria-hidden="true"><span></span><span></span><span></span></div>
        <strong>ComfyUI 模型库正在加载</strong>
        <p>首次打开可能需要几秒钟</p>
      </div>
    `
    host.prepend(overlay)

    const cleanupListeners = () => {
      observer?.disconnect()
      window.clearTimeout(timeoutId)
      window.removeEventListener("error", handleResourceError, true)
    }
    const dispose = () => {
      cleanupListeners()
      overlay.remove()
    }
    const finish = () => {
      if (settled) return
      settled = true
      dispose()
    }
    const showError = (title, detail) => {
      if (settled) return
      settled = true
      cleanupListeners()
      overlay.setAttribute("role", "alert")
      overlay.innerHTML = `${styleMarkup}
        <div class="manager-loading-card">
          <strong>${title}</strong>
          <p>${detail}</p>
          <button type="button">重新加载</button>
        </div>
      `
      overlay.querySelector("button")?.addEventListener("click", () => window.location.reload())
    }
    function handleResourceError(event) {
      if (event.target instanceof HTMLScriptElement || event.target instanceof HTMLLinkElement) {
        showError("ComfyUI 模型库加载失败", "页面资源加载失败，请检查 ComfyUI 是否正常运行")
      }
    }
    const isReady = () => Boolean(document.querySelector("main button"))

    window.addEventListener("error", handleResourceError, true)
    observer = new MutationObserver(() => {
      if (isReady()) finish()
    })
    observer.observe(document.documentElement, { childList: true, subtree: true })
    timeoutId = window.setTimeout(() => {
      showError("ComfyUI 模型库加载超时", "请确认 ComfyUI 页面可以正常访问后重试")
    }, 30_000)
    if (isReady()) finish()

    window.__disposeComfyuiManagerLoading = dispose
  }

  window.__installComfyuiManagerLoading()
})()
