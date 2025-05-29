function debounce(func, wait) {
  /**
   * Delays the execution of a function until after a specified wait time.
   *
   * @param func {Function} - The function to debounce.
   * @param wait {number} - The number of milliseconds to delay.
   * @returns {Function} - A new function that delays the execution of the original function.
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

function prioritizeSuggestions(suggestions) {
  /**
   * Sorts suggestions to prioritize the most popular versions of each symbol.
   * @param {Array<Object>} suggestions - An array of suggestion objects.
   * @returns {Array<Object>} - The sorted array of suggestions.
   */
  const popularVersions = {
    'BTC': [{ symbol: 'BTCUSD', exchange: 'BINANCE', name: 'Bitcoin USD', type: 'crypto', screener: 'crypto' }],
    'ETH': [{ symbol: 'ETHUSD', exchange: 'BINANCE', name: 'Ethereum USD', type: 'crypto', screener: 'crypto' }],
    'XRP': [{ symbol: 'XRPUSD', exchange: 'BINANCE', name: 'Ripple USD', type: 'crypto', screener: 'crypto' }],
    'SOL': [{ symbol: 'SOLUSD', exchange: 'BINANCE', name: 'Solana USD', type: 'crypto', screener: 'crypto' }],
    'DOGE': [{ symbol: 'DOGEUSD', exchange: 'BINANCE', name: 'Dogecoin USD', type: 'crypto', screener: 'crypto' }],
    'ADA': [{ symbol: 'ADAUSD', exchange: 'BINANCE', name: 'Cardano USD', type: 'crypto', screener: 'crypto' }],
    'DOT': [{ symbol: 'DOTUSD', exchange: 'BINANCE', name: 'Polkadot USD', type: 'crypto', screener: 'crypto' }],
    'AVAX': [{ symbol: 'AVAXUSD', exchange: 'BINANCE', name: 'Avalanche USD', type: 'crypto', screener: 'crypto' }],
    'MATIC': [{ symbol: 'MATICUSD', exchange: 'BINANCE', name: 'Polygon USD', type: 'crypto', screener: 'crypto' }],
    'LINK': [{ symbol: 'LINKUSD', exchange: 'BINANCE', name: 'Chainlink USD', type: 'crypto', screener: 'crypto' }],
    'UNI': [{ symbol: 'UNIUSD', exchange: 'BINANCE', name: 'Uniswap USD', type: 'crypto', screener: 'crypto' }],
    'SHIB': [{ symbol: 'SHIBUSD', exchange: 'BINANCE', name: 'Shiba Inu USD', type: 'crypto', screener: 'crypto' }],
    'LTC': [{ symbol: 'LTCUSD', exchange: 'BINANCE', name: 'Litecoin USD', type: 'crypto', screener: 'crypto' }],
    'BCH': [{ symbol: 'BCHUSD', exchange: 'BINANCE', name: 'Bitcoin Cash USD', type: 'crypto', screener: 'crypto' }],
    'ATOM': [{ symbol: 'ATOMUSD', exchange: 'BINANCE', name: 'Cosmos USD', type: 'crypto', screener: 'crypto' }],
    'XLM': [{ symbol: 'XLMUSD', exchange: 'BINANCE', name: 'Stellar USD', type: 'crypto', screener: 'crypto' }],
    'ALGO': [{ symbol: 'ALGOUSD', exchange: 'BINANCE', name: 'Algorand USD', type: 'crypto', screener: 'crypto' }],
    'FIL': [{ symbol: 'FILUSD', exchange: 'BINANCE', name: 'Filecoin USD', type: 'crypto', screener: 'crypto' }],
    'ETC': [{ symbol: 'ETCUSD', exchange: 'BINANCE', name: 'Ethereum Classic USD', type: 'crypto', screener: 'crypto' }],
    'NEAR': [{ symbol: 'NEARUSD', exchange: 'BINANCE', name: 'NEAR Protocol USD', type: 'crypto', screener: 'crypto' }],
    'AAPL': [{ symbol: 'AAPL', exchange: 'NASDAQ', name: 'Apple Inc.', searchTerms: ['apple'] }],
    'MSFT': [{ symbol: 'MSFT', exchange: 'NASDAQ', name: 'Microsoft Corporation', searchTerms: ['microsoft'] }],
    'GOOGL': [{ symbol: 'GOOGL', exchange: 'NASDAQ', name: 'Alphabet Inc.', searchTerms: ['google', 'alphabet'] }],
    'GOOG': [{ symbol: 'GOOG', exchange: 'NASDAQ', name: 'Alphabet Inc. Class C', searchTerms: ['google', 'alphabet'] }],
    'AMZN': [{ symbol: 'AMZN', exchange: 'NASDAQ', name: 'Amazon.com, Inc.', searchTerms: ['amazon'] }],
    'TSLA': [{ symbol: 'TSLA', exchange: 'NASDAQ', name: 'Tesla, Inc.', searchTerms: ['tesla'] }],
    'META': [{ symbol: 'META', exchange: 'NASDAQ', name: 'Meta Platforms, Inc.', searchTerms: ['facebook', 'meta'] }],
    'NVDA': [{ symbol: 'NVDA', exchange: 'NASDAQ', name: 'NVIDIA Corporation', searchTerms: ['nvidia'] }],
    'NFLX': [{ symbol: 'NFLX', exchange: 'NASDAQ', name: 'Netflix, Inc.', searchTerms: ['netflix'] }],
    'INTC': [{ symbol: 'INTC', exchange: 'NASDAQ', name: 'Intel Corporation', searchTerms: ['intel'] }],
    'AMD': [{ symbol: 'AMD', exchange: 'NASDAQ', name: 'Advanced Micro Devices, Inc.', searchTerms: ['amd'] }],
    'CRM': [{ symbol: 'CRM', exchange: 'NYSE', name: 'Salesforce, Inc.', searchTerms: ['salesforce'] }],
    'CSCO': [{ symbol: 'CSCO', exchange: 'NASDAQ', name: 'Cisco Systems, Inc.', searchTerms: ['cisco'] }],
    'ORCL': [{ symbol: 'ORCL', exchange: 'NYSE', name: 'Oracle Corporation', searchTerms: ['oracle'] }],
    'IBM': [{ symbol: 'IBM', exchange: 'NYSE', name: 'International Business Machines', searchTerms: ['ibm'] }],
    'ADBE': [{ symbol: 'ADBE', exchange: 'NASDAQ', name: 'Adobe Inc.', searchTerms: ['adobe'] }],
    'PYPL': [{ symbol: 'PYPL', exchange: 'NASDAQ', name: 'PayPal Holdings, Inc.', searchTerms: ['paypal'] }],
    'QCOM': [{ symbol: 'QCOM', exchange: 'NASDAQ', name: 'Qualcomm Incorporated', searchTerms: ['qualcomm'] }],
    'TXN': [{ symbol: 'TXN', exchange: 'NASDAQ', name: 'Texas Instruments Incorporated', searchTerms: ['texas instruments'] }],
    'JPM': [{ symbol: 'JPM', exchange: 'NYSE', name: 'JPMorgan Chase & Co.', searchTerms: ['jpmorgan', 'chase'] }],
    'BAC': [{ symbol: 'BAC', exchange: 'NYSE', name: 'Bank of America Corporation', searchTerms: ['bank of america'] }],
    'WFC': [{ symbol: 'WFC', exchange: 'NYSE', name: 'Wells Fargo & Company', searchTerms: ['wells fargo'] }],
    'C': [{ symbol: 'C', exchange: 'NYSE', name: 'Citigroup Inc.', searchTerms: ['citi', 'citigroup', 'citibank'] }],
    'GS': [{ symbol: 'GS', exchange: 'NYSE', name: 'The Goldman Sachs Group, Inc.', searchTerms: ['goldman', 'goldman sachs'] }],
    'MS': [{ symbol: 'MS', exchange: 'NYSE', name: 'Morgan Stanley', searchTerms: ['morgan'] }],
    'V': [{ symbol: 'V', exchange: 'NYSE', name: 'Visa Inc.', searchTerms: ['visa', 'visa inc'] }],
    'MA': [{ symbol: 'MA', exchange: 'NYSE', name: 'Mastercard Incorporated', searchTerms: ['mastercard', 'master card'] }],
    'AXP': [{ symbol: 'AXP', exchange: 'NYSE', name: 'American Express Company', searchTerms: ['american express', 'amex'] }],
    'JNJ': [{ symbol: 'JNJ', exchange: 'NYSE', name: 'Johnson & Johnson', searchTerms: ['johnson'] }],
    'PFE': [{ symbol: 'PFE', exchange: 'NYSE', name: 'Pfizer Inc.', searchTerms: ['pfizer'] }],
    'ABBV': [{ symbol: 'ABBV', exchange: 'NYSE', name: 'AbbVie Inc.', searchTerms: ['abbvie'] }],
    'MRK': [{ symbol: 'MRK', exchange: 'NYSE', name: 'Merck & Co., Inc.', searchTerms: ['merck'] }],
    'UNH': [{ symbol: 'UNH', exchange: 'NYSE', name: 'UnitedHealth Group Incorporated', searchTerms: ['unitedhealth', 'united health'] }],
    'BMY': [{ symbol: 'BMY', exchange: 'NYSE', name: 'Bristol-Myers Squibb Company', searchTerms: ['bristol', 'squibb'] }],
    'TMO': [{ symbol: 'TMO', exchange: 'NYSE', name: 'Thermo Fisher Scientific Inc.', searchTerms: ['thermo', 'fisher'] }],
    'ABT': [{ symbol: 'ABT', exchange: 'NYSE', name: 'Abbott Laboratories', searchTerms: ['abbott'] }],
    'KO': [{ symbol: 'KO', exchange: 'NYSE', name: 'The Coca-Cola Company', searchTerms: ['coca', 'cola', 'coke'] }],
    'PEP': [{ symbol: 'PEP', exchange: 'NASDAQ', name: 'PepsiCo, Inc.', searchTerms: ['pepsi', 'pepsico'] }],
    'MCD': [{ symbol: 'MCD', exchange: 'NYSE', name: 'McDonald\'s Corporation', searchTerms: ['mcdonald', 'mcdonalds'] }],
    'NKE': [{ symbol: 'NKE', exchange: 'NYSE', name: 'NIKE, Inc.', searchTerms: ['nike'] }],
    'WMT': [{ symbol: 'WMT', exchange: 'NYSE', name: 'Walmart Inc.', searchTerms: ['walmart', 'wal-mart'] }],
    'PG': [{ symbol: 'PG', exchange: 'NYSE', name: 'The Procter & Gamble Company', searchTerms: ['procter', 'gamble', 'p&g'] }],
    'COST': [{ symbol: 'COST', exchange: 'NASDAQ', name: 'Costco Wholesale Corporation', searchTerms: ['costco'] }],
    'HD': [{ symbol: 'HD', exchange: 'NYSE', name: 'The Home Depot, Inc.', searchTerms: ['home depot'] }],
    'DIS': [{ symbol: 'DIS', exchange: 'NYSE', name: 'The Walt Disney Company', searchTerms: ['disney', 'walt'] }],
    'XOM': [{ symbol: 'XOM', exchange: 'NYSE', name: 'Exxon Mobil Corporation', searchTerms: ['exxon', 'mobil'] }],
    'CVX': [{ symbol: 'CVX', exchange: 'NYSE', name: 'Chevron Corporation', searchTerms: ['chevron'] }],
    'COP': [{ symbol: 'COP', exchange: 'NYSE', name: 'ConocoPhillips', searchTerms: ['conoco', 'phillips'] }],
    'BP': [{ symbol: 'BP', exchange: 'NYSE', name: 'BP p.l.c.', searchTerms: ['british petroleum'] }],
    'SHEL': [{ symbol: 'SHEL', exchange: 'NYSE', name: 'Shell plc', searchTerms: ['shell'] }],
    'VZ': [{ symbol: 'VZ', exchange: 'NYSE', name: 'Verizon Communications Inc.', searchTerms: ['verizon'] }],
    'T': [{ symbol: 'T', exchange: 'NYSE', name: 'AT&T Inc.', searchTerms: ['at&t'] }],
    'BRK.A': [{ symbol: 'BRK.A', exchange: 'NYSE', name: 'Berkshire Hathaway Inc.', searchTerms: ['berkshire', 'buffett'] }],
    'BRK.B': [{ symbol: 'BRK.B', exchange: 'NYSE', name: 'Berkshire Hathaway Inc.', searchTerms: ['berkshire', 'buffett'] }],
    'BABA': [{ symbol: 'BABA', exchange: 'NYSE', name: 'Alibaba Group Holding Limited', searchTerms: ['alibaba'] }],
    'TSM': [{ symbol: 'TSM', exchange: 'NYSE', name: 'Taiwan Semiconductor Manufacturing Company', searchTerms: ['taiwan', 'semiconductor'] }],
    'SHOP': [{ symbol: 'SHOP', exchange: 'NYSE', name: 'Shopify Inc.', searchTerms: ['shopify'] }],
    'SE': [{ symbol: 'SE', exchange: 'NYSE', name: 'Sea Limited', searchTerms: ['sea'] }],
    'TCEHY': [{ symbol: 'TCEHY', exchange: 'OTC', name: 'Tencent Holdings Limited', searchTerms: ['tencent'] }],
    'UBER': [{ symbol: 'UBER', exchange: 'NYSE', name: 'Uber Technologies, Inc.', searchTerms: ['uber'] }],
    'ABNB': [{ symbol: 'ABNB', exchange: 'NASDAQ', name: 'Airbnb, Inc.', searchTerms: ['airbnb'] }],
    'ZM': [{ symbol: 'ZM', exchange: 'NASDAQ', name: 'Zoom Video Communications, Inc.', searchTerms: ['zoom'] }],
    'SQ': [{ symbol: 'SQ', exchange: 'NYSE', name: 'Block, Inc.', searchTerms: ['square', 'block'] }],
    'PLTR': [{ symbol: 'PLTR', exchange: 'NYSE', name: 'Palantir Technologies Inc.', searchTerms: ['palantir'] }],
    'GME': [{ symbol: 'GME', exchange: 'NYSE', name: 'GameStop Corp.', searchTerms: ['gamestop'] }],
    'AMC': [{ symbol: 'AMC', exchange: 'NYSE', name: 'AMC Entertainment Holdings, Inc.', searchTerms: ['amc'] }]
  };

  let searchTerm = '';

  if (typeof suggestions === 'object' && !Array.isArray(suggestions) && suggestions.query) {
    searchTerm = suggestions.query.toUpperCase();
  }

  if (!searchTerm && Array.isArray(suggestions) && suggestions.searchTerm) {
    searchTerm = suggestions.searchTerm.toUpperCase();
  }

  if (!searchTerm && suggestions.length > 0) {
    searchTerm = (suggestions[0].symbol || suggestions[0].name || '').toUpperCase();
  }

  if (!searchTerm) {
    console.error("Could not determine a search term for prioritization.");
    return Array.isArray(suggestions) ? suggestions : [];
  }

  const potentialMatches = [];
  const termMatches = [];
  const exactTermMatches = [];

  Object.keys(popularVersions).forEach(key => {
    const item = popularVersions[key][0];

    item.isPreferredMatch = false;
    item.isExactTermMatch = false;

    const exactSymbolMatch = key === searchTerm || (searchTerm.length === 1 && key === searchTerm);

    const strongMatch = key.includes(searchTerm) ||
      (item.name && item.name.toUpperCase().includes(searchTerm));

    const matchInSuggestions = suggestions.some(s => {
      const symbolMatch = s.symbol && (
        s.symbol === key ||
        s.symbol.toUpperCase().includes(key) ||
        key.includes(s.symbol.toUpperCase())
      );

      const nameMatch = s.name && (
        s.name.toUpperCase().includes(key.toUpperCase()) ||
        item.name.toUpperCase().includes(s.name.toUpperCase())
      );

      return symbolMatch || nameMatch;
    });

    const isExactTermMatch = searchTerm && (
      exactSymbolMatch ||
      (item.searchTerms && item.searchTerms.some(term =>
        term.toLowerCase() === searchTerm.toLowerCase()
      ))
    );

    const searchTermMatch = searchTerm && (
      strongMatch ||
      (item.searchTerms && item.searchTerms.some(term =>
        term.toLowerCase().includes(searchTerm.toLowerCase()) ||
        searchTerm.toLowerCase().includes(term.toLowerCase())
      ))
    );

    if (key.length === 1 && key === searchTerm) {
      exactTermMatches.push(key);
    }
    else if (isExactTermMatch) {
      exactTermMatches.push(key);
    }

    if (strongMatch || (searchTermMatch && matchInSuggestions)) {
      termMatches.push(key);
    }

    if (matchInSuggestions) {
      potentialMatches.push(key);
    }
  });

  const allMatches = [...new Set([...exactTermMatches, ...termMatches, ...potentialMatches])];

  const relevantMatches = allMatches.filter(key => {
    const item = popularVersions[key][0];

    if (searchTerm.length === 1) {
      return key === searchTerm ||
        key.startsWith(searchTerm) ||
        (item.searchTerms && item.searchTerms.some(term => term.startsWith(searchTerm.toLowerCase())));
    }

    const relevanceCheck =
      key.includes(searchTerm) ||
      item.name.toUpperCase().includes(searchTerm) ||
      (item.searchTerms && item.searchTerms.some(term =>
        term.toLowerCase().includes(searchTerm.toLowerCase()) ||
        searchTerm.toLowerCase().includes(term.toLowerCase())
      ));

    return relevanceCheck;
  });

  let suggestionsArray = Array.isArray(suggestions) ? [...suggestions] : [];

  relevantMatches.forEach(key => {
    const preferredVersion = popularVersions[key][0];
    const existingIndex = suggestionsArray.findIndex(s =>
      s.symbol === preferredVersion.symbol &&
      s.exchange === preferredVersion.exchange
    );

    if (existingIndex === -1) {
      preferredVersion.isPreferredMatch = true;
      if (exactTermMatches.includes(key)) {
        preferredVersion.isExactTermMatch = true;
      }
      suggestionsArray.unshift(preferredVersion);
    } else {
      suggestionsArray[existingIndex].isPreferredMatch = true;
      if (exactTermMatches.includes(key)) {
        suggestionsArray[existingIndex].isExactTermMatch = true;
      }
    }
  });

  const sortedSuggestions = suggestionsArray.sort((a, b) => {
    const scoreA = (
      (a.isExactTermMatch ? 100 : 0) +
      (a.isPreferredMatch ? 50 : 0)
    );
    const scoreB = (
      (b.isExactTermMatch ? 100 : 0) +
      (b.isPreferredMatch ? 50 : 0)
    );

    if (scoreA !== scoreB) {
      return scoreB - scoreA;
    }

    const baseSymbolA = a.symbol ? a.symbol.split(':').pop().replace(/USD$|USDT$/, '') : '';
    const baseSymbolB = b.symbol ? b.symbol.split(':').pop().replace(/USD$|USDT$/, '') : '';

    if (baseSymbolA === searchTerm && baseSymbolB !== searchTerm) return -1;
    if (baseSymbolB === searchTerm && baseSymbolA !== searchTerm) return 1;

    const aNameMatch = a.name && a.name.toUpperCase().includes(searchTerm);
    const bNameMatch = b.name && b.name.toUpperCase().includes(searchTerm);
    if (aNameMatch && !bNameMatch) return -1;
    if (bNameMatch && !aNameMatch) return 1;

    const aIsListedPopular = popularVersions[baseSymbolA] !== undefined;
    const bIsListedPopular = popularVersions[baseSymbolB] !== undefined;

    const aIsPreferred = Object.keys(popularVersions).some(key => {
      const preferred = popularVersions[key][0];
      return preferred.symbol === a.symbol && preferred.exchange === a.exchange;
    });
    const bIsPreferred = Object.keys(popularVersions).some(key => {
      const preferred = popularVersions[key][0];
      return preferred.symbol === b.symbol && preferred.exchange === b.exchange;
    });

    if (aIsPreferred && !bIsPreferred) return -1;
    if (bIsPreferred && !aIsPreferred) return 1;

    if (aIsListedPopular && !bIsListedPopular) return -1;
    if (bIsListedPopular && !aIsListedPopular) return 1;

    if (a.type === 'crypto' && a.symbol?.includes('USD') &&
      !(b.type === 'crypto' && b.symbol?.includes('USD'))) {
      return -1;
    }
    if (b.type === 'crypto' && b.symbol?.includes('USD') &&
      !(a.type === 'crypto' && a.symbol?.includes('USD'))) {
      return 1;
    }

    return 0;
  });

  return sortedSuggestions;
}

function showSuggestions(suggestions, query = '') {
  /**
   * Displays stock suggestions in the suggestion div.
   *
   * @param {Array<Object>} suggestions - An array of suggestion objects with symbol and name properties.
   * @param {string} query - The original search query entered by the user.
   */
  const suggestionsDiv = document.getElementById("stockSuggestions");
  const featureCards = document.getElementById("featureCards");
  if (!suggestionsDiv) {
    console.error("Stock suggestions div not found");
    return;
  }

  if (suggestions.length === 0) {
    hideSuggestions();
    return;
  }

  if (query) {
    suggestions.query = query;
  }

  const prioritizedSuggestions = prioritizeSuggestions(suggestions);

  suggestionsDiv.innerHTML = prioritizedSuggestions
    .map(
      (suggestion) => `
            <div class="suggestion p-2 md:p-3 hover:bg-accent/10 cursor-pointer transition-colors duration-200 border-b border-accent/10 last:border-0" 
                     onclick="selectSuggestion('${suggestion.symbol}')">
                    <div class="font-medium text-accent text-sm md:text-base">${suggestion.symbol}</div>
                    <div class="text-xs md:text-sm text-white/60">${suggestion.name}</div>
            </div>
    `
    )
    .join("");

  suggestionsDiv.classList.remove("hidden");
  suggestionsDiv.style.display = "block";
  suggestionsDiv.style.position = "absolute";
  suggestionsDiv.style.width = "100%";
  suggestionsDiv.style.zIndex = "50";
  suggestionsDiv.style.maxHeight = "60vh";
  suggestionsDiv.style.overflowY = "auto";

  if (window.innerWidth > 768) {
    setTimeout(() => {
      const suggestionsHeight = suggestionsDiv.offsetHeight;
      if (featureCards) {
        featureCards.style.marginTop = `calc(20px + ${suggestionsHeight}px)`;
      }
    }, 10);
  }
}

function hideSuggestions() {
  /**
   * Hides the stock suggestions and resets the margin top of feature cards.
   */
  const suggestionsDiv = document.getElementById("stockSuggestions");
  const featureCards = document.getElementById("featureCards");

  if (suggestionsDiv) {
    suggestionsDiv.style.display = "none";
    suggestionsDiv.classList.add("hidden");
    suggestionsDiv.innerHTML = "";
    if (featureCards) {
      if (window.innerWidth <= 768) {
        featureCards.style.marginTop = "3rem";
      } else {
        featureCards.style.marginTop = "5rem";
      }
    }
  }
}

function selectSuggestion(symbol) {
  /**
   * Handles the selection of a stock suggestion.
   *
   * @param symbol {string} - The stock symbol of the selected suggestion.
   */
  const searchInput = document.getElementById("stockSearch");
  if (!searchInput) return;

  searchInput.value = symbol;
  hideSuggestions();
  searchStock();
}

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("stockSearch");
  if (searchInput) {
    
    const debouncedSuggest = debounce((query) => {
      if (query.length > 0) {
        fetch(`/api/stock/suggest/${query}`)
          .then((response) => {
            if (!response.ok) {
              throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
          })
          .then((suggestions) => {
            showSuggestions(suggestions, query);
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
        e.preventDefault();
        searchStock();
      }
    });

    document.addEventListener("click", (e) => {
      const suggestionsDiv = document.getElementById("stockSuggestions");
      if (
        searchInput && suggestionsDiv &&
        !searchInput.contains(e.target) &&
        !suggestionsDiv.contains(e.target)
      ) {
        hideSuggestions();
      }
    });
  }
});

function searchStock() {
  /**
   * Navigates to the stock details page for the entered stock symbol.
   */
  const searchInput = document.getElementById("stockSearch");
  if (!searchInput) return;
  
  const symbol = searchInput.value.toUpperCase();
  if (!symbol) return;

  hideSuggestions();

  const stockResult = document.getElementById("stockResult");
  if (stockResult) {
    stockResult.classList.remove("hidden");
    setTimeout(() => {
      stockResult.classList.remove("opacity-0", "translate-y-4");
    }, 50);
  }

  window.location.href = `/stocks?symbol=${symbol}`;
}

document.addEventListener("DOMContentLoaded", function () {
  const typedStrings = window.innerWidth < 768 
    ? [
      "AI-powered stock analysis",
      "Real-time market data",
      "Make informed decisions",
      "Track stocks easily",
    ] 
    : [
      "AI-powered stock analysis and insights",
      "Real-time market data at your fingertips",
      "Make informed trading decisions",
      "Track your favorite stocks effortlessly",
    ];

  new Typed("#typed", {
    strings: typedStrings,
    typeSpeed: 50,
    backSpeed: 30,
    backDelay: 2000,
    loop: true,
  });

  if (window.innerWidth >= 768) {
    VanillaTilt.init(document.querySelectorAll(".tilt-card"), {
      max: 5,
      speed: 400,
      glare: true,
      "max-glare": 0.2,
      scale: 1.02,
    });
  }

  const animateCount = (element) => {
    const target = parseInt(element.dataset.target.replace(/[^0-9]/g, ""));
    const duration = 2000;
    const step = target / (duration / 16);
    let current = 0;

    const timer = setInterval(() => {
      current += step;
      if (current >= target) {
        element.textContent = element.dataset.target;
        clearInterval(timer);
      } else {
        element.textContent = Math.floor(current).toLocaleString();
      }
    }, 16);
  };

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.querySelectorAll(".animate-count").forEach((counter) => {
            animateCount(counter);
          });
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.5 }
  );

  document.querySelectorAll(".animate-count").forEach((counter) => {
    observer.observe(counter.parentElement.parentElement.parentElement);
  });

  document.querySelectorAll(".bg-gradient-to-r").forEach((button) => {
    button.addEventListener("mouseenter", function () {
      const shimmerElement = this.querySelector(".animate-shimmer");
      if (shimmerElement) {
        shimmerElement.style.animation = "none";
        void shimmerElement.offsetWidth;
        shimmerElement.style.animation = "shimmer 1.5s infinite";
      }
    });
  });

  if (!CSS.supports("selector(:has(*))")) {
    document.styleSheets[0].insertRule(
      `
            @keyframes shimmer {
                0% {
                    transform: translateX(-100%);
                }
                100% {
                    transform: translateX(100%);
                }
            }
        `,
      0
    );
  }
});

window.addEventListener('resize', function() {
  const suggestionsDiv = document.getElementById("stockSuggestions");
  const featureCards = document.getElementById("featureCards");

  if (featureCards && (!suggestionsDiv || suggestionsDiv.style.display === "none")) {
    if (window.innerWidth <= 768) {
      featureCards.style.marginTop = "3rem";
    } else {
      featureCards.style.marginTop = "5rem";
    }
  }
});