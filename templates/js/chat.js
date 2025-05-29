const md                  = window.markdownit();
const pendingOperations   = new Set();
let currentChatId         = null;
let currentPage           = 1;
let totalPages            = 1;
let perPage               = 10;
let selectedFiles         = [];
let suggestionTimeout     = null;

const translations = {
  en: {
    noChatsYet: "No chats yet. Start a new conversation!",
    errorLoadingChats: "Error loading chats"
  }
};

function getTranslation(key, lang = 'en') {
  /**
   * Gets a translated string for the given key.
   * @param {string} key - The translation key.
   * @param {string} lang - The language code (defaults to 'en').
   * @returns {string} The translated string or the key if not found.
   */
  const languageTranslations = translations[lang] || translations.en;
  return languageTranslations[key] || key;
}

function showLoader(selector) {
  /**
   * Displays a loading indicator inside the specified element.
   * @param {string} selector - CSS selector for the target element.
   */
  const targetElement = document.querySelector(selector);
  if (!targetElement) {
    console.warn(`showLoader: Element with selector "${selector}" not found.`);
    return;
  }
  hideLoader(selector); 
  
  const loaderDiv = document.createElement('div');
  loaderDiv.className = 'inline-loader flex items-center justify-center gap-2 py-6 text-white/40 absolute inset-0 bg-dark-100/50 z-10';
  loaderDiv.innerHTML = `
      <div class="w-2 h-2 bg-accent/40 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
      <div class="w-2 h-2 bg-accent/40 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
      <div class="w-2 h-2 bg-accent/40 rounded-full animate-bounce"></div>
  `;
  targetElement.style.position = 'relative';
  targetElement.appendChild(loaderDiv);
}

function hideLoader(selector) {
  /**
   * Hides the loading indicator inside the specified element.
   * @param {string} selector - CSS selector for the target element.
   */
  const targetElement = document.querySelector(selector);
  if (!targetElement) {
     console.warn(`hideLoader: Element with selector "${selector}" not found.`);
    return;
  }
  const loader = targetElement.querySelector('.inline-loader');
  if (loader) {
    loader.remove();
  }
}

function showToast(message, type = 'info', duration = 3000) {
  /**
   * Shows a toast notification message.
   * @param {string} message - The message to display.
   * @param {string} type - The type of toast ('info', 'success', 'warning', 'error').
   * @param {number} duration - The duration (in milliseconds) to display the message.
   * @returns {void}
   */
  const toastDiv = document.createElement('div');
  let bgColorClass = 'bg-blue-500/90';
  let iconSvg = `
    <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
    </svg>
  `;

  switch (type) {
    case 'success':
      bgColorClass = 'bg-green-500/90';
      iconSvg = `
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
      `;
      break;
    case 'warning':
      bgColorClass = 'bg-yellow-500/90';
      iconSvg = `
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
             <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>
       `;
      break;
    case 'error':
      bgColorClass = 'bg-red-500/90';
      iconSvg = `
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>
      `;
      break;
  }

  toastDiv.className = `fixed top-4 right-4 ${bgColorClass} text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center gap-3 message-appear`;
  toastDiv.innerHTML = `${iconSvg}<span>${message}</span>`;
  
  document.body.appendChild(toastDiv);
  setTimeout(() => {
    toastDiv.style.opacity = '0';
    toastDiv.style.transform = 'translateY(-20px)';
    toastDiv.style.transition = 'all 0.3s ease-out';
    setTimeout(() => {
      if (toastDiv.parentNode) {
        toastDiv.remove();
      }
    }, 300);
  }, duration);
}

function estimateTokenCount(text) {
  /**
   * Estimates the number of tokens in a text string.
   * @param {string} text - The text to estimate tokens for.
   * @returns {number} The estimated token count.
   */
  if (!text || text.length === 0) {
    return 0;
  }
  
  return Math.ceil(text.length / 4);
}

const languages = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Español' },
  { code: 'fr', name: 'Français' },
  { code: 'de', name: 'Deutsch' },
  { code: 'it', name: 'Italiano' },
  { code: 'pt', name: 'Português' },
  { code: 'ru', name: 'Русский' },
  { code: 'zh', name: '中文' },
  { code: 'ja', name: '日本語' },
  { code: 'ko', name: '한국어' },
  { code: 'ar', name: 'العربية' },
  { code: 'hi', name: 'हिन्दी' },
  { code: 'nl', name: 'Nederlands' },
  { code: 'sv', name: 'Svenska' },
  { code: 'tr', name: 'Türkçe' },
  { code: 'pl', name: 'Polski' },
  { code: 'el', name: 'Ελληνικά' },
  { code: 'id', name: 'Bahasa Indonesia' },
  { code: 'ms', name: 'Bahasa Melayu' },
  { code: 'th', name: 'ภาษาไทย' },
  { code: 'vi', name: 'Tiếng Việt' },
  { code: 'uk', name: 'Українська' },
  { code: 'ro', name: 'Română' },
  { code: 'cs', name: 'Čeština' },
  { code: 'da', name: 'Dansk' },
  { code: 'fi', name: 'Suomi' },
  { code: 'no', name: 'Norsk' },
  { code: 'hu', name: 'Magyar' },
  { code: 'sk', name: 'Slovenčina' },
  { code: 'bg', name: 'Български' },
  { code: 'hr', name: 'Hrvatski' },
  { code: 'lt', name: 'Lietuvių' },
  { code: 'lv', name: 'Latviešu' },
  { code: 'et', name: 'Eesti' },
  { code: 'sr', name: 'Српски' },
  { code: 'sl', name: 'Slovenščina' },
  { code: 'sq', name: 'Shqip' },
  { code: 'mk', name: 'Македонски' },
  { code: 'be', name: 'Беларуская' },
  { code: 'az', name: 'Azərbaycan' },
  { code: 'ka', name: 'ქართული' },
  { code: 'hy', name: 'Հայերեն' },
  { code: 'kk', name: 'Қазақ тілі' },
  { code: 'ky', name: 'Кыргызча' },
  { code: 'tg', name: 'Тоҷикӣ' },
  { code: 'tk', name: 'Türkmen dili' },
  { code: 'uz', name: 'Oʻzbek tili' },
  { code: 'mn', name: 'Монгол' },
  { code: 'ps', name: 'پښتو' },
  { code: 'ur', name: 'اردو' },
  { code: 'fa', name: 'فارسی' },
  { code: 'am', name: 'አማርኛ' },
  { code: 'sw', name: 'Kiswahili' },
  { code: 'xh', name: 'isiXhosa' },
  { code: 'zu', name: 'isiZulu' },
  { code: 'af', name: 'Afrikaans' },
  { code: 'ga', name: 'Gaeilge' },
  { code: 'cy', name: 'Cymraeg' },
  { code: 'lb', name: 'Lëtzebuergesch' },
  { code: 'mt', name: 'Malti' },
  { code: 'is', name: 'Íslenska' },
  { code: 'yi', name: 'ייִדיש' },
  { code: 'eo', name: 'Esperanto' },
  { code: 'eu', name: 'Euskara' },
  { code: 'gl', name: 'Galego' },
  { code: 'ca', name: 'Català' },
  { code: 'oc', name: 'Occitan' },
  { code: 'co', name: 'Corsu' },
  { code: 'gd', name: 'Gàidhlig' },
  { code: 'br', name: 'Brezhoneg' },
  { code: 'fy', name: 'Frysk' },
  { code: 'sc', name: 'Sardu' },
  { code: 'rm', name: 'Rumantsch' },
  { code: 'la', name: 'Latina' },
];

function getUserLanguagePreference() {
  /**
   * Fetches the user's language preference from the server.
   * @returns {Promise<string>} The language code of the user's preference.
   */
  return fetch('/api/user/language')
    .then((response) => response.json())
    .then((data) => data.language)
    .catch((error) => {
      console.error('Error getting language preference:', error);
      return 'en';
    });
}

function setUserLanguagePreference(languageCode) {
  /**
   * Sets the user's language preference on the server.
   * @param {string} languageCode - The language code to set as the user's preference.
   * @returns {Promise<void>} Resolves when the preference is set.
   */
  return fetch('/api/user/language', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ language: languageCode }),
  })
    .then((response) => response.json())
    .catch((error) => {
      console.error('Error setting language preference:', error);
      showError('Failed to update language preference');
    });
}

function getBrowserLanguages() {
  /**
   * Retrieves the languages preferred by the user's browser.
   * @returns {string[]} An array of language codes preferred by the browser.
   */
  const browserLanguages = [];
  if (navigator.languages && navigator.languages.length) {
    navigator.languages.forEach((lang) => {
      const baseCode = lang.split('-')[0].toLowerCase();
      if (!browserLanguages.includes(baseCode)) {
        browserLanguages.push(baseCode);
      }
    });
  } else {
    const lang = (navigator.language || navigator.userLanguage || 'en').split('-')[0].toLowerCase();
    browserLanguages.push(lang);
  }
  return browserLanguages;
}

function initializeLanguageSelector() {
  /**
   * Initializes the language selector dropdown and sets up event listeners.
   * @returns {void}
   */
  const languageSelector = document.getElementById('languageSelector');
  const languageDropdown = document.getElementById('languageDropdown');
  const currentLanguageSpan = document.getElementById('currentLanguage');
  const browserLanguages = getBrowserLanguages();
  const sortedLanguages = [...languages].sort((a, b) => {
    const aInBrowser = browserLanguages.includes(a.code);
    const bInBrowser = browserLanguages.includes(b.code);
    if (aInBrowser && !bInBrowser) return -1;
    if (!aInBrowser && bInBrowser) return 1;
    return a.name.localeCompare(b.name);
  });

  languageDropdown.innerHTML = sortedLanguages
    .map(
      (lang) =>
        `<button data-lang-code="${lang.code}" class="language-option w-full text-left px-4 py-2 hover:bg-accent/10 transition-colors text-sm ${
          browserLanguages.includes(lang.code) ? 'font-medium text-accent' : 'text-white/80'
        }">${lang.name}</button>`
    )
    .join('');

  languageSelector.addEventListener('click', function (e) {
    e.stopPropagation();
    languageDropdown.classList.toggle('hidden');
  });

  document.addEventListener('click', function () {
    languageDropdown.classList.add('hidden');
  });

  document.querySelectorAll('.language-option').forEach((option) => {
    option.addEventListener('click', function (e) {
      e.stopPropagation();
      const langCode = this.getAttribute('data-lang-code');
      const langName = this.textContent;
      currentLanguageSpan.textContent = langName;
      languageDropdown.classList.add('hidden');
      setUserLanguagePreference(langCode);
    });
  });

  getUserLanguagePreference().then((languageCode) => {
    const language = languages.find((lang) => lang.code === languageCode) || languages[0];
    currentLanguageSpan.textContent = language.name;
  });
}

function debounce(func, wait) {
  /**
   * Creates a debounced version of a function that delays its execution.
   * @param {Function} func - The function to debounce.
   * @param {number} wait - The number of milliseconds to delay.
   * @returns {Function} The debounced function.
   */
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

function handleResize() {
  /**
   * Handles the resizing of the sidebar based on the window width.
   * @returns {void}
   */
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  
  if (!sidebar) return;
  
  if (window.innerWidth >= 768) {
    sidebar.classList.remove('-translate-x-full');
    
    if (backdrop) {
      backdrop.remove();
    }
    
    document.body.style.overflow = '';
  } 
  else {
    sidebar.classList.add('-translate-x-full');
  }
}

window.addEventListener('resize', debounce(handleResize, 100));
document.getElementById('mobileSidebarToggle').addEventListener('click', function () {
  const sidebar = document.getElementById('sidebar');
  const openIcon = document.getElementById('sidebarOpenIcon');
  const closeIcon = document.getElementById('sidebarCloseIcon');
  const isSidebarVisible = !sidebar.classList.contains('-translate-x-full');
  if (!isSidebarVisible) {
    sidebar.classList.remove('-translate-x-full');
    openIcon.classList.add('hidden');
    closeIcon.classList.remove('hidden');
    const backdrop = document.createElement('div');
    backdrop.id = 'sidebarBackdrop';
    backdrop.className = 'inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden opacity-0 transition-opacity duration-300';
    backdrop.onclick = closeSidebar;
    document.body.appendChild(backdrop);
    requestAnimationFrame(() => {
      backdrop.classList.add('opacity-100');
    });
    document.body.style.overflow = 'hidden';
  } else {
    closeSidebar();
  }
});

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    
    if (sidebar) {
        sidebar.classList.add('-translate-x-full');
        
        if (backdrop) {
            backdrop.classList.remove('opacity-100');
            setTimeout(() => {
                backdrop.classList.add('hidden');
                document.body.style.overflow = '';
            }, 300);
        }
        
        const openIcon = document.getElementById('sidebarOpenIcon');
        const closeIcon = document.getElementById('sidebarCloseIcon');
        if (openIcon && closeIcon) {
            openIcon.classList.remove('hidden');
            closeIcon.classList.add('hidden');
        }
    }
}

let lastActiveTab = 'chat';

/**
 * Toggles the sidebar visibility on mobile devices.
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    let backdrop = document.getElementById('sidebarBackdrop');
    
    if (sidebar) {
        const isHidden = sidebar.classList.contains('-translate-x-full');
        
        sidebar.classList.toggle('-translate-x-full');
        
        if (isHidden) {
            if (!backdrop) {
                backdrop = document.createElement('div');
                backdrop.id = 'sidebarBackdrop';
                backdrop.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden opacity-0 transition-opacity duration-300';
                document.body.appendChild(backdrop);
                
                backdrop.addEventListener('click', function(e) {
                    e.preventDefault();
                    closeSidebar();
                });
            }
            
            backdrop.classList.remove('hidden');
            
            setTimeout(() => {
                backdrop.classList.add('opacity-100');
            }, 10);
            
            document.body.style.overflow = 'hidden';
            
            setTimeout(() => {
                if (typeof showTabFunction === 'function') {
                    showTabFunction(lastActiveTab);
                } else if (typeof window.showSidebarTab === 'function') {
                    window.showSidebarTab(lastActiveTab);
                }
            }, 50);
        } else {
            
            if (document.getElementById('watchlistTabBtn').classList.contains('chat-tab-active')) {
                lastActiveTab = 'watchlist';
            } else {
                lastActiveTab = 'chat';
            }
            
            if (backdrop) {
                backdrop.classList.remove('opacity-100');
                setTimeout(() => {
                    backdrop.classList.add('hidden');
                    document.body.style.overflow = '';
                }, 300);
            }
        }
        
        const openIcon = document.getElementById('sidebarOpenIcon');
        const closeIcon = document.getElementById('sidebarCloseIcon');
        if (openIcon && closeIcon) {
            openIcon.classList.toggle('hidden');
            closeIcon.classList.toggle('hidden');
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
    if (mobileSidebarToggle) {
        mobileSidebarToggle.addEventListener('click', toggleSidebar);
    }
    
    const backdrop = document.getElementById('sidebarBackdrop');
    if (backdrop) {
        backdrop.addEventListener('click', closeSidebar);
    }
    
    initializeMobileTabs();
});

let showTabFunction;

function initializeMobileTabs() {
    /**
     * Initializes mobile tab navigation
     */
    const chatTabBtn = document.getElementById('chatTabBtn');
    const watchlistTabBtn = document.getElementById('watchlistTabBtn');
    
    if (chatTabBtn && watchlistTabBtn) {
        chatTabBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showTab('chat');
        });
        watchlistTabBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showTab('watchlist');
        });
    }
    
    function showTab(tabName) {
        console.log(`Showing tab: ${tabName}`);
        const sidebar = document.getElementById('sidebar');
        if (!sidebar || !chatTabBtn || !watchlistTabBtn) {
            console.error("Required elements for tab navigation not found");
            return;
        }

        lastActiveTab = tabName;

        const chatSections = sidebar.querySelectorAll('.chat-section');
        const watchlistSections = sidebar.querySelectorAll('.watchlist-section');
        const tabButtonsContainer = sidebar.querySelector('.always-visible');

        if (chatSections.length === 0) {
            console.warn("No '.chat-section' elements found within the sidebar.");
        }
        if (watchlistSections.length === 0) {
            console.warn("No '.watchlist-section' elements found within the sidebar.");
        }

        if (tabName === 'chat') {
            chatTabBtn.classList.add('bg-accent/20', 'border-accent/30', 'chat-tab-active');
            chatTabBtn.classList.remove('text-white/60', 'hover:text-white', 'hover:bg-dark-300/50');

            watchlistTabBtn.classList.remove('bg-accent/20', 'border-accent/30', 'chat-tab-active');
            watchlistTabBtn.classList.add('text-white/60', 'hover:text-white', 'hover:bg-dark-300/50');

            chatSections.forEach(el => {
                el.classList.remove('hidden');
                el.style.display = '';
                console.log('Showing chat section:', el);
            });
            watchlistSections.forEach(el => {
                el.classList.add('hidden');
                console.log('Hiding watchlist section:', el);
            });
            
            if (document.getElementById('chatList').children.length === 0) {
                console.log('No chats loaded, loading chats...');
                loadChats();
            }
        } else {
            watchlistTabBtn.classList.add('bg-accent/20', 'border-accent/30', 'chat-tab-active');
            watchlistTabBtn.classList.remove('text-white/60', 'hover:text-white', 'hover:bg-dark-300/50');

            chatTabBtn.classList.remove('bg-accent/20', 'border-accent/30', 'chat-tab-active');
            chatTabBtn.classList.add('text-white/60', 'hover:text-white', 'hover:bg-dark-300/50');

            chatSections.forEach(el => {
                el.classList.add('hidden');
                el.style.display = 'none';
                console.log('Hiding chat section:', el);
            });
            watchlistSections.forEach(el => {
                el.classList.remove('hidden');
                el.style.display = 'block';
                console.log('Showing watchlist section:', el);
            });

            loadWatchlist();
        }
        
        if (tabButtonsContainer) {
            tabButtonsContainer.style.display = 'flex';
        }
    }
    
    showTabFunction = showTab;
    
    window.showSidebarTab = showTab;
}

function showMobileWatchlist() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar && sidebar.classList.contains('-translate-x-full')) {
        toggleSidebar();
        
        setTimeout(() => {
            if (typeof showTabFunction === 'function') {
                showTabFunction('watchlist');
            } else if (typeof window.showSidebarTab === 'function') {
                window.showSidebarTab('watchlist');
            }
        }, 300);
    } else if (typeof showTabFunction === 'function') {
        showTabFunction('watchlist');
    } else if (typeof window.showSidebarTab === 'function') {
        window.showSidebarTab('watchlist');
    }
}

document.addEventListener('click', function (event) {
  const sidebar = document.getElementById('sidebar');
  const toggleButton = document.getElementById('mobileSidebarToggle');
  const chatContainer = document.querySelector('.flex-1.flex.flex-col.glass-effect');
  
  if (sidebar && 
      !sidebar.contains(event.target) && 
      !toggleButton.contains(event.target) &&
      window.innerWidth < 768 && 
      !sidebar.classList.contains('-translate-x-full')) {
    
    if (chatContainer && chatContainer.contains(event.target)) {
      return;
    }
    
    setTimeout(() => {
      closeSidebar();
    }, 100);
  }
});

document.addEventListener('keydown', function (event) {
  if (event.key === 'Escape') {
    closeSidebar();
  }
});

function createChatElement(chat) {
  /**
   * Creates an element for displaying a chat in the sidebar.
   * @param {Object} chat - The chat object to create an element for.
   * @returns {HTMLElement} The created chat element.
   */
  const chatElement = document.createElement('div');
  chatElement.className = 'chat-list-item relative flex items-center p-3 bg-dark-300/30 hover:bg-dark-300/50 rounded-lg border border-transparent transition-colors cursor-pointer group';
  chatElement.setAttribute('data-chat-id', chat.id);
  
  const displayDate = new Date(chat.created_at);
  const dateString = displayDate.toLocaleDateString(undefined, { 
    month: 'short', 
    day: 'numeric',
    year: displayDate.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined 
  });
  
  chatElement.innerHTML = `
    <div class="flex-1 overflow-hidden">
      <div class="flex items-center justify-between">
        <h4 class="font-medium text-white truncate max-w-[140px]">${chat.title || 'Untitled Chat'}</h4>
        <span class="text-white/40 text-xs">${dateString}</span>
      </div>
      <p class="text-white/60 text-xs truncate">${chat.last_message || 'No messages yet'}</p>
    </div>
    <div class="absolute right-2 top-2 hidden group-hover:flex items-center gap-1">
      <button onclick="event.stopPropagation(); deleteChat(${chat.id})" class="p-1 text-white/40 hover:text-red-400 transition-colors rounded-full hover:bg-red-500/10">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
        </svg>
      </button>
    </div>
  `;
  
  chatElement.addEventListener('click', () => openChat(chat.id));
  
  const currentChatId = document.getElementById('chat_id').value;
  if (currentChatId && parseInt(currentChatId) === chat.id) {
    chatElement.classList.add('bg-accent/10', 'border-accent/30');
  }
  
  return chatElement;
}

function loadWatchlist() {
  /**
   * Loads the user's watchlist from the server and displays it within the sidebar.
   * @returns {void}
   */
  
  const watchlistBtn = document.getElementById('watchlistTabBtn');
  if (window.innerWidth < 768 && watchlistBtn && watchlistBtn.classList.contains('chat-tab-active')) {
    console.log("Forcing watchlist visibility for mobile");
    sidebar.querySelectorAll('.watchlist-section').forEach(el => {
      el.style.display = 'block';
      el.classList.remove('hidden');
    });
  }
  
  const watchlistDiv = document.getElementById('watchlist');
  
  if (!watchlistDiv) {
    console.error("Watchlist div not found! Critical error.");
    return;
  }
  
  console.log("Found watchlist div:", watchlistDiv);
  
  watchlistDiv.classList.remove('hidden');
  
  watchlistDiv.innerHTML = `
    <div class="flex items-center justify-center gap-2 py-6 text-white/40">
        <div class="w-2 h-2 bg-accent/40 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
        <div class="w-2 h-2 bg-accent/40 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
        <div class="w-2 h-2 bg-accent/40 rounded-full animate-bounce"></div>
    </div>
    `;
    
  console.log("Loading watchlist data for:", watchlistDiv);
  fetch('/api/watchlist')
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load watchlist: ${response.status} ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      console.log("Watchlist data:", data);
      
      watchlistDiv.classList.remove('hidden');
      if (window.getComputedStyle(watchlistDiv).display === 'none') {
        watchlistDiv.style.display = 'block';
      }
      
      if (data.length === 0) {
        watchlistDiv.innerHTML =
          '<div class="text-white/40 text-sm p-4 bg-dark-300/30 rounded-lg border border-white/5 text-center">No stocks in watchlist</div>';
        return;
      }
      
      const html = data
        .map(
          (stock) => `
            <div class="watchlist-item flex justify-between items-center p-3 bg-dark-300/30 hover:bg-dark-300/50 rounded-lg border border-transparent transition-all duration-200 mb-2 relative overflow-hidden">
                <div class="flex-1">
                    <span class="font-medium text-white text-base flex items-center">
                        <svg class="w-4 h-4 mr-1.5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path>
                        </svg>
                        ${stock.symbol}
                    </span>
                    <p class="text-sm text-white/40">${new Date(stock.added_at).toLocaleDateString()}</p>
                    <div class="absolute bottom-0 left-0 w-full h-0.5 bg-gradient-to-r from-accent/5 via-accent/30 to-accent/5"></div>
                </div>
                <button onclick="addToMessage('${stock.symbol}')" 
                        class="text-accent hover:text-accent-light transition-colors p-2 rounded-full hover:bg-accent/10 flex-shrink-0 transform hover:scale-110 transition-transform">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                    </svg>
                </button>
            </div>
        `
        )
        .join('');
        
      watchlistDiv.innerHTML = html;
      
      console.log(`Watchlist updated with ${data.length} items, visibility: ${window.getComputedStyle(watchlistDiv).display}`);
      
      const items = watchlistDiv.querySelectorAll('.watchlist-item');
      items.forEach((item, index) => {
          item.style.opacity = '0';
          item.style.transform = 'translateY(10px)';
          
          setTimeout(() => {
              item.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
              item.style.opacity = '1';
              item.style.transform = 'translateY(0)';
          }, 50 * index);
      });
      
      if (watchlistBtn && watchlistBtn.classList.contains('chat-tab-active')) {
        setTimeout(() => {
          if (window.getComputedStyle(watchlistDiv).display === 'none') {
            console.log("EMERGENCY FIX: Forcing watchlist visible with stylesheet");
            document.head.insertAdjacentHTML('beforeend', 
              `<style>
                #watchlist { 
                  display: block !important; 
                  visibility: visible !important;
                }
              </style>`);
          }
        }, 100);
      }
    })
    .catch((error) => {
      console.error('Error loading watchlist:', error);
      watchlistDiv.innerHTML =
        '<div class="text-red-400 text-sm p-4 bg-red-500/10 rounded-lg border border-red-500/20 text-center">Error loading watchlist</div>';
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const isMobile = window.innerWidth < 768;
    if (isMobile) {
        const watchlistTabBtn = document.getElementById('watchlistTabBtn');
        
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            sidebar.classList.add('touch-auto');
        }
    }
    
    loadWatchlist();
});

async function loadChats(page = 1, refresh = false) {
  /**
   * Loads the user's chats from the server.
   * Displays them in the chats sidebar.
   * @param {number} page - The page number to load
   * @param {boolean} refresh - Whether to force a refresh
   */
  try {
    console.log("Loading chats... Page:", page, "Refresh:", refresh);
    
    if (refresh) {
      currentPage = 1;
    } else {
      currentPage = page;
    }
    
    showLoader("#chatList");
    const response = await fetch(`/api/chats?page=${currentPage}&per_page=${perPage}${refresh ? '&bypass_cache=1' : ''}`);
    
    if (!response.ok) {
      throw new Error(`Error loading chats: ${response.status}`);
    }
    
    const data = await response.json();
    console.log("Chats loaded:", data);
    const chats = data.chats || [];
    totalPages = data.pagination.pages || 1;
    
    const chatsList = document.getElementById("chatList");
    if (!chatsList) {
      console.error("Chat list element not found");
      return;
    }
    
    if (currentPage === 1 || refresh) {
      chatsList.innerHTML = "";
    }
    
    if (chats.length === 0 && currentPage === 1) {
      chatsList.innerHTML = `
        <div class="p-4 text-center text-white/60">
          <svg class="w-12 h-12 mx-auto mb-2 text-accent/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
          </svg>
          <p>${getTranslation('noChatsYet')}</p>
        </div>
      `;
    } else {
      chats.forEach(chat => {
        const chatElement = createChatElement(chat);
        chatsList.appendChild(chatElement);
      });
    }
    
    const loadMoreButton = document.getElementById("load-more-chats");
    if (loadMoreButton) {
      if (currentPage < totalPages) {
        loadMoreButton.style.display = "block";
      } else {
        loadMoreButton.style.display = "none";
      }
    }
    
    hideLoader("#chatList");
    
    if (document.getElementById('chatTabBtn').classList.contains('chat-tab-active')) {
      document.querySelectorAll('.chat-section').forEach(el => {
        el.classList.remove('hidden');
        el.style.display = '';
      });
    }
  } catch (error) {
    console.error("Failed to load chats:", error);
    showToast(getTranslation('errorLoadingChats'), "error");
    hideLoader("#chatList");
    
    const chatsList = document.getElementById("chatList");
    if (chatsList && (!chatsList.innerHTML || chatsList.innerHTML.trim() === "")) {
      setTimeout(() => {
        createNewChat();
      }, 1000);
    }
  }
}

function openChat(chatId) {
  /**
   * Opens a chat and loads its messages.
   * @param {string} chatId - The ID of the chat to open.
   * @returns {void}
   */
  stopSpeaking();

  fetch(`/api/chats/${chatId}`)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load chat: ${response.status} ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      const chatIdInput = document.getElementById('chat_id');
      if (chatIdInput) {
        chatIdInput.value = data.id;
        window.history.pushState({}, '', `/chat?chat_id=${data.id}`);
      }
      const chatMessages = document.getElementById('chatMessages');
      if (!chatMessages) return;
      chatMessages.innerHTML = '';
      if (data.messages && data.messages.length > 0) {
        data.messages.forEach((msg) => {
          appendMessage(msg.content, msg.is_user, false, msg.images);
        });
      } else {
        let message = 'No messages yet. Start a conversation!';
        if (data.title === 'Untitled Chat') {
          message = 'New chat started. Ask something about stocks!';
        }
        chatMessages.innerHTML = `<div class="text-center text-white/60 p-8 flex flex-col items-center"><svg class="w-12 h-12 text-accent/40 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg><span>${message}</span></div>`;
      }
      chatMessages.scrollTop = chatMessages.scrollHeight;

      if (window.innerWidth < 768) {
        closeSidebar();
      }
    })
    .catch((error) => {
      console.error('Error loading chat messages:', error);
      const chatMessages = document.getElementById('chatMessages');
      if (chatMessages) {
        chatMessages.innerHTML =
          '<div class="text-center text-red-400 p-8 bg-red-500/10 rounded-lg border border-red-500/20 m-4"><svg class="w-12 h-12 text-red-400/40 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg><p>Error loading chat messages. Please try again.</p></div>';
      }
    });
}

function addToMessage(symbol) {
  /**
   * Adds a stock symbol to the message input field.
   * @param {string} symbol - The stock symbol to add.
   * @returns {void}
   */
  const input = document.getElementById('stockSymbols');
  const symbols = input.value.split(',').map((s) => s.trim()).filter((s) => s);
  if (!symbols.includes(symbol)) {
    symbols.push(symbol);
    input.value = symbols.join(', ');
    input.classList.add('border-accent');
    setTimeout(() => input.classList.remove('border-accent'), 800);
  }
}

function speakText(text) {
  /**
   * Speaks the given text using the browser's text-to-speech functionality.
   * @param {string} text - The text to speak.
   * @returns {void}
   */
  if (!text || text.trim() === '') {
    return;
  }

  if (!window.speechSynthesisSupported) {
    showError('Text-to-speech is not supported in your browser');
    return;
  }

  const maxChunkLength = 200;
  const textChunks = [];

  const sentences = text.split(/(?<=[.!?])\s+/);
  let currentChunk = '';

  for (const sentence of sentences) {
    if (currentChunk.length + sentence.length < maxChunkLength) {
      currentChunk += (currentChunk ? ' ' : '') + sentence;
    } else {
      if (currentChunk) {
        textChunks.push(currentChunk);
      }
      currentChunk = sentence;
    }
  }

  if (currentChunk) {
    textChunks.push(currentChunk);
  }

  let voices = window.speechSynthesis.getVoices();

  if (voices.length === 0) {
    setTimeout(() => {
      voices = window.speechSynthesis.getVoices();
      speakTextChunks(textChunks, voices);
    }, 100);
  } else {
    speakTextChunks(textChunks, voices);
  }
}

function speakTextChunks(textChunks, voices) {
  /**
   * Speaks the given text chunks using the browser's text-to-speech functionality.
   * @param {string[]} textChunks - An array of text chunks to speak.
   * @param {SpeechSynthesisVoice[]} voices - An array of available voices.
   * @returns {void}
   */
  if (!textChunks || textChunks.length === 0) {
    return;
  }

  stopSpeaking();

  const buttons = document.querySelectorAll('.read-aloud-btn');
  buttons.forEach((btn) => btn.classList.add('speaking'));

  let voice = null;

  const userLang = navigator.language || navigator.userLanguage || 'en-US';
  const langCode = userLang.split('-')[0];

  voice = voices.find((v) => v.lang.startsWith(langCode) && v.name.toLowerCase().includes('female'));

  if (!voice) {
    voice = voices.find((v) => v.name.toLowerCase().includes('female'));
  }

  if (!voice) {
    voice = voices.find((v) => v.lang.startsWith(langCode));
  }

  if (!voice && voices.length > 0) {
    voice = voices[0];
  }

  if (!voice) {
    showError('No voices available for text-to-speech');
    buttons.forEach((btn) => btn.classList.remove('speaking'));
    return;
  }

  let currentChunkIndex = 0;
  let resumeInterval = null;
  let timeoutId = null;

  function resumeSpeechSynthesis() {
    if (document.querySelector('.read-aloud-btn.speaking')) {
      window.speechSynthesis.pause();
      window.speechSynthesis.resume();
    } else {
      clearInterval(resumeInterval);
      resumeInterval = null;
    }
  }

  resumeInterval = setInterval(resumeSpeechSynthesis, 5000);

  function speakNextChunk() {
    if (currentChunkIndex >= textChunks.length) {
      buttons.forEach((btn) => btn.classList.remove('speaking'));
      clearInterval(resumeInterval);
      return;
    }

    const chunk = textChunks[currentChunkIndex];

    const utterance = new SpeechSynthesisUtterance(chunk);
    utterance.voice = voice;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onend = function () {
      clearTimeout(timeoutId);
      currentChunkIndex++;
      speakNextChunk();
    };

    utterance.onerror = function (event) {
      clearTimeout(timeoutId);

      if (event.error === 'interrupted' || event.error === 'canceled') {
        // Do nothing
      } else {
        showError(`Speech synthesis error: ${event.error}`);
        currentChunkIndex++;
        speakNextChunk();
      }
    };

    const chunkDuration = chunk.length * 50;
    const minDuration = 3000;
    const maxDuration = 15000;
    const timeout = Math.max(minDuration, Math.min(maxDuration, chunkDuration));

    timeoutId = setTimeout(() => {
      currentChunkIndex++;
      speakNextChunk();
    }, timeout);

    try {
      window.speechSynthesis.speak(utterance);
    } catch (error) {
      showError('Failed to start text-to-speech');
      clearTimeout(timeoutId);
      buttons.forEach((btn) => btn.classList.remove('speaking'));
      clearInterval(resumeInterval);
    }
  }

  speakNextChunk();
}

function stopSpeaking() {
  /**
   * Stops any currently playing text-to-speech.
   * @returns {void}
   */
  if (window.speechSynthesisSupported) {
    window.speechSynthesis.cancel();
  }

  const buttons = document.querySelectorAll('.read-aloud-btn.speaking');
  buttons.forEach((btn) => btn.classList.remove('speaking'));

  if (window.speechSynthesisResumeInterval) {
    clearInterval(window.speechSynthesisResumeInterval);
    window.speechSynthesisResumeInterval = null;
  }

  const errorMessages = document.querySelectorAll('.speech-error-message');
  errorMessages.forEach((msg) => {
    msg.style.opacity = '0';
    setTimeout(() => {
      if (msg.parentNode) {
        msg.parentNode.removeChild(msg);
      }
    }, 500);
  });
}

function extractTextFromHTML(html) {
  /**
   * Extracts text content from an HTML string.
   * @param {string} html - The HTML string to extract text from.
   * @returns {string} The extracted text.
   */
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = html;
  const extractedText = tempDiv.textContent || tempDiv.innerText || '';
  return extractedText;
}

function appendMessage(message, isUser = false, isError = false, images = []) {
  /**
   * Appends a message to the chat window.
   * @param {string} message - The message content.
   * @param {boolean} isUser - Whether the message is from the user.
   * @param {boolean} isError - Whether the message is an error message.
   * @param {string[]} images - An array of image URLs attached to the message.
   * @returns {void}
   */
  const chatMessages = document.getElementById('chatMessages');
  const messageDiv = document.createElement('div');

  const baseClasses = 'message-appear p-4 rounded-lg';

  if (isUser) {
    messageDiv.className = `${baseClasses} ml-auto message-user max-w-[70%]`;
  } else if (isError) {
    messageDiv.className = `${baseClasses} bg-red-500/10 text-red-400 border border-red-500/20`;
  } else {
    messageDiv.className = `${baseClasses} message-ai max-w-[80%]`;
  }

  let content = '';
  if (isUser) {
    content = `<div class="mb-2">${message}</div>`;
    if (images && images.length > 0) {
      content += `<div class="text-sm text-white/60 mt-2 flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4-4m0 0l4 4m-4-4v6m4-10l2.5-2.5M14 9.5L16.5 7M16 7h4v4"></path>
                </svg>
                ${images.length} image${images.length !== 1 ? 's' : ''} attached
            </div>`;
    }
  } else {
    content = isError
      ? `
            <div class="flex items-start gap-2">
                <svg class="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
                <div>${message}</div>
            </div>
        `
      : `
            <div class="prose prose-invert max-w-none message-content">
                ${md.render(message)}
            </div>
        `;

    if (!isError) {
      content += `
                <div class="flex justify-end mt-2">
                    <button class="read-aloud-btn px-2 py-1 bg-accent/10 hover:bg-accent/20 text-accent rounded-lg text-xs flex items-center gap-1 transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path>
                        </svg>
                        Read Aloud
                    </button>
                </div>
            `;
    }
  }

  messageDiv.innerHTML = content;

  if (!isUser && !isError) {
    const readButton = messageDiv.querySelector('.read-aloud-btn');
    if (readButton) {
      readButton.addEventListener('click', function () {
        const messageContent = messageDiv.querySelector('.message-content');
        let textToRead;
        if (messageContent) {
          textToRead = messageContent.textContent || messageContent.innerText || message;
        } else {
          textToRead = message;
        }

        if (this.classList.contains('speaking')) {
          stopSpeaking();
          this.classList.remove('speaking', 'bg-accent', 'text-black');
          this.classList.add('bg-accent/10', 'text-accent');
          this.innerHTML = `
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path>
                        </svg>
                        Read Aloud
                    `;
        } else {
          document.querySelectorAll('.read-aloud-btn.speaking').forEach((btn) => {
            btn.classList.remove('speaking', 'bg-accent', 'text-black');
            btn.classList.add('bg-accent/10', 'text-accent');
            btn.innerHTML = `
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path>
                            </svg>
                            Read Aloud
                        `;
          });

          speakText(textToRead);
          this.classList.add('speaking', 'bg-accent', 'text-black');
          this.classList.remove('bg-accent/10', 'text-accent');
          this.innerHTML = `
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path>
                        </svg>
                        Stop
                    `;

          speechSynthesis.onend = function () {
            if (readButton.classList.contains('speaking')) {
              readButton.classList.remove('speaking', 'bg-accent', 'text-black');
              readButton.classList.add('bg-accent/10', 'text-accent');
              readButton.innerHTML = `
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path>
                                </svg>
                                Read Aloud
                            `;
            }
          };
        }
      });
    }
  }

  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

document.getElementById('newChatBtn').addEventListener('click', function () {
  fetch('/api/chats/cleanup', {
    method: 'POST',
  })
    .then(() => createNewChat())
    .catch((err) => {
      console.error('Error cleaning up empty chats:', err);
      createNewChat();
    });
});

function createNewChat() {
  /**
   * Creates a new chat.
   * @returns {void}
   */
  stopSpeaking();

  fetch('/api/chats/new', {
    method: 'POST',
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.chat_id) {
        document.getElementById('chat_id').value = data.chat_id;
        document.getElementById('chatMessages').innerHTML =
          '<div class="text-center text-white/60 p-8 flex flex-col items-center"><svg class="w-12 h-12 text-accent/40 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg><span>New chat started. Ask something about stocks!</span></div>';
        document.getElementById('message').value = '';
        document.getElementById('stockSymbols').value = '';

        setTimeout(() => {
          currentPage = 1;
          loadChats(currentPage, true);
        }, 300);

        window.history.pushState({}, '', `/chat?chat_id=${data.chat_id}`);
      }
    })
    .catch((err) => {
      console.error('Error creating new chat:', err);
      document.getElementById('chatMessages').innerHTML =
        '<div class="text-center text-red-400 p-8 bg-red-500/10 rounded-lg border border-red-500/20 m-4"><svg class="w-12 h-12 text-red-400/40 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg><p>Error creating new chat. Please try again.</p></div>';
    });
}

function deleteChat(chatId) {
  /**
   * Deletes a chat.
   * @param {string} chatId - The ID of the chat to delete.
   * @returns {void}
   */
  stopSpeaking();

  if (!confirm('Are you sure you want to delete this chat?')) {
    return;
  }
  fetch(`/api/chats/${chatId}`, {
    method: 'DELETE',
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to delete chat: ${response.status} ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.success) {
        const currentChatId = document.getElementById('chat_id').value;
        if (currentChatId === chatId.toString()) {
          createNewChat();
        }
        loadChats(currentPage, true);
        showSuccess('Chat deleted successfully');
      }
    })
    .catch((error) => {
      console.error('Error deleting chat:', error);
      showError('Failed to delete chat');
    });
}

function clearAllChats() {
  /**
   * Clears all chats.
   * @returns {void}
   */
  stopSpeaking();

  if (!confirm('Are you sure you want to delete all chats? This action cannot be undone.')) {
    return;
  }
  fetch('/api/chats/clear_all', {
    method: 'DELETE',
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to clear chats: ${response.status} ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.success) {
        createNewChat();
        loadChats(1, true);
        showSuccess('All chats cleared successfully');
      }
    })
    .catch((error) => {
      console.error('Error clearing chats:', error);
      showError('Failed to clear chats');
    });
}

document.getElementById('clearAllChatsBtn').addEventListener('click', clearAllChats);

function loadInitialChat() {
  /**
   * Loads the initial chat based on the chat_id URL parameter.
   * @returns {void}
   */
  const urlParams = new URLSearchParams(window.location.search);
  const chatId = urlParams.get('chat_id');
  if (chatId) {
    openChat(chatId);
  }

  const symbol = urlParams.get('symbol');
  if (symbol) {
    document.getElementById('stockSymbols').value = symbol;
  }

  loadChats(1, true);
}

function initializeExportDropdown() {
  /**
   * Initializes the export dropdown functionality.
   * @returns {void}
   */
  const exportButton = document.getElementById('exportButton');
  const exportOptions = document.getElementById('exportOptions');

  exportButton.addEventListener('click', function (e) {
    e.stopPropagation();
    exportOptions.classList.toggle('hidden');
  });

  document.addEventListener('click', function () {
    exportOptions.classList.add('hidden');
  });

  document.querySelectorAll('.export-option').forEach((option) => {
    option.addEventListener('click', function (e) {
      e.stopPropagation();
      const format = this.getAttribute('data-format');
      const chatId = document.getElementById('chat_id').value;

      if (!chatId) {
        showError('No chat selected to export');
        return;
      }

      exportChat(chatId, format);
      exportOptions.classList.add('hidden');
    });
  });
}
function exportChat(chatId, format) {
  /**
   * Exports a chat in the specified format.
   * @param {string} chatId - The ID of the chat to export.
   * @param {string} format - The format to export the chat in ('json' or 'csv').
   * @returns {void}
   */
  const loadingId = showLoading(`Exporting chat as ${format.toUpperCase()}...`);

  fetch(`/api/chats/${chatId}`)
    .then((response) => response.json())
    .then((data) => {
      hideLoading(loadingId);

      if (!data.messages || data.messages.length === 0) {
        showError('No messages to export');
        return;
      }

      let exportData;
      let fileName;
      let mimeType;

      if (format === 'json') {
        exportData = JSON.stringify(data, null, 2);
        fileName = `chat_${chatId}_${formatDateForFileName(new Date())}.json`;
        mimeType = 'application/json';
      } else if (format === 'csv') {
        exportData = convertToCSV(data);
        fileName = `chat_${chatId}_${formatDateForFileName(new Date())}.csv`;
        mimeType = 'text/csv';
      }

      downloadFile(exportData, fileName, mimeType);
    })
    .catch((error) => {
      hideLoading(loadingId);
      console.error('Error exporting chat:', error);
      showError('Error exporting chat. Please try again.');
    });
}

function convertToCSV(chatData) {
  /**
   * Converts chat data to CSV format.
   * @param {object} chatData - The chat data object containing messages.
   * @returns {string} - The CSV formatted string.
   */
  let csv = 'Timestamp,Role,Content\n';

  chatData.messages.forEach((msg) => {
    const timestamp = new Date(msg.created_at || new Date()).toISOString();
    const role = msg.is_user ? 'User' : 'Assistant';
    const content = `"${msg.content.replace(/"/g, '""')}"`;

    csv += `${timestamp},${role},${content}\n`;
  });

  return csv;
}

function formatDateForFileName(date) {
  /**
   * Formats a date object into a string suitable for use in a filename.
   * @param {Date} date - The date object to format.
   * @returns {string} - The formatted date string.
   */
  return date
    .toISOString()
    .replace(/:/g, '-')
    .replace(/\..+/, '')
    .replace('T', '_');
}

function downloadFile(content, fileName, mimeType) {
  /**
   * Downloads a file to the user's browser.
   * @param {string} content - The content of the file.
   * @param {string} fileName - The name of the file to be downloaded.
   * @param {string} mimeType - The MIME type of the file.
   * @returns {void}
   */
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.style.display = 'none';

  document.body.appendChild(a);
  a.click();

  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);

  showSuccess(`Chat exported successfully as ${fileName}`);
}

function showSuccess(message, duration = 3000) {
  /**
   * Shows a success notification message.
   * @param {string} message - The message to display.
   * @param {number} duration - The duration (in milliseconds) to display the message.
   * @returns {void}
   */
  const successDiv = document.createElement('div');
  successDiv.className =
    'fixed top-4 right-4 bg-green-500/90 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center gap-3 message-appear';
  successDiv.innerHTML = `
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        <span>${message}</span>
    `;
  document.body.appendChild(successDiv);
  setTimeout(() => {
    successDiv.style.opacity = '0';
    successDiv.style.transform = 'translateY(-20px)';
    successDiv.style.transition = 'all 0.3s ease-out';
    setTimeout(() => successDiv.remove(), 300);
  }, duration);
}

function showLoading(message) {
  /**
   * Shows a loading indicator with a message.
   * @param {string} message - The message to display in the loading indicator.
   * @returns {string} - The ID of the loading indicator element.
   */
  const id = 'loading-' + Date.now();
  const loadingDiv = document.createElement('div');
  loadingDiv.id = id;
  loadingDiv.className =
    'fixed top-4 right-4 bg-dark-300/95 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center gap-3 message-appear';
  loadingDiv.innerHTML = `
        <div class="w-5 h-5">
            <div class="w-full h-full border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
        </div>
        <span>${message}</span>
    `;
  document.body.appendChild(loadingDiv);
  return id;
}

function hideLoading(id) {
  /**
   * Hides the loading indicator.
   * @param {string} id - The ID of the loading indicator element to hide.
   * @returns {void}
   */
  const loadingDiv = document.getElementById(id);
  if (loadingDiv) {
    loadingDiv.style.opacity = '0';
    loadingDiv.style.transform = 'translateY(-20px)';
    loadingDiv.style.transition = 'all 0.3s ease-out';
    setTimeout(() => loadingDiv.remove(), 300);
  }
}

function addLoadingAnimation(chatMessages) {
  /**
   * Adds a loading animation to the chat messages area.
   * @param {HTMLElement} chatMessages - The HTML element representing the chat messages area.
   * @returns {void}
   */
  removeLoadingAnimation();
  const loadingDiv = document.createElement('div');
  loadingDiv.id = 'loadingMessage';
  loadingDiv.className =
    'message-appear p-4 rounded-lg message-ai max-w-[80%] flex items-center gap-3';
  loadingDiv.innerHTML = `
    <div class="flex items-center gap-3">
        <div class="w-5 h-5">
            <div class="w-full h-full border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
        </div>
        <div class="flex space-x-2">
            <div class="w-3 h-3 rounded-full bg-accent/40 animate-pulse"></div>
            <div class="w-3 h-3 rounded-full bg-accent/40 animate-pulse [animation-delay:0.2s]"></div>
            <div class="w-3 h-3 rounded-full bg-accent/40 animate-pulse [animation-delay:0.4s]"></div>
        </div>
        <span class="text-sm text-white/60">Generating response...</span>
    </div>
`;
  chatMessages.appendChild(loadingDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeLoadingAnimation() {
  /**
   * Removes the loading animation from the chat messages area.
   * @returns {void}
   */
  const loadingDiv = document.getElementById('loadingMessage');
  if (loadingDiv) {
    loadingDiv.remove();
  }
}

let socket = io({
  transports: ['websocket', 'polling'],
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 20000,
  autoConnect: true,
  forceNew: false,
  path: '/socket.io',
  query: {},
  upgrade: true,
  rememberUpgrade: true,
  timestampRequests: true,
  timestampParam: 't',
  transportOptions: {
    polling: {
      extraHeaders: {}
    }
  }
});

socket.io.on("error", () => {});
socket.io.on("reconnect_error", () => {});
socket.io.on("connect_error", () => {});

socket.on('connect', () => {
  console.log('WebSocket connected');
});

socket.on('disconnect', () => {});

window.addEventListener('error', (e) => {
  if (e.message.includes('WebSocket') || e.message.includes('socket.io')) {
    e.preventDefault();
  }
}, true);

const originalConsoleError = console.error;
console.error = (...args) => {
  if (args.length > 0 && 
      (typeof args[0] === 'string' && 
      (args[0].includes('WebSocket') || 
       args[0].includes('socket.io') ||
       args[0].includes('Invalid session')))) {
    return;
  }
  originalConsoleError.apply(console, args);
};

socket.on('chat_completed', (data) => {
  /**
   * Handles the 'chat_completed' event from the WebSocket.
   * @param {object} data - The data received from the event.
   * @returns {void}
   */
  const operationId = data.operation_id;
  if (pendingOperations.has(operationId)) {
    removeLoadingAnimation();
    appendMessage(data.response, false);
    updateMessageCount(data.messages_left);
    pendingOperations.delete(operationId);
    loadChats();
  }
  updateUsageStats();
});

socket.on('chat_error', (data) => {
  /**
   * Handles the 'chat_error' event from the WebSocket.
   * @param {object} data - The data received from the event.
   * @returns {void}
   */
  const operationId = data.operation_id;
  if (pendingOperations.has(operationId)) {
    removeLoadingAnimation();
    appendMessage(data.error, false, true);
    updateMessageCount(data.messages_left);
    pendingOperations.delete(operationId);
  }
});

function updateMessageCount(messagesLeft) {
  /**
   * Updates the displayed message count.
   * @param {number} messagesLeft - The number of messages left in the subscription.
   * @returns {void}
   */
  const messageCountSpan = document.querySelector('#messageCount');
  const subscriptionLimit = parseInt(messageCountSpan.textContent.split('/')[1]);
  messageCountSpan.textContent = `${subscriptionLimit - messagesLeft}/${subscriptionLimit}`;
  updateProgressBars();
}

function updateProgressBars() {
  /**
   * Updates the progress bars for message and image usage.
   * @returns {void}
   */
  const messageCount = document.getElementById('messageCount').textContent;
  const [used, limit] = messageCount.split('/').map(Number);
  const messagePercent = (used / limit) * 100;
  const messageBar = document.getElementById('messageBar');
  messageBar.style.width = `${messagePercent}%`;
  messageBar.className = `h-1.5 rounded-full relative ${
    messagePercent > 90 ? 'bg-red-500' :
    messagePercent > 75 ? 'bg-yellow-500' :
    'bg-accent'
  }`;

  {% if current_user.subscription.name != "Free" %}
  const imageCount = document.getElementById('imageCount').textContent;
  const [imagesUsed, imageLimit] = imageCount.split('/').map(Number);
  const imagePercent = (imagesUsed / imageLimit) * 100;
  const imageBar = document.getElementById('imageBar');
  imageBar.style.width = `${imagePercent}%`;
  imageBar.className = `h-1.5 rounded-full relative ${
    imagePercent > 90 ? 'bg-red-500' :
    imagePercent > 75 ? 'bg-yellow-500' :
    'bg-highlight'
  }`;
  {% endif %}
}

function updateOperationStatus(operationId) {
  /**
   * Updates the status of a long-running operation.
   * @param {string} operationId - The ID of the operation to check.
   * @returns {void}
   */
  fetch(`/api/chat/status/${operationId}`)
    .then((response) => response.json())
    .then((data) => {
      const loadingMessage = document.getElementById('loadingMessage');
      if (loadingMessage) {
        if (data.current_step) {
          loadingMessage.innerHTML = `
                        <div class="flex flex-col gap-2 w-full">
                            <div class="flex items-center gap-3">
                                <div class="w-5 h-5">
                                    <div class="w-full h-full border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
                                </div>
                                <span>${data.current_step}</span>
                            </div>
                            <div class="text-xs text-white/40 mt-2 pl-8">
                                ${data.steps
                                  .map(
                                    (step, index) => `
                                    <div class="flex items-center gap-2">
                                        ${
                                          index <
                                          data.steps.findIndex(
                                            (s) => s.description === data.current_step
                                          )
                                            ? `<svg class="w-3 h-3 text-accent" fill="currentColor" viewBox="0 0 20 20">
                                                <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/>
                                            </svg>`
                                            : index ===
                                              data.steps.findIndex(
                                                (s) => s.description === data.current_step
                                              )
                                            ? `<div class="w-3 h-3">
                                                <div class="w-full h-full border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
                                            </div>`
                                            : `<div class="w-3 h-3 rounded-full border border-white/20"></div>`
                                        }
                                        <span class="${
                                          index ===
                                          data.steps.findIndex(
                                            (s) => s.description === data.current_step
                                          )
                                            ? 'text-white/80'
                                            : index <
                                              data.steps.findIndex(
                                                (s) => s.description === data.current_step
                                              )
                                            ? 'text-white/60'
                                            : 'text-white/40'
                                        }">${step.description}</span>
                                    </div>
                                  `
                                  )
                                  .join('')}
                            </div>
                        </div>
                    `;
        }
      }
      if (data.status === 'completed') {
        removeLoadingAnimation();
        appendMessage(data.result, false);
        pendingOperations.delete(operationId);
        loadChats();
      } else if (data.status === 'failed') {
        removeLoadingAnimation();
        appendMessage(data.error, false, true);
        pendingOperations.delete(operationId);
      } else if (pendingOperations.has(operationId)) {
        setTimeout(() => updateOperationStatus(operationId), 1500);
      }
    })
    .catch((error) => {
      console.error('Error checking operation status:', error);
      if (pendingOperations.has(operationId)) {
        setTimeout(() => updateOperationStatus(operationId), 3000);
      }
    });
}

console.log("{{ current_user.subscription.name }}");

{% if current_user.subscription.name != "Free" %}

document.getElementById('imageUpload').addEventListener('change', function (e) {
  /**
   * Handles the change event for image upload input.
   * @param {Event} e - The change event.
   * @returns {void}
   */
  const files = Array.from(e.target.files);
  
  const imageLimit = {{ current_user.subscription.image_limit }};
  const dailyImagesUsed = {{ current_user.daily_image_count }};
  const remainingImages = imageLimit - dailyImagesUsed;
  
  if (files.length > 1) {
    showError('Maximum 1 image per message allowed');
    e.target.value = '';
    return;
  }
  
  if (files.length > remainingImages) {
    showError(`You can only upload ${remainingImages} more image${remainingImages !== 1 ? 's' : ''} today`);
    e.target.value = '';
    return;
  }
  
  selectedFiles = files;
  document.getElementById('clearImages').classList.remove('hidden');
  document.getElementById('imageUploadText').textContent = `${files.length} image${files.length !== 1 ? 's' : ''} selected`;

  const imageList = document.getElementById('imageList');
  const previewArea = document.getElementById('imagePreviewArea');
  imageList.innerHTML = '';
  
  if (files.length > 0) {
      previewArea.classList.remove('hidden');
      files.forEach(file => {
        const listItem = document.createElement('div');
        listItem.className = 'flex items-center gap-2 text-white/80 bg-dark-300/30 p-2 rounded';
        listItem.innerHTML = `
                <svg class="w-4 h-4 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4-4m0 0l4 4m-4-4v6m4-10l2.5-2.5M14 9.5L16.5 7M16 7h4v4"></path>
                </svg>
                <span class="truncate">${file.name}</span>
            `;
        imageList.appendChild(listItem);
      });
  } else {
      previewArea.classList.add('hidden');
      document.getElementById('clearImages').classList.add('hidden');
      document.getElementById('imageUploadText').textContent = 'Upload images (max 1)';
  }
});

document.getElementById('clearImages').addEventListener('click', function () {
  /**
   * Clears the selected images.
   * @returns {void}
   */
  selectedFiles = [];
  document.getElementById('imageUpload').value = '';
  document.getElementById('imageUploadText').textContent = 'Upload images (max 1)';
  document.getElementById('clearImages').classList.add('hidden');
  document.getElementById('imagePreviewArea').classList.add('hidden');
  document.getElementById('imageList').innerHTML = '';
});
{% endif %}

const messageInput = document.getElementById('message');
const typingIndicator = document.getElementById('typingIndicator');

messageInput.addEventListener('input', function () {
  /**
   * Shows typing indicator when message input has value and updates token counter.
   * @returns {void}
   */
  
  updateTokenCounter();
  
  if (this.value.length > 0) {
    typingIndicator.innerHTML = '<span class="blinking-cursor">|</span>';
    typingIndicator.classList.remove('invisible');
  } else {
    typingIndicator.classList.add('invisible');
  }
});

document.addEventListener('paste', function(e) {
  /**
   * Handles the paste event for image uploads.
   * @param {Event} e - The paste event.
   * @returns {void}
   */
  {% if current_user.subscription.name != "Free" %}
  const activeElement = document.activeElement;
  const messageInputContainer = document.getElementById('messageInputContainer');
  if (!messageInputContainer || !messageInputContainer.contains(activeElement)) {
      return;
  }

  const items = e.clipboardData.items;
  let imageFiles = [];

  for (let i = 0; i < items.length; i++) {
    if (items[i].type.indexOf('image') !== -1) {
      imageFiles.push(items[i].getAsFile());
    }
  }

  if (imageFiles.length > 0) {
    e.preventDefault();
    
    const imageLimit = {{ current_user.subscription.image_limit }};
    const dailyImagesUsed = {{ current_user.daily_image_count }};
    const remainingImages = imageLimit - dailyImagesUsed;
    const maxImagesPerMessage = 1;
    
    const totalImages = selectedFiles.length + imageFiles.length;

    if (totalImages > maxImagesPerMessage) {
      showError(`Maximum ${maxImagesPerMessage} images per message allowed`);
      return;
    }
    
    if (totalImages > remainingImages) {
      showError(`You can only upload ${remainingImages - selectedFiles.length} more image${(remainingImages - selectedFiles.length) !== 1 ? 's' : ''} today`);
      return;
    }

    selectedFiles = selectedFiles.concat(imageFiles);
    
    document.getElementById('clearImages').classList.remove('hidden');
    document.getElementById('imageUploadText').textContent = `${selectedFiles.length} image${selectedFiles.length !== 1 ? 's' : ''} selected`;

    const imageList = document.getElementById('imageList');
    const previewArea = document.getElementById('imagePreviewArea');
    previewArea.classList.remove('hidden');
    
    imageFiles.forEach(file => {
        const listItem = document.createElement('div');
        listItem.className = 'flex items-center gap-2 text-white/80 bg-dark-300/30 p-2 rounded';
        const fileName = file.name || `Pasted Image ${new Date().toLocaleTimeString()}`; 
        listItem.innerHTML = `
          <svg class="w-4 h-4 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4-4m0 0l4 4M8 12v8m4-16l4 4m0 0l4-4m-4 4v8"/>
          </svg>
          <span class="truncate">${fileName}</span>
        `;
        imageList.appendChild(listItem);
    });
  }
  {% endif %}
});

document.getElementById('chatForm').addEventListener('submit', async function (e) {
  e.preventDefault();

  stopSpeaking();

  const submitButton = this.querySelector('button[type="submit"]');
  const message = document.getElementById('message').value.trim();
  const symbols = document.getElementById('stockSymbols').value.trim();
  const chatId = document.getElementById('chat_id').value;

  if (!message) {
    showError('Please enter a message.');
    document.getElementById('message').classList.add('error-shake');
    setTimeout(() => document.getElementById('message').classList.remove('error-shake'), 500);
    return;
  }
  
  const tokenCount = estimateTokenCount(message);
  if (tokenCount > 500) {
    showError(`Message is too long (${tokenCount}/500 tokens). Please shorten it.`);
    document.getElementById('message').classList.add('error-shake');
    setTimeout(() => document.getElementById('message').classList.remove('error-shake'), 500);
    return;
  }

  submitButton.disabled = true;
  submitButton.classList.add('send-button-animation');
  const originalContent = submitButton.innerHTML;
  submitButton.innerHTML = `
    <svg class="w-5 h-5 animate-spin" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
    </svg>
`;

  const imageInfo = selectedFiles.length > 0 ? selectedFiles.map(f => f.name) : [];
  appendMessage(message, true, false, imageInfo);

  const formData = new FormData();
  formData.append('message', message);
  formData.append('symbols', symbols);

  if (chatId) {
    formData.append('chat_id', chatId);
  }

  {% if current_user.subscription.name != "Free" %}
  selectedFiles.forEach((file, index) => {
    const fileName = file.name || `pasted_image_${index + 1}.png`; 
    formData.append('images', file, fileName);
  });
  {% endif %}

  const chatMessages = document.getElementById('chatMessages');
  addLoadingAnimation(chatMessages);

  try {
    const response = await fetch('/api/chat/queue', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      let errorMsg = 'Failed to send message.';
      try {
          const data = await response.json();
          errorMsg = data.error || errorMsg;
      } catch (jsonError) {
          errorMsg = `Error: ${response.status} ${response.statusText}`;
      }
      throw new Error(errorMsg);
    }

    const data = await response.json();

    if (data.error) {
        throw new Error(data.error);
    }

    if (data.chat_id) {
      const chatIdInput = document.getElementById('chat_id');
      const isNewChat = !chatIdInput.value;
      if (chatIdInput.value !== data.chat_id) {
        chatIdInput.value = data.chat_id;
        window.history.pushState({}, '', `/chat?chat_id=${data.chat_id}`);
      }

      if (isNewChat) {
         setTimeout(() => loadChats(1, true), 150); 
      }
    }

    pendingOperations.add(data.operation_id);
    updateOperationStatus(data.operation_id);

  } catch (error) {
    console.error('Error sending message:', error);
    removeLoadingAnimation();
    showError(error.message || 'An unexpected error occurred.'); 
    appendMessage(`Error: ${error.message || 'Could not send message.'}`, false, true); 
  } finally {
    submitButton.disabled = false;
    submitButton.classList.remove('send-button-animation');
    submitButton.innerHTML = originalContent;
    
    document.getElementById('message').value = ''; 
    typingIndicator.classList.add('invisible');
    updateTokenCounter();

    {% if current_user.subscription.name != "Free" %}
    if (document.getElementById('clearImages')) {
        document.getElementById('clearImages').click(); 
    }
    {% endif %}
  }
});

function showError(message, duration = 3000) {
  /**
   * Shows an error notification message.
   * @param {string} message - The message to display.
   * @param {number} duration - The duration (in milliseconds) to display the message.
   * @returns {void}
   */
  const errorDiv = document.createElement('div');
  errorDiv.className =
    'fixed top-4 right-4 bg-red-500/90 text-white px-6 py-3 rounded-lg shadow-lg error-shake z-50 flex items-center gap-3 message-appear';
  errorDiv.innerHTML = `
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>
        <span>${message}</span>
    `;
  document.body.appendChild(errorDiv);
  setTimeout(() => {
    errorDiv.style.opacity = '0';
    errorDiv.style.transform = 'translateY(-20px)';
    errorDiv.style.transition = 'all 0.3s ease-out';
    setTimeout(() => {
        if (errorDiv.parentNode) { 
            errorDiv.remove();
        }
    }, 300);
  }, duration);
}


function updateUsageStats() {
  /**
   * Updates the displayed usage statistics.
   * @returns {void}
   */
  fetch('/api/metrics/usage')
    .then(response => response.json())
    .then(data => {
      const { messages, images, next_reset } = data;
      const nextReset = new Date(next_reset);
      const timeUntil = Math.max(0, Math.floor((nextReset - new Date()) / 1000));

      document.getElementById('messageCount').textContent =
        `${messages.used}/${messages.limit}`;

      const messagePercent = (messages.used / messages.limit) * 100;
      const messageBar = document.getElementById('messageBar');
      messageBar.style.width = `${messagePercent}%`;
      messageBar.className = `h-1.5 rounded-full relative ${messagePercent > 90 ? 'bg-red-500' :
          messagePercent > 75 ? 'bg-yellow-500' :
            'bg-accent'
        }`;
      {% if current_user.subscription.name != "Free" %}
      document.getElementById('imageCount').textContent =
        `${images.used}/${images.limit}`;

      const imagePercent = (images.used / images.limit) * 100;
      const imageBar = document.getElementById('imageBar');
      imageBar.style.width = `${imagePercent}%`;
      imageBar.className = `h-1.5 rounded-full relative ${imagePercent > 90 ? 'bg-red-500' :
          imagePercent > 75 ? 'bg-yellow-500' :
            'bg-highlight'
        }`;
      {% endif %}

      document.getElementById('resetTime').textContent =
        timeUntil > 3600
          ? `${Math.floor(timeUntil / 3600)}h ${Math.floor((timeUntil % 3600) / 60)}m`
          : `${Math.floor(timeUntil / 60)}m`;
    });
}

let chatRefreshInterval = null;

function updateTokenCounter() {
    const messageInput = document.getElementById('message');
    if (!messageInput) return 0; 

    const tokenCountElement = document.getElementById('tokenCount');
    const tokenCounter = document.getElementById('tokenCounter');
    const text = messageInput.value;
    
    const tokenCount = estimateTokenCount(text);
    
    if (tokenCountElement) {
        tokenCountElement.textContent = tokenCount;
    }
    
    if (tokenCounter) {
        tokenCounter.classList.remove('text-yellow-500', 'text-red-500', 'font-bold');
        tokenCounter.classList.add('text-white/50');

        if (tokenCount > 500) {
            tokenCounter.classList.remove('text-white/50');
            tokenCounter.classList.add('text-red-500', 'font-bold');
        } else if (tokenCount > 400) {
            tokenCounter.classList.remove('text-white/50');
            tokenCounter.classList.add('text-yellow-500');
        }
    }
    
    return tokenCount;
}
  
document.addEventListener('DOMContentLoaded', function () {
  console.log('DOM fully loaded and parsed. Initializing...');

  if (!window.speechSynthesis) {
    console.warn('Speech synthesis not supported by this browser.');
    window.speechSynthesisSupported = false;
  } else {
    window.speechSynthesisSupported = true;
    const voices = window.speechSynthesis.getVoices();
    if (voices.length === 0) {
      window.speechSynthesis.onvoiceschanged = () => {
        console.log('Speech synthesis voices loaded.');
      };
    } else {
      console.log('Speech synthesis voices already available.');
    }
  }

  initializeLanguageSelector();
  initializeExportDropdown();
  handleResize();

  initializeMobileTabs();

  document
    .querySelectorAll('.chat-section')
    .forEach((el) => el.classList.remove('hidden'));
  document.querySelectorAll('.watchlist-section').forEach((el) => {
    if (window.innerWidth >= 768) {
      el.classList.remove('hidden');
    } else {
      el.classList.add('hidden');
    }
  });

  loadWatchlist();

  loadInitialChat();

  setTimeout(() => {
    const url = `/api/chats?page=${currentPage}&per_page=${perPage}&bypass_cache=1`;
    fetch(url)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Error loading chats: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        console.log('Chats data:', data);
        const chatsList = document.getElementById('chatList');
        if (chatsList) {
          if (data.chats && data.chats.length > 0) {
            chatsList.innerHTML = '';
            data.chats.forEach((chat) => {
              const chatElement = createChatElement(chat);
              chatsList.appendChild(chatElement);
            });
          } else {
            chatsList.innerHTML = `
                            <div class="p-4 text-center text-white/60">
                                <svg class="w-12 h-12 mx-auto mb-2 text-accent/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                                </svg>
                                <p>${getTranslation('noChatsYet')}</p>
                            </div>
                        `;
          }
        }
      })
      .catch((error) => {
        console.error('Error refreshing chats:', error);
        createNewChat();
      });
  }, 500);

  updateUsageStats();
  updateTokenCounter();

  window.addEventListener('resize', debounce(handleResize, 150));

  const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
  if (mobileSidebarToggle) {
    mobileSidebarToggle.addEventListener('click', function () {
      const sidebar = document.getElementById('sidebar');
      const openIcon = document.getElementById('sidebarOpenIcon');
      const closeIcon = document.getElementById('sidebarCloseIcon');
      if (!sidebar || !openIcon || !closeIcon) return;

      const isSidebarVisible = !sidebar.classList.contains('-translate-x-full');
      if (!isSidebarVisible) {
        sidebar.classList.remove('-translate-x-full');
        openIcon.classList.add('hidden');
        closeIcon.classList.remove('hidden');

        if (!document.getElementById('sidebarBackdrop')) {
          const backdrop = document.createElement('div');
          backdrop.id = 'sidebarBackdrop';
          backdrop.className =
            'fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden opacity-0 transition-opacity duration-300';
          backdrop.onclick = closeSidebar;
          document.body.appendChild(backdrop);
          requestAnimationFrame(() => {
            backdrop.classList.add('opacity-100');
          });
          document.body.style.overflow = 'hidden';
        }
      } else {
        closeSidebar();
      }
    });
  } else {
    console.warn("Element with ID 'mobileSidebarToggle' not found.");
  }

  const newChatBtn = document.getElementById('newChatBtn');
  if (newChatBtn) {
  } else {
    console.warn("Element with ID 'newChatBtn' not found.");
  }

  const clearAllChatsBtn = document.getElementById('clearAllChatsBtn');
  if (clearAllChatsBtn) {
    clearAllChatsBtn.addEventListener('click', clearAllChats);
  } else {
    console.warn("Element with ID 'clearAllChatsBtn' not found.");
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      console.log('Tab became visible, refreshing chats.');
      loadChats(currentPage, true);
    } else {
      console.log('Tab became hidden.');
      stopSpeaking();
    }
  });

  window.addEventListener('beforeunload', () => {
    console.log('Page unloading. Cleaning up intervals and speech.');
    if (chatRefreshInterval) {
      clearInterval(chatRefreshInterval);
    }
    stopSpeaking();
  });

  setInterval(updateUsageStats, 60000);

  if (chatRefreshInterval) clearInterval(chatRefreshInterval);
  chatRefreshInterval = setInterval(() => {
    if (document.visibilityState === 'visible') {
      console.log('Refreshing chat list periodically.');
      loadChats(currentPage, true);
    }
  }, 60000);

  console.log('Initialization complete.');

  initializeStockSymbolSuggestions();
});

async function loadMoreChats() {
  /**
   * Loads the next page of chats
   */
  currentPage++;
  await loadChats();
}

document.addEventListener('DOMContentLoaded', function () {
  console.log('Adding direct watchlist visibility handler');

  const watchlistTabBtn = document.getElementById('watchlistTabBtn');
  if (watchlistTabBtn) {
    watchlistTabBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('WATCHLIST TAB CLICKED - FORCING VISIBILITY');

      const sidebar = document.getElementById('sidebar');
      if (sidebar) {
        const chatTabBtn = document.getElementById('chatTabBtn');
        if (chatTabBtn) {
          chatTabBtn.classList.remove(
            'bg-accent/20',
            'border-accent/30',
            'chat-tab-active'
          );
          chatTabBtn.classList.add(
            'text-white/60',
            'hover:text-white',
            'hover:bg-dark-300/50'
          );
        }

        watchlistTabBtn.classList.add(
          'bg-accent/20',
          'border-accent/30',
          'chat-tab-active'
        );
        watchlistTabBtn.classList.remove(
          'text-white/60',
          'hover:text-white',
          'hover:bg-dark-300/50'
        );

        sidebar.querySelectorAll('.chat-section').forEach((el) => {
          el.style.display = 'none';
          el.classList.add('hidden');
        });

        const watchlistDiv = document.getElementById('watchlist');
        if (watchlistDiv) {
          console.log('FORCING WATCHLIST DISPLAY');
          watchlistDiv.style.display = 'block';
          watchlistDiv.classList.remove('hidden');

          setTimeout(() => {
            const computedStyle = window.getComputedStyle(watchlistDiv);
            console.log('Watchlist computed display:', computedStyle.display);
            console.log(
              'Watchlist has hidden class:',
              watchlistDiv.classList.contains('hidden')
            );

            if (computedStyle.display === 'none') {
              watchlistDiv.style.display = 'block !important';
              document.head.insertAdjacentHTML(
                'beforeend',
                '<style>#watchlist { display: block !important; }</style>'
              );
            }
          }, 50);

          sidebar.querySelectorAll('.watchlist-section').forEach((el) => {
            el.style.display = 'block';
            el.classList.remove('hidden');
          });

          loadWatchlist();
        } else {
          console.error('Watchlist div not found!');
        }
      }
    });
  }

  const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
  if (mobileSidebarToggle) {
    const originalClickHandler = mobileSidebarToggle.onclick;
    mobileSidebarToggle.onclick = function (e) {
      if (originalClickHandler) originalClickHandler.call(this, e);

      setTimeout(() => {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && !sidebar.classList.contains('-translate-x-full')) {
          const chatTabBtn = document.getElementById('chatTabBtn');
          if (chatTabBtn) {
            chatTabBtn.click();
          }
        }
      }, 50);
    };
  }
});

function initializeStockSymbolSuggestions() {
  /**
   * Initializes the stock symbol suggestions functionality.
   */
  const stockSymbolsInput = document.getElementById('stockSymbols');
  if (!stockSymbolsInput) return;

  const suggestionsContainer = document.createElement('div');
  suggestionsContainer.id = 'symbolSuggestions';
  suggestionsContainer.className =
    'absolute z-20 w-full bg-dark-200 border border-accent/20 rounded-lg mt-1 shadow-lg max-h-48 overflow-y-auto hidden';

  stockSymbolsInput.parentNode.appendChild(suggestionsContainer);

  stockSymbolsInput.addEventListener('input', function (e) {
    const query = e.target.value.trim().split(',').pop().trim();

    if (suggestionTimeout) {
      clearTimeout(suggestionTimeout);
    }

    if (!query) {
      suggestionsContainer.classList.add('hidden');
      return;
    }

    suggestionTimeout = setTimeout(() => {
      fetchStockSuggestions(query);
    }, 300);
  });

  document.addEventListener('click', function (e) {
    if (
      !stockSymbolsInput.contains(e.target) &&
      !suggestionsContainer.contains(e.target)
    ) {
      suggestionsContainer.classList.add('hidden');
    }
  });

  stockSymbolsInput.addEventListener('focus', function (e) {
    const query = e.target.value.trim().split(',').pop().trim();
    if (query && query.length > 0) {
      fetchStockSuggestions(query);
    }
  });

  function fetchStockSuggestions(query) {
    /**
     * Fetches stock symbol suggestions from the API.
     * @param {string} query - The search query.
     */
    if (!query || query.length < 1) {
      suggestionsContainer.classList.add('hidden');
      return;
    }

    fetch(`/api/stock/suggest/${encodeURIComponent(query)}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Error: ${response.status} ${response.statusText}`);
        }
        return response.json();
      })
      .then((data) => {
        if (!data || !data.length) {
          suggestionsContainer.classList.add('hidden');
          return;
        }

        renderSuggestions(data);
      })
      .catch((error) => {
        console.error('Error fetching stock suggestions:', error);
        suggestionsContainer.classList.add('hidden');
      });
  }

  function renderSuggestions(suggestions) {
    /**
     * Renders stock suggestions in the suggestions container.
     * @param {Array} suggestions - The stock suggestions array.
     */
    suggestionsContainer.innerHTML = '';

    if (!suggestions || suggestions.length === 0) {
      suggestionsContainer.classList.add('hidden');
      return;
    }

    suggestions.forEach((stock) => {
      const suggestionItem = document.createElement('div');
      suggestionItem.className =
        'flex items-center justify-between px-4 py-2 hover:bg-accent/10 cursor-pointer transition-colors';

      const nameDisplay = stock.name
        ? `<span class="text-sm text-white/80 truncate">${stock.name}</span>`
        : '';

      const extraInfoDisplay = `
        <span class="text-xs uppercase px-1.5 py-0.5 rounded font-semibold mr-1.5 ${
          stock.type === 'crypto'
            ? 'bg-highlight/10 text-highlight'
            : 'bg-accent/10 text-accent'
        }">${stock.type || 'N/A'}</span>
        <span class="text-xs text-white/50">${stock.exchange || '-'}</span>
      `;

      suggestionItem.innerHTML = `
        <div class="flex flex-col">
          <span class="font-semibold text-white">${stock.symbol}</span>
          ${nameDisplay}
          <div class="mt-1">${extraInfoDisplay}</div>
        </div>
        <button class="text-accent hover:text-accent-light p-1 rounded-full hover:bg-accent/10 transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
          </svg>
        </button>
      `;

      suggestionItem.addEventListener('click', () => {
        addSymbolToInput(stock.symbol);
      });

      suggestionsContainer.appendChild(suggestionItem);
    });

    suggestionsContainer.classList.remove('hidden');
  }

  function addSymbolToInput(symbol) {
    /**
     * Adds a symbol to the input field and maintains proper comma formatting.
     * @param {string} symbol - The stock symbol to add.
     */
    const currentValue = stockSymbolsInput.value;
    const parts = currentValue.split(',').map((part) => part.trim());

    parts.pop();

    parts.push(symbol);

    stockSymbolsInput.value = parts.join(', ') + (parts.length > 0 ? ', ' : '');

    suggestionsContainer.classList.add('hidden');

    stockSymbolsInput.focus();
    stockSymbolsInput.selectionStart = stockSymbolsInput.value.length;
    stockSymbolsInput.selectionEnd = stockSymbolsInput.value.length;

    stockSymbolsInput.classList.add('border-accent');
    setTimeout(() => stockSymbolsInput.classList.remove('border-accent'), 800);
  }
}