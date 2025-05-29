document.addEventListener("DOMContentLoaded", () => {
  const announcementKey = "pwa-announcement-dismissed";
  const announcementVersion = "1.0.0";
  const storedVersion = localStorage.getItem(announcementKey);

  if (storedVersion !== announcementVersion) {
    showAnnouncement();
  }

  function showAnnouncement() {
    /**
     * Displays the PWA announcement banner.
     */
    const announcement = document.createElement("div");
    announcement.className = "pwa-announcement";
    announcement.innerHTML = `
      <div class="pwa-announcement-content">
        <div class="pwa-announcement-icon">🚀</div>
        <div class="pwa-announcement-text">
          <div class="pwa-announcement-title">StockAssist is now available as an app!</div>
          <div class="pwa-announcement-description">Install it for a better experience and offline access.</div>
        </div>
        <div class="pwa-announcement-actions">
          <button class="pwa-announcement-button" id="announcement-install">Install Now</button>
          <button class="pwa-announcement-close" id="announcement-close">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(announcement);

    const installButton = document.getElementById("announcement-install");
    const closeButton = document.getElementById("announcement-close");

    if (installButton) {
      installButton.addEventListener("click", () => {
        localStorage.setItem(announcementKey, announcementVersion);
        announcement.classList.add("pwa-announcement-hidden");
        setTimeout(() => {
          announcement.remove();
        }, 300);

        if (window.deferredPrompt) {
          window.deferredPrompt.prompt();

          window.deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === "accepted") {
              console.log("User accepted the install prompt");
            } else {
              console.log("User dismissed the install prompt");
              showInstallInstructions();
            }
            window.deferredPrompt = null;
          });
        } else {
          showInstallInstructions();
        }
      });
    }

    if (closeButton) {
      closeButton.addEventListener("click", () => {
        localStorage.setItem(announcementKey, announcementVersion);
        announcement.classList.add("pwa-announcement-hidden");
        setTimeout(() => {
          announcement.remove();
        }, 300);
      });
    }
  }

  function showInstallInstructions() {
    /**
     * Displays the installation instructions modal based on the user's platform.
     */
    const modal = document.createElement("div");
    modal.className = "pwa-install-modal";

    const userAgent = navigator.userAgent.toLowerCase();
    let instructions = "";

    if (/iphone|ipad|ipod/.test(userAgent)) {
      instructions = `
        <h3>Install on iOS:</h3>
        <ol>
          <li>Tap the Share button <span class="icon">📤</span> at the bottom of the screen</li>
          <li>Scroll down and tap "Add to Home Screen" <span class="icon">➕</span></li>
          <li>Tap "Add" in the top right corner</li>
        </ol>
      `;
    } else if (/android/.test(userAgent)) {
      instructions = `
        <h3>Install on Android:</h3>
        <ol>
          <li>Tap the menu button <span class="icon">⋮</span> in the top right</li>
          <li>Tap "Add to Home screen"</li>
          <li>Tap "Add" to confirm</li>
        </ol>
      `;
    } else {
      instructions = `
        <h3>Install on Desktop:</h3>
        <ol>
          <li>Click the install icon <span class="icon">⊕</span> in the address bar</li>
          <li>Click "Install" in the dialog that appears</li>
        </ol>
      `;
    }

    modal.innerHTML = `
      <div class="pwa-install-modal-content">
        <div class="pwa-install-modal-header">
          <h2>Install StockAssist</h2>
          <button class="pwa-install-modal-close" id="modal-close">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="pwa-install-modal-body">
          ${instructions}
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    const closeModalButton = document.getElementById("modal-close");
    if (closeModalButton) {
      closeModalButton.addEventListener("click", () => {
        modal.classList.add("pwa-install-modal-hidden");
        setTimeout(() => {
          modal.remove();
        }, 300);
      });
    }

    setTimeout(() => {
      modal.classList.add("pwa-install-modal-visible");
    }, 10);
  }
});