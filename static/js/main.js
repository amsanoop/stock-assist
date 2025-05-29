function searchStock() {
  /**
   * Searches for a stock by symbol and displays the results.
   */
  const symbol = document.getElementById("stockSearch").value.toUpperCase();
  if (!symbol) return;

  fetch(`/api/stock/${symbol}`)
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showSuggestions(data.suggestions || []);
        throw new Error(data.error);
      }

      const stockResult = document.getElementById("stockResult");
      stockResult.classList.remove("hidden");

      document.getElementById("stockName").textContent = data.name;
      document.getElementById("stockSymbol").textContent = data.symbol;
      document.getElementById("stockPrice").textContent = `$${data.price.toFixed(
        2
      )}`;

      const changeElement = document.getElementById("stockChange");
      const changeValue = `${(data.change * 100).toFixed(2)}%`;
      changeElement.textContent = changeValue;
      changeElement.classList.remove("text-red-500", "text-accent");
      changeElement.classList.add(
        data.change >= 0 ? "text-accent" : "text-red-500"
      );

      document.getElementById("marketCap").textContent =
        formatMarketCap(data.marketCap);
      document.getElementById("volume").textContent = formatNumber(data.volume);
      document.getElementById("peRatio").textContent = data.peRatio
        ? data.peRatio.toFixed(2)
        : "N/A";
      document.getElementById("dayHigh").textContent = `$${data.dayHigh.toFixed(
        2
      )}`;
      document.getElementById("dayLow").textContent = `$${data.dayLow.toFixed(
        2
      )}`;

      const exchangeElement = document.getElementById("exchange");
      if (exchangeElement) {
        exchangeElement.textContent = data.exchange;
      }

      const screenerElement = document.getElementById("screener");
      if (screenerElement) {
        screenerElement.textContent = data.screener;
      }

      if (data.recommendation) {
        const recommendationElement =
          document.getElementById("recommendation");
        if (recommendationElement) {
          recommendationElement.textContent = data.recommendation;
          recommendationElement.className = `text-lg font-bold ${
            data.recommendation === "BUY"
              ? "text-green-500"
              : data.recommendation === "SELL"
              ? "text-red-500"
              : "text-yellow-500"
          }`;
        }
      }

      showStockResult();
      hideSuggestions();
    })
    .catch((error) => {
      console.error("Error:", error);
    });
}

function initTiltEffect() {
  /**
   * Initializes the tilt effect for elements with the class 'tilt-card'.
   */
  const cards = document.querySelectorAll(".tilt-card");
  cards.forEach((card) => {
    VanillaTilt.init(card, {
      max: 5,
      speed: 400,
      glare: true,
      "max-glare": 0.2,
      scale: 1.02,
    });
  });
}

function updateStockDisplay(data) {
  /**
   * Updates the stock display with the provided data, animating the changes.
   * @param {object} data - The stock data to display.
   */
  const stockResult = document.getElementById("stockResult");
  stockResult.classList.remove("hidden");

  const metrics = [
    { id: "stockName", value: data.name, delay: 0 },
    { id: "stockPrice", value: formatCurrency(data.price), delay: 100 },
    { id: "stockChange", value: formatPercentage(data.change), delay: 200 },
    { id: "marketCap", value: formatMarketCap(data.marketCap), delay: 300 },
    { id: "volume", value: formatNumber(data.volume), delay: 400 },
    {
      id: "peRatio",
      value: data.peRatio ? data.peRatio.toFixed(2) : "N/A",
      delay: 500,
    },
  ];

  metrics.forEach(({ id, value, delay }) => {
    setTimeout(() => {
      const element = document.getElementById(id);
      element.style.opacity = "0";
      element.textContent = value;
      element.classList.add("animate-metric-slide");
      element.style.opacity = "1";
    }, delay);
  });

  const changeElement = document.getElementById("stockChange");
  changeElement.className = `text-lg font-bold ${
    data.change >= 0
      ? "text-accent animate-pulse-subtle"
      : "text-red-500 animate-pulse-subtle"
  }`;

  initTiltEffect();
}

function showError(message) {
  /**
   * Displays an error message in an alert box.
   * @param {string} message - The error message to display.
   */
  alert(message);
}

function formatCurrency(value) {
  /**
   * Formats a number as currency (USD).
   * @param {number} value - The number to format.
   * @returns {string} The formatted currency string.
   */
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function formatNumber(value) {
  /**
   * Formats a number with commas.
   * @param {number} value - The number to format.
   * @returns {string} The formatted number string.
   */
  return new Intl.NumberFormat().format(value);
}

function formatMarketCap(value) {
  /**
   * Formats a market cap value to a human-readable string (e.g., $1.23T, $4.56B, $7.89M).
   * @param {number} value - The market cap value.
   * @returns {string} The formatted market cap string.
   */
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  return formatCurrency(value);
}

function formatPercentage(value) {
  /**
   * Formats a number as a percentage.
   * @param {number} value - The number to format.
   * @returns {string} The formatted percentage string.
   */
  return `${(value * 100).toFixed(2)}%`;
}

function showNotification(message, type = "success") {
  /**
   * Shows a notification message on the screen.
   * @param {string} message - The message to display.
   * @param {string} type - The type of notification ('success', 'error', 'info', or any other value for gray).
   */
  const existingNotifications = document.querySelectorAll(".notification");
  existingNotifications.forEach((notification) => notification.remove());

  const notification = document.createElement("div");
  notification.className = `notification fixed top-4 right-4 px-4 py-2 rounded-lg text-white transition-opacity duration-300 z-50 ${
    type === "success"
      ? "bg-green-500"
      : type === "error"
      ? "bg-red-500"
      : type === "info"
      ? "bg-blue-500"
      : "bg-gray-500"
  }`;
  notification.textContent = message;
  document.body.appendChild(notification);

  setTimeout(() => {
    notification.classList.add("opacity-0");
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

function debounce(func, wait) {
  /**
   * Debounces a function, delaying its execution until after a specified wait time.
   * @param {function} func - The function to debounce.
   * @param {number} wait - The wait time in milliseconds.
   * @returns {function} A new function that is the debounced version of the original.
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

function copyToClipboard(text) {
  /**
   * Copies text to the clipboard and shows a notification.
   * @param {string} text - The text to copy.
   */
  navigator.clipboard.writeText(text).then(
    () => showNotification("Copied to clipboard"),
    () => showNotification("Failed to copy to clipboard", "error")
  );
}

function showSuggestions(suggestions) {
  /**
   * Displays stock suggestions in a dropdown.
   * @param {array} suggestions - An array of suggestion objects.
   */
  const searchInput = document.getElementById("stockSearch");
  let suggestionsDiv = document.getElementById("stockSuggestions");

  if (!suggestionsDiv) {
    suggestionsDiv = document.createElement("div");
    suggestionsDiv.id = "stockSuggestions";
    suggestionsDiv.className =
      "absolute left-0 right-0 z-50 mt-2 bg-primary-50/95 backdrop-blur-xl border border-white/10 rounded-lg shadow-lg max-h-60 overflow-auto";

    const searchContainer = searchInput.closest(".relative");
    searchContainer.appendChild(suggestionsDiv);
  }

  if (suggestions.length === 0) {
    suggestionsDiv.style.display = "none";
    return;
  }

  suggestionsDiv.innerHTML = suggestions
    .map(
      (suggestion) => `
        <div class="suggestion p-3 hover:bg-white/5 cursor-pointer transition-colors duration-200" 
             onclick="selectSuggestion('${suggestion.exchange}:${suggestion.symbol}')">
            <div class="font-medium text-white">${suggestion.symbol}</div>
            <div class="text-sm text-white/60">${suggestion.name}</div>
            <div class="text-xs text-white/40">${suggestion.exchange} (${
        suggestion.screener || suggestion.type
      })</div>
        </div>
    `
    )
    .join("");

  suggestionsDiv.style.display = "block";
}

function hideSuggestions() {
  /**
   * Hides the stock suggestions dropdown.
   */
  const suggestionsDiv = document.getElementById("stockSuggestions");
  if (suggestionsDiv) {
    suggestionsDiv.style.display = "none";
  }
}

function selectSuggestion(symbol) {
  /**
   * Selects a suggestion from the dropdown and populates the search input.
   * @param {string} symbol - The symbol of the selected suggestion.
   */
  const searchInput = document.getElementById("stockSearch");
  searchInput.value = symbol;
  hideSuggestions();
  searchStock();
}

function showStockResult() {
  /**
   * Shows the stock result element with a slide-in animation.
   */
  const stockResult = document.getElementById("stockResult");
  stockResult.classList.remove("hidden");
  requestAnimationFrame(() => {
    stockResult.classList.add("animate-slide-in");
    stockResult.classList.remove("opacity-0");
  });
}

document.addEventListener("click", function (event) {
  const suggestionsDiv = document.getElementById("stockSuggestions");
  const searchInput = document.getElementById("stockSearch");

  if (
    suggestionsDiv &&
    searchInput &&
    !suggestionsDiv.contains(event.target) &&
    event.target !== searchInput
  ) {
    hideSuggestions();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("stockSearch");
  if (searchInput) {
    searchInput.addEventListener("focus", () => {
      searchInput.classList.add("animate-search-glow");
    });
    searchInput.addEventListener("blur", () => {
      searchInput.classList.remove("animate-search-glow");
    });

    const debouncedSuggest = debounce((query) => {
      if (query.length > 0) {
        fetch(`/api/stock/suggest/${query}`)
          .then((response) => response.json())
          .then((suggestions) => {
            showSuggestions(suggestions);
          })
          .catch((error) => {
            console.error("Error fetching suggestions:", error);
          });
      } else {
        hideSuggestions();
      }
    }, 300);

    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.trim();
      debouncedSuggest(query);
    });

    searchInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        searchStock();
      }
    });
  }

  const flashMessages = document.querySelectorAll('[role="alert"]');
  flashMessages.forEach((message) => {
    setTimeout(() => {
      message.classList.add("opacity-0");
      setTimeout(() => message.remove(), 300);
    }, 5000);
  });

  initTiltEffect();
});
