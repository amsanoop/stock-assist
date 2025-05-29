window.deferredPrompt = null;

window.addEventListener("load", () => {
  /**
   * Registers the service worker if it is supported by the navigator.
   */
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .register("/js/service-worker.js")
      .then((registration) => {
        console.log(
          "ServiceWorker registration successful with scope: ",
          registration.scope
        );
      })
      .catch((error) => {
        console.log("ServiceWorker registration failed: ", error);
      });
  }
});

window.addEventListener("beforeinstallprompt", (e) => {
  /**
   * Handles the beforeinstallprompt event to defer the installation prompt.
   * @param {Event} e - The beforeinstallprompt event.
   */
  e.preventDefault();
  window.deferredPrompt = e;
  console.log("Install prompt deferred");
});

window.addEventListener("appinstalled", () => {
  /**
   * Handles the appinstalled event to clear the deferred prompt.
   */
  window.deferredPrompt = null;
  console.log("PWA was installed");
});