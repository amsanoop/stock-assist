function toggleUserMenu() {
  /**
   * Toggles the visibility of the user menu.
   */
  const menu = document.getElementById("userMenu");
  if (!menu) return;
  menu.classList.toggle("hidden");
  menu.classList.toggle("scale-95");
  menu.classList.toggle("opacity-0");
}

function toggleMobileMenu() {
  /**
   * Toggles the visibility of the mobile menu.
   */
  const menu = document.getElementById("mobileMenu");
  const menuIcon = document.getElementById("menuIcon");
  const closeIcon = document.getElementById("closeIcon");

  if (!menu || !menuIcon || !closeIcon) return;

  menu.classList.toggle("hidden");
  menuIcon.classList.toggle("hidden");
  closeIcon.classList.toggle("hidden");
}

function toggleChatWidget() {
  /**
   * Toggles the visibility of the Tawk.to chat widget on mobile.
   */
  if (!Tawk_API) return;

  const chatButton = document.getElementById("chatToggleBtn");
  const chatIcon = document.getElementById("chatToggleIcon");
  const closeIcon = document.getElementById("chatCloseIcon");

  if (chatButton.dataset.state === "visible") {
    Tawk_API.hideWidget();
    chatButton.dataset.state = "hidden";
    chatIcon.classList.remove("hidden");
    closeIcon.classList.add("hidden");
    chatButton.setAttribute("aria-label", "Open support chat");
  } else {
    Tawk_API.showWidget();
    chatButton.dataset.state = "visible";
    chatIcon.classList.add("hidden");
    closeIcon.classList.remove("hidden");
    chatButton.setAttribute("aria-label", "Close support chat");
  }
}

function fixNavbarDisplay() {
  /**
   * Forces desktop navbar to display on larger screens.
   */
  if (window.innerWidth >= 768) {
    const desktopNav = document.querySelector(
      ".flex.sm\\:ml-10.sm\\:space-x-8.hidden.sm\\:hidden.md\\:flex"
    );
    const userMenu = document.querySelector(
      ".flex.sm\\:items-center.sm\\:space-x-6.hidden.sm\\:hidden.md\\:flex"
    );

    if (desktopNav) {
      desktopNav.style.display = "flex";
      desktopNav.classList.remove("hidden");
    }

    if (userMenu) {
      userMenu.style.display = "flex";
      userMenu.classList.remove("hidden");
    }
  }
}

document.addEventListener("click", (event) => {
  /**
   * Closes the user menu when clicking outside the menu and user button.
   * @param {Event} event - The click event.
   */
  const userMenu = document.getElementById("userMenu");
  if (!userMenu) return;

  const userButton = event.target.closest("button");

  if (!userButton && !userMenu.contains(event.target)) {
    userMenu.classList.add("hidden", "scale-95", "opacity-0");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  /**
   * Adds animations to page elements when the DOM is fully loaded.
   */
  const mainContent = document.querySelector("main");
  if (mainContent) {
    mainContent.classList.add("animate-fadeIn");
  }

  fixNavbarDisplay();
  window.addEventListener("resize", fixNavbarDisplay);

  setTimeout(fixNavbarDisplay, 100);

  const buttons = document.querySelectorAll(
    'button:not([type="button"]), .btn-accent'
  );
  buttons.forEach((button) => {
    button.addEventListener("mouseenter", function () {
      this.classList.add("animate-pulse");
    });
    button.addEventListener("mouseleave", function () {
      this.classList.remove("animate-pulse");
    });
  });

  createChatToggleButton();
});

function createChatToggleButton() {
  /**
   * Creates and adds the chat toggle button to the DOM.
   * Now only creates the button for non-mobile devices
   */
  
  // Don't create the floating button on mobile devices
  if (window.innerWidth < 768) {
    return;
  }
  
  const button = document.createElement("button");
  button.id = "chatToggleBtn";
  button.className = "chat-toggle-btn";
  button.setAttribute("aria-label", "Toggle support chat");
  button.dataset.state = "visible";

  const chatSvg = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "svg"
  );
  chatSvg.id = "chatToggleIcon";
  chatSvg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  chatSvg.setAttribute("fill", "none");
  chatSvg.setAttribute("viewBox", "0 0 24 24");
  chatSvg.setAttribute("stroke", "currentColor");
  chatSvg.setAttribute("stroke-width", "2");
  chatSvg.classList.add("hidden");

  const chatPath = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "path"
  );
  chatPath.setAttribute("stroke-linecap", "round");
  chatPath.setAttribute("stroke-linejoin", "round");
  chatPath.setAttribute(
    "d",
    "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
  );

  chatSvg.appendChild(chatPath);

  const closeSvg = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "svg"
  );
  closeSvg.id = "chatCloseIcon";
  closeSvg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  closeSvg.setAttribute("fill", "none");
  closeSvg.setAttribute("viewBox", "0 0 24 24");
  closeSvg.setAttribute("stroke", "currentColor");
  closeSvg.setAttribute("stroke-width", "2");

  const closePath = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "path"
  );
  closePath.setAttribute("stroke-linecap", "round");
  closePath.setAttribute("stroke-linejoin", "round");
  closePath.setAttribute("d", "M6 18L18 6M6 6l12 12");

  closeSvg.appendChild(closePath);

  button.appendChild(chatSvg);
  button.appendChild(closeSvg);

  button.addEventListener("click", toggleChatWidget);

  document.body.appendChild(button);

  const checkTawkInterval = setInterval(() => {
    if (typeof Tawk_API !== "undefined" && Tawk_API.onLoad) {
      clearInterval(checkTawkInterval);

      Tawk_API.onLoad = function () {
        if (window.innerWidth < 768) {
          setTimeout(() => {
            button.click();
          }, 1000);
        }
      };
    }
  }, 300);
}